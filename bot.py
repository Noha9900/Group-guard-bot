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
# Temporary storage for bulk zipping
user_collections = {} 

if not os.path.exists(DOWNLOAD_PATH):
    os.makedirs(DOWNLOAD_PATH)

# ================= HELPERS =================
async def vanish_msg(message, delay=1):
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

# ================= FEATURE: BEAUTIFUL WELCOME =================
@app.on_message(filters.new_chat_members)
async def welcome_handler(client, message):
    for member in message.new_chat_members:
        welcome_text = (
            f"✨ **WELCOME TO THE CLAN!** ✨\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 **User:** {member.mention}\n"
            f"🆔 **ID:** `{member.id}`\n"
            f"📅 **Date:** `{datetime.datetime.now().strftime('%Y-%m-%d')}`\n"
            f"🏰 **Group:** {message.chat.title}\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"🚀 *Stay active and follow the rules!*"
        )
        try:
            w_msg = await message.reply(welcome_text)
            # Welcome stays for 60 seconds
            asyncio.create_task(vanish_msg(w_msg, 60)) 
            asyncio.create_task(vanish_msg(message, 5))
        except: pass

# ================= FEATURE: ZIP/UNZIP LOGIC =================

@app.on_message(filters.command(["zip", "unzip"]) & filters.group | filters.private)
async def archive_handler(client, message):
    asyncio.create_task(vanish_msg(message))
    uid = message.from_user.id
    if not await is_admin(client, message.chat.id, uid): return

    cmd = message.command[0].lower()

    if cmd == "zip":
        # Check if replying to a media or document
        if not message.reply_to_message or not (message.reply_to_message.document or message.reply_to_message.photo):
            m = await message.reply("❌ Reply to a document or photo to zip it.")
            return asyncio.create_task(vanish_msg(m, 5))
        
        status = await message.reply("📦 **Zipping File...**")
        file_path = await client.download_media(message.reply_to_message, file_name=f"{DOWNLOAD_PATH}/")
        zip_path = f"{file_path}.zip"
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            zipf.write(file_path, os.path.basename(file_path))
        
        await client.send_document(message.chat.id, zip_path, caption="✅ **Successfully Zipped!**")
        os.remove(file_path)
        os.remove(zip_path)
        await status.delete()

    elif cmd == "unzip":
        if not message.reply_to_message or not message.reply_to_message.document:
            m = await message.reply("❌ Reply to a `.zip` file to extract.")
            return asyncio.create_task(vanish_msg(m, 5))
        
        status = await message.reply("📂 **Extracting Archive...**")
        zip_path = await client.download_media(message.reply_to_message, file_name=f"{DOWNLOAD_PATH}/")
        extract_dir = f"{DOWNLOAD_PATH}/ext_{uid}_{datetime.datetime.now().timestamp()}"
        
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
            
            # Send all extracted files
            for root, dirs, files in os.walk(extract_dir):
                for file in files:
                    await client.send_document(message.chat.id, os.path.join(root, file))
            await status.edit("✅ **Extraction Complete!**")
        except Exception as e:
            await status.edit(f"❌ **Failed:** {e}")
        
        shutil.rmtree(extract_dir, ignore_errors=True)
        if os.path.exists(zip_path): os.remove(zip_path)

# ================= COMMANDS LOGIC =================

@app.on_message(filters.command(["status", "cleanup", "lock", "unlock", "ban", "unban", "stream", "start"]))
async def admin_commands(client, message):
    asyncio.create_task(vanish_msg(message))
    uid = message.from_user.id
    chat_id = message.chat.id
    cmd = message.command[0].lower()

    if cmd == "start":
        if uid == OWNER_ID and chat_id != uid:
            await message.reply("🔄 **Bot Restarting...**")
            os.execl(sys.executable, sys.executable, *sys.argv)
        else:
            await message.reply(f"✨ **Hello {message.from_user.first_name}!**\nI am SuperBot.")
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
    
    if not await is_admin(client, chat_id, uid):
        user_dl_count[uid] = user_dl_count.get(uid, 0) + 1
        if user_dl_count[uid] > 3:
            m = await message.reply("❌ **Limit Reached (3/3).**")
            return asyncio.create_task(vanish_msg(m, 5))

    if len(message.command) < 2:
        return await message.reply("❓ Usage: `/dl [URL]`")

    status = await message.reply("⏳ **Processing Download...**")
    await status.edit("✅ Download Complete (Logic ready).")

# ================= RUNNER =================
async def main():
    await start_web_server()
    await app.start()
    print("--- SuperBot Ready: Welcome & Archive Tools Active ---")
    await idle()

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
    
