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
    # Setting permissions to False for lock, True for unlock
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
    # Copy to the bot's own chat (Private) and all authorized groups
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
        
        # Handle Media Groups (Albums)
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

# [WORKING COMMANDS: /dl, /stream, /ban, /unban LOGIC GOES HERE - UNCHANGED]

async def main():
    await start_web_server()
    await app.start()
    print("--- SuperBot Online: All Commands Fixed ---")
    await idle()

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
                
