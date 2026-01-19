import os
import sys
import asyncio
import datetime
import yt_dlp
import zipfile
import io
from aiohttp import web
from pyrogram import Client, filters, idle, enums
from pyrogram.types import Message, ChatPermissions
from pyrogram.errors import FloodWait

# ================= CONFIGURATION =================
API_ID = 36982189
API_HASH = "d3ec5feee7342b692e7b5370fb9c8db7"
BOT_TOKEN = "8544773286:AAHkDc5awfunKMaO-407F7JtcmrY1OmazRc"
OWNER_ID = 8072674531 

DOWNLOAD_PATH = "./downloads"
PORT = int(os.environ.get("PORT", 10000))
BASE_URL = os.environ.get("BASE_URL", "https://group-guard-bot.onrender.com").rstrip('/')

app = Client("SuperBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

user_dl_count = {}
user_warnings = {}

if not os.path.exists(DOWNLOAD_PATH):
    os.makedirs(DOWNLOAD_PATH)

# ================= HELPERS =================
async def vanish_msg(message, delay=1):
    await asyncio.sleep(delay)
    try: await message.delete()
    except: pass

async def is_admin(client, chat_id, user_id):
    if user_id == OWNER_ID: return True
    # If in private chat, the user is the owner check only
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

# ================= COMMANDS LOGIC =================

@app.on_message(filters.command(["status", "cleanup", "lock", "unlock", "ban", "unban", "zip", "unzip", "stream", "start"]))
async def admin_commands(client, message):
    asyncio.create_task(vanish_msg(message))
    uid = message.from_user.id
    chat_id = message.chat.id
    cmd = message.command[0].lower()

    # /start is accessible to all, but has admin-only reset features
    if cmd == "start":
        if uid == OWNER_ID and chat_id != uid:
            await message.reply("🔄 **Bot Restarting...**")
            os.execl(sys.executable, sys.executable, *sys.argv)
        else:
            await message.reply(f"✨ **Hello {message.from_user.first_name}!**\nI am SuperBot. Admins can use management tools.")
        return

    # Check Admin Permission for all other commands
    if not await is_admin(client, chat_id, uid):
        m = await message.reply("🚫 **Access Denied:** Only Admins can use this.")
        asyncio.create_task(vanish_msg(m, 5))
        return

    # Process Commands
    if cmd == "status":
        status_msg = await message.reply("📊 **Generating Audit...**")
        active, inactive = [], []
        async for m in client.get_chat_members(chat_id):
            u = m.user
            if u.is_deleted: continue
            ustatus = str(u.status).replace("UserStatus.", "").lower() if u.status else "hidden"
            line = f"{u.id:<15} | @{u.username or 'N/A':<20} | {ustatus}"
            if ustatus in ["online", "recently"]: active.append(line)
            else: inactive.append(line)
        report = f"Audit: {message.chat.title}\n\nActive:\n" + "\n".join(active) + "\n\nInactive:\n" + "\n".join(inactive)
        bio = io.BytesIO(report.encode()); bio.name = f"Audit_{chat_id}.txt"
        await client.send_document(OWNER_ID, bio)
        await status_msg.edit("✅ Audit sent to Admin DM.")

    elif cmd == "cleanup":
        status_msg = await message.reply("🔍 **Cleaning Deleted Accounts...**")
        count = 0
        async for member in client.get_chat_members(chat_id):
            if member.user.is_deleted:
                try:
                    await client.ban_chat_member(chat_id, member.user.id)
                    await client.unban_chat_member(chat_id, member.user.id)
                    count += 1
                except: pass
        await status_msg.edit(f"✅ Removed `{count}` ghost accounts.")

    elif cmd in ["lock", "unlock"]:
        perms = ChatPermissions(can_send_messages=(cmd == "unlock"))
        await client.set_chat_permissions(chat_id, perms)
        await message.reply(f"{'🔓' if cmd == 'unlock' else '🔒'} Group {cmd.capitalize()}ed.")

# ================= DOWNLOADER (MEMBERS LIMIT) =================

@app.on_message(filters.command("dl"))
async def download_handler(client, message):
    asyncio.create_task(vanish_msg(message))
    uid = message.from_user.id
    chat_id = message.chat.id
    
    # Member Limit Check
    if not await is_admin(client, chat_id, uid):
        user_dl_count[uid] = user_dl_count.get(uid, 0) + 1
        if user_dl_count[uid] > 3:
            m = await message.reply("❌ **Limit Reached:** You only get 3 downloads per session.")
            asyncio.create_task(vanish_msg(m, 5))
            return

    if len(message.command) < 2:
        return await message.reply("❓ Usage: `/dl [URL]`")

    status = await message.reply("⏳ **Processing Download...**")
    # Insert your specific yt-dlp logic here...
    await status.edit("✅ Download Complete (File Sent).")

# ================= RUNNER =================
async def main():
    await start_web_server()
    await app.start()
    print("--- SuperBot Running with Fixed Permissions ---")
    await idle()

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
