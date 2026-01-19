import os
import sys
import asyncio
import datetime
import yt_dlp
import zipfile
import io
import shutil
from aiohttp import web
from pyrogram import Client, filters, idle, enums
from pyrogram.types import Message, ChatPermissions
from pyrogram.errors import FloodWait

# ================= CONFIGURATION =================
API_ID = 36982189
API_HASH = "d3ec5feee7342b692e7b5370fb9c8db7"
BOT_TOKEN = "8544773286:AAHkDc5awfunKMaO-407F7JtcmrY1OmazRc"
OWNER_ID = 8072674531 

# List of Group IDs for broadcasting (Include the -100 prefix)
# Example: [-100123456789]
GROUPS_TO_BROADCAST = [] 

DOWNLOAD_PATH = "./downloads"
PORT = int(os.environ.get("PORT", 10000))
BASE_URL = os.environ.get("BASE_URL", "https://group-guard-bot.onrender.com").rstrip('/')

app = Client("SuperBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Storage for download tracking {user_id: {"count": 0, "last_reset": date}}
user_dl_stats = {}

if not os.path.exists(DOWNLOAD_PATH):
    os.makedirs(DOWNLOAD_PATH)

# ================= HELPERS =================
async def smart_vanish(message, delay=1):
    if message.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        await asyncio.sleep(delay)
        try: await message.delete()
        except: pass

async def is_admin(client, chat_id, user_id):
    if user_id == OWNER_ID: return True
    if chat_id == user_id: return user_id == OWNER_ID
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]
    except: return False

# ================= WEB SERVER =================
async def health_check(request):
    return web.Response(text="Bot is Alive!", status=200)

async def start_web_server():
    server = web.Application()
    server.add_routes([web.get('/', health_check), web.static('/watch', DOWNLOAD_PATH)])
    runner = web.AppRunner(server)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()

# ================= FIXED FEATURES =================

@app.on_message(filters.command("broadcast") & filters.user(OWNER_ID))
async def broadcast_handler(client, message):
    if not message.reply_to_message:
        return await message.reply("❌ Reply to a message to broadcast it.")
    
    status = await message.reply("📢 **Broadcasting...**")
    sent = 0
    # Broadcast to all specified groups
    for chat_id in GROUPS_TO_BROADCAST:
        try:
            await message.reply_to_message.copy(chat_id)
            sent += 1
        except Exception: pass
    
    await status.edit(f"✅ **Broadcast Complete!**\nSent to `{sent}` groups.")

@app.on_message(filters.command("stream"))
async def stream_handler(client, message):
    asyncio.create_task(smart_vanish(message, 1))
    if not await is_admin(client, message.chat.id, message.from_user.id): return
    
    target = message.reply_to_message
    if not target:
        return await message.reply("❌ Reply to a video, file, or link to stream.")

    status = await message.reply("🔄 **Generating Streamable Link...**")
    
    try:
        if target.text or target.caption:
            url = target.text or target.caption
            ydl_opts = {'format': 'best', 'quiet': True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                stream_link = info.get('url')
        
        elif target.video or target.document:
            file_path = await client.download_media(target, file_name=f"{DOWNLOAD_PATH}/")
            stream_link = f"{BASE_URL}/watch/{os.path.basename(file_path)}"
        else:
            return await status.edit("❌ Unsupported format.")

        await status.edit(f"🎬 **Stream Link Ready:**\n\n🔗 [Click to Stream]({stream_link})", disable_web_page_preview=True)
    except Exception as e:
        await status.edit(f"❌ Error: {str(e)}")

@app.on_message(filters.command("dl"))
async def download_handler(client, message):
    asyncio.create_task(smart_vanish(message, 1))
    uid = message.from_user.id
    today = datetime.date.today()
    
    # Member Daily Limit Logic
    if not await is_admin(client, message.chat.id, uid):
        if uid not in user_dl_stats or user_dl_stats[uid]["last_reset"] != today:
            user_dl_stats[uid] = {"count": 0, "last_reset": today}
        
        if user_dl_stats[uid]["count"] >= 3:
            m = await message.reply("❌ **Daily Limit Reached!** (3/3). Try again tomorrow.")
            return asyncio.create_task(smart_vanish(m, 5))
        user_dl_stats[uid]["count"] += 1

    url = message.text.split(None, 1)[1] if len(message.command) > 1 else None
    if not url and message.reply_to_message:
        url = message.reply_to_message.text or message.reply_to_message.caption

    if not url:
        return await message.reply("❌ Provide a link or reply to one.")

    status = await message.reply("⏳ **Downloading...**")
    try:
        ydl_opts = {'outtmpl': f'{DOWNLOAD_PATH}/%(title)s.%(ext)s', 'quiet': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info)
        
        await client.send_document(message.chat.id, file_path, caption=f"✅ **Downloaded:** {info.get('title')}")
        os.remove(file_path)
        await status.delete()
    except Exception as e:
        await status.edit(f"❌ **Download Failed:** {str(e)}")

@app.on_message(filters.command(["ban", "unban"]))
async def moderation_handler(client, message):
    asyncio.create_task(smart_vanish(message, 1))
    # Admin check only works in groups; for Private DM, only the Owner can use it
    if not await is_admin(client, message.chat.id, message.from_user.id): return
    
    # Handle both replies and manual IDs
    user_id = None
    if message.reply_to_message:
        user_id = message.reply_to_message.from_user.id
    elif len(message.command) > 1:
        user_id = message.command[1]
    
    if not user_id:
        return await message.reply("❌ Reply to a user or provide their ID.")

    cmd = message.command[0].lower()
    try:
        if cmd == "ban":
            # Ban logic (works in groups; for channels, user must use channel-specific logic)
            await client.ban_chat_member(message.chat.id, user_id)
            await message.reply(f"🚫 **User Banned:** `{user_id}`")
        else:
            await client.unban_chat_member(message.chat.id, user_id)
            await message.reply(f"✅ **User Unbanned:** `{user_id}`")
    except Exception as e:
        await message.reply(f"❌ **Action Failed:** {str(e)}")

# ================= RUNNER =================
async def main():
    await start_web_server()
    await app.start()
    print("--- SuperBot Ready: All Commands Fixed ---")
    await idle()

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
    
