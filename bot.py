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
GROUPS_TO_BROADCAST = [] 

DOWNLOAD_PATH = "./downloads"
PORT = int(os.environ.get("PORT", 10000))
BASE_URL = os.environ.get("BASE_URL", "https://group-guard-bot.onrender.com").rstrip('/')

app = Client("SuperBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Storage for download tracking
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

# ================= NEW: GROUP GUARD FEATURES =================

# 1. Anti-Link (Removes links from members instantly)
@app.on_message(filters.group & ~filters.service, group=-1)
async def anti_link_handler(client, message):
    if await is_admin(client, message.chat.id, message.from_user.id):
        return
    
    # Check for URLs in text or caption
    entities = message.entities or message.caption_entities
    if entities:
        for entity in entities:
            if entity.type in [enums.MessageEntityType.URL, enums.MessageEntityType.TEXT_LINK]:
                await message.delete()
                return

# 2. Join/Left Tag Cleaner & Auto-Welcome
@app.on_message(filters.service, group=-2)
async def service_handler(client, message):
    # Remove "User Joined" or "User Left" messages instantly
    if message.new_chat_members or message.left_chat_member:
        asyncio.create_task(smart_vanish(message, 0))
    
    # Send Welcome Message for new members
    if message.new_chat_members:
        for member in message.new_chat_members:
            welcome_text = (
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"💐 **Hello, Welcome to our Group!**\n\n"
                f"👤 **Subscriber:** {member.mention}\n"
                f"🆔 **ID:** `{member.id}`\n"
                f"📅 **Date:** `{datetime.datetime.now().strftime('%d %b %Y')}`\n"
                f"━━━━━━━━━━━━━━━━━━━━━"
            )
            w_msg = await message.reply(welcome_text)
            asyncio.create_task(smart_vanish(w_msg, 20)) # Welcome vanishes after 20s

# ================= ADMINISTRATIVE & MODERATION =================

@app.on_message(filters.command("restart") & filters.user(OWNER_ID))
async def restart_handler(client, message):
    await message.reply("🔄 **Bot is Restarting...**")
    os.execl(sys.executable, sys.executable, *sys.argv)

@app.on_message(filters.command("cleanup") & filters.group)
async def cleanup_handler(client, message):
    asyncio.create_task(smart_vanish(message, 1))
    if not await is_admin(client, message.chat.id, message.from_user.id): return
    
    status_msg = await message.reply("🔍 **Scanning for deleted accounts...**")
    deleted_count = 0
    async for member in client.get_chat_members(message.chat.id):
        if member.user.is_deleted:
            try:
                await client.ban_chat_member(message.chat.id, member.user.id)
                await client.unban_chat_member(message.chat.id, member.user.id)
                deleted_count += 1
            except: pass
    await status_msg.edit(f"✅ **Cleanup Complete!** Removed `{deleted_count}` ghost accounts.")

@app.on_message(filters.command(["lock", "unlock"]) & filters.group)
async def lock_unlock_handler(client, message):
    asyncio.create_task(smart_vanish(message, 1))
    if not await is_admin(client, message.chat.id, message.from_user.id): return
    
    is_lock = message.command[0].lower() == "lock"
    permissions = ChatPermissions(
        can_send_messages=not is_lock,
        can_send_media_messages=not is_lock,
        can_send_other_messages=not is_lock,
        can_add_web_page_previews=not is_lock
    )
    
    try:
        await client.set_chat_permissions(message.chat.id, permissions)
        status = "Locked 🔒 (All media & messages disabled)" if is_lock else "Unlocked 🔓"
        await message.reply(f"🛡️ **Group is now {status}**")
    except Exception as e:
        await message.reply(f"❌ Error: {e}")

@app.on_message(filters.command("broadcast") & filters.user(OWNER_ID))
async def broadcast_handler(client, message):
    if not message.reply_to_message:
        return await message.reply("❌ Reply to a post or message to broadcast it.")
    
    status = await message.reply("📢 **Broadcasting to Bot and Groups...**")
    sent = 0
    targets = [message.from_user.id] + GROUPS_TO_BROADCAST
    for chat_id in targets:
        try:
            await message.reply_to_message.copy(chat_id)
            sent += 1
        except: pass
    await status.edit(f"✅ **Broadcast Done!** Sent to `{sent}` locations.")

@app.on_message(filters.command("status") & filters.group)
async def status_handler(client, message):
    asyncio.create_task(smart_vanish(message, 1))
    if not await is_admin(client, message.chat.id, message.from_user.id): return
    
    progress = await message.reply("📊 **Generating Detailed Audit...**")
    active, inactive = [], []
    
    async for member in client.get_chat_members(message.chat.id):
        u = member.user
        if u.is_deleted: continue
        
        uname = f"@{u.username}" if u.username else "No Username"
        ustatus = str(u.status).replace("UserStatus.", "").lower() if u.status else "hidden"
        last_seen = u.last_online_date if hasattr(u, 'last_online_date') and u.last_online_date else "N/A"
        
        info = f"ID: {u.id} | User: {uname} | Status: {ustatus} | Last Seen: {last_seen}"
        if ustatus in ["online", "recently"]: active.append(info)
        else: inactive.append(info)

    report = f"Audit Report for: {message.chat.title}\n\n"
    report += "🟢 ACTIVE USERS:\n" + "\n".join(active) + "\n\n"
    report += "🔴 INACTIVE USERS:\n" + "\n".join(inactive)
    
    bio = io.BytesIO(report.encode()); bio.name = f"Audit_{message.chat.id}.txt"
    await client.send_document(OWNER_ID, bio, caption=f"📑 **Full Status Audit**\nGroup: {message.chat.title}")
    await progress.edit("✅ **Report sent to your DM.**")

# ================= ZIP / UNZIP TOOLS =================

@app.on_message(filters.command(["zip", "unzip"]))
async def zip_unzip_handler(client, message):
    asyncio.create_task(smart_vanish(message, 1))
    if not await is_admin(client, message.chat.id, message.from_user.id): return
    
    cmd = message.command[0].lower()
    password = message.command[1] if len(message.command) > 1 else None

    if cmd == "zip":
        if not message.reply_to_message:
            return await message.reply("❌ Reply to a photo or album to zip.")
        
        status = await message.reply("📦 **Zipping Files...**")
        files_to_zip = []
        
        if message.reply_to_message.media_group_id:
            album = await client.get_media_group(message.chat.id, message.reply_to_message.id)
            for item in album:
                files_to_zip.append(await client.download_media(item, f"{DOWNLOAD_PATH}/"))
        else:
            files_to_zip.append(await client.download_media(message.reply_to_message, f"{DOWNLOAD_PATH}/"))

        zip_path = f"{DOWNLOAD_PATH}/Archive_{message.from_user.id}.zip"
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for f in files_to_zip:
                zipf.write(f, os.path.basename(f))
                os.remove(f)

        await client.send_document(message.chat.id, zip_path, caption=f"✅ ZIP Created! Password: {password if password else 'None'}")
        os.remove(zip_path)
        await status.delete()

    elif cmd == "unzip":
        if not message.reply_to_message or not message.reply_to_message.document:
            return await message.reply("❌ Reply to a .zip file.")
        
        status = await message.reply("📂 **Extracting...**")
        zip_file = await client.download_media(message.reply_to_message, f"{DOWNLOAD_PATH}/")
        ext_dir = f"{DOWNLOAD_PATH}/ext_{message.from_user.id}"
        
        try:
            with zipfile.ZipFile(zip_file, 'r') as zip_ref:
                if password: zip_ref.setpassword(password.encode())
                zip_ref.extractall(ext_dir)
            for root, _, files in os.walk(ext_dir):
                for f in files:
                    await client.send_document(message.chat.id, os.path.join(root, f))
            await status.edit("✅ Extraction Complete!")
        except Exception as e:
            await status.edit(f"❌ Failed: {e}")
        shutil.rmtree(ext_dir, ignore_errors=True); os.remove(zip_file)

# ================= FIXED COMMANDS: STREAM & DL =================

@app.on_message(filters.command("stream"))
async def stream_handler(client, message):
    asyncio.create_task(smart_vanish(message, 1))
    if not await is_admin(client, message.chat.id, message.from_user.id): return
    
    target = message.reply_to_message
    if not target:
        return await message.reply("❌ Reply to a video, file, or link to stream.")

    status = await message.reply("🔄 **Generating Stream Link...**")
    
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
async def download_handler(client, message: Message):
    asyncio.create_task(smart_vanish(message, 1))
    uid = message.from_user.id
    today = datetime.date.today()
    
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
        ydl_opts = {'outtmpl': f'{DOWNLOAD_PATH}/%(title)s.%(ext)s', 'quiet': True, 'format': 'best'}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info)
        
        await client.send_document(message.chat.id, file_path, caption=f"✅ **Downloaded:** {info.get('title')}")
        if os.path.exists(file_path): os.remove(file_path)
        await status.delete()
    except Exception as e:
        await status.edit(f"❌ **Download Failed:** {str(e)}")

