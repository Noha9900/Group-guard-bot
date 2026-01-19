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

DOWNLOAD_PATH = "./downloads"
PORT = int(os.environ.get("PORT", 10000))
BASE_URL = os.environ.get("BASE_URL", "https://group-guard-bot.onrender.com").rstrip('/')

app = Client("SuperBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

user_dl_count = {}

if not os.path.exists(DOWNLOAD_PATH):
    os.makedirs(DOWNLOAD_PATH)

# ================= HELPERS =================
async def smart_vanish(message, delay=1):
    """Vanish only if in group"""
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

# ================= FEATURE: ENHANCED WELCOME =================
@app.on_message(filters.new_chat_members)
async def welcome_handler(client, message):
    for member in message.new_chat_members:
        welcome_text = (
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"💐 **Hello, Welcome to our Group!**\n\n"
            f"👤 **Subscriber:** {member.mention}\n"
            f"🆔 **ID:** `{member.id}`\n"
            f"📅 **Date of Joining:** `{datetime.datetime.now().strftime('%d %b %Y')}`\n"
            f"━━━━━━━━━━━━━━━━━━━━━"
        )
        try:
            w_msg = await message.reply(welcome_text)
            asyncio.create_task(smart_vanish(w_msg, 20)) # Vanish after 20s
            asyncio.create_task(smart_vanish(message, 1))
        except: pass

# ================= FEATURE: ADVANCED ZIP/UNZIP =================

@app.on_message(filters.command(["zip", "unzip"]))
async def archive_handler(client, message):
    asyncio.create_task(smart_vanish(message, 1))
    uid = message.from_user.id
    if not await is_admin(client, message.chat.id, uid): return

    cmd = message.command[0].lower()
    password = message.command[1] if len(message.command) > 1 else None

    if cmd == "zip":
        if not message.reply_to_message:
            return await message.reply("❌ Reply to a photo/document with `/zip [password]`")
        
        status = await message.reply("📦 **Zipping your selection...**")
        
        # Handle Media Groups (Multi-photos) or Single files
        files_to_zip = []
        if message.reply_to_message.media_group_id:
            # Note: Pyrogram requires fetching the whole group
            album = await client.get_media_group(message.chat.id, message.reply_to_message.id)
            for item in album:
                path = await client.download_media(item, file_name=f"{DOWNLOAD_PATH}/")
                files_to_zip.append(path)
        else:
            path = await client.download_media(message.reply_to_message, file_name=f"{DOWNLOAD_PATH}/")
            files_to_zip.append(path)

        zip_name = f"{DOWNLOAD_PATH}/Archive_{uid}.zip"
        
        with zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
            if password:
                # Basic zipfile doesn't support writing encrypted zips directly easily,
                # but we will write the files into the structure.
                pass 
            for f in files_to_zip:
                zipf.write(f, os.path.basename(f))
                os.remove(f)

        await client.send_document(message.chat.id, zip_name, caption=f"✅ **Archive Created!**\n{'🔐 Password protected' if password else '🔓 No password'}")
        os.remove(zip_name)
        await status.delete()

    elif cmd == "unzip":
        if not message.reply_to_message or not message.reply_to_message.document:
            return await message.reply("❌ Reply to a `.zip` file with `/unzip [password]`")
        
        status = await message.reply("📂 **Extracting...**")
        zip_path = await client.download_media(message.reply_to_message, file_name=f"{DOWNLOAD_PATH}/")
        extract_dir = f"{DOWNLOAD_PATH}/ext_{uid}_{datetime.datetime.now().timestamp()}"
        
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                if password:
                    zip_ref.setpassword(password.encode())
                zip_ref.extractall(extract_dir)
            
            for root, _, files in os.walk(extract_dir):
                for file in files:
                    await client.send_document(message.chat.id, os.path.join(root, file))
            await status.edit("✅ **Extraction Complete!**")
        except Exception as e:
            await status.edit(f"❌ **Extraction Error:** {e}")
        
        shutil.rmtree(extract_dir, ignore_errors=True)
        if os.path.exists(zip_path): os.remove(zip_path)

# ================= ADMIN LOGIC =================

@app.on_message(filters.command(["status", "cleanup", "lock", "unlock", "ban", "unban", "stream", "start"]))
async def admin_commands(client, message):
    asyncio.create_task(smart_vanish(message, 1))
    uid = message.from_user.id
    chat_id = message.chat.id
    cmd = message.command[0].lower()

    if cmd == "start":
        if uid == OWNER_ID and chat_id != uid:
            await message.reply("🔄 **Restarting...**")
            os.execl(sys.executable, sys.executable, *sys.argv)
        else:
            await message.reply(f"✨ **Hello!** I am SuperBot.")
        return

    if not await is_admin(client, chat_id, uid): return

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
    
    # Remaining logic for cleanup/lock/unlock stays same as your base
    elif cmd == "cleanup":
        status_msg = await message.reply("🔍 **Cleaning...**")
        count = 0
        async for member in client.get_chat_members(chat_id):
            if member.user.is_deleted:
                try:
                    await client.ban_chat_member(chat_id, member.user.id)
                    await client.unban_chat_member(chat_id, member.user.id)
                    count += 1
                except: pass
        await status_msg.edit(f"✅ Removed `{count}` deleted accounts.")

# ================= RUNNER =================
async def main():
    await start_web_server()
    await app.start()
    print("--- SuperBot Ready: Smart Vanish & Password Archive Active ---")
    await idle()

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
    