# ================= MODERATION: BAN & UNBAN =================

@app.on_message(filters.command(["ban", "unban"]))
async def moderation_handler(client, message):
    asyncio.create_task(smart_vanish(message, 1))
    if not await is_admin(client, message.chat.id, message.from_user.id): return
    
    user_id = None
    if message.reply_to_message:
        user_id = message.reply_to_message.from_user.id
    elif len(message.command) > 1:
        user_id = message.command[1]
    
    if not user_id: return await message.reply("❌ Reply to a user or provide their ID.")

    cmd = message.command[0].lower()
    try:
        if cmd == "ban":
            await client.ban_chat_member(message.chat.id, user_id)
            await message.reply(f"🚫 **User Banned:** `{user_id}`")
        else:
            await client.unban_chat_member(message.chat.id, user_id)
            await message.reply(f"✅ **User Unbanned:** `{user_id}`")
    except Exception as e:
        await message.reply(f"❌ Action Failed: {str(e)}")

# ================= SYSTEM START =================

@app.on_message(filters.command("start"))
async def start_handler(client, message):
    attractive_msg = (
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"✨ **Hello, {message.from_user.first_name}!** ✨\n\n"
        f"💐 **Welcome to SuperBot!**\n"
        f"I am your all-in-one group manager and downloader.\n\n"
        f"🛡️ **Moderation** | 📥 **Downloads**\n"
        f"🎬 **Streaming** | 📦 **Archive Tools**\n"
        f"━━━━━━━━━━━━━━━━━━━━━"
    )
    await message.reply(attractive_msg)

# ================= WEB SERVER & RUNNER =================

async def health_check(request):
    return web.Response(text="Bot is Alive!", status=200)

async def start_web_server():
    server = web.Application()
    server.add_routes([web.get('/', health_check), web.static('/watch', DOWNLOAD_PATH)])
    runner = web.AppRunner(server)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()

async def main():
    await start_web_server()
    await app.start()
    print("--- SuperBot Online: All Commands Fixed ---")
    await idle()

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
        
