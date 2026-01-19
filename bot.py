import os
import sys
import asyncio
import datetime
import yt_dlp
import zipfile
from aiohttp import web
from pyrogram import Client, filters, idle, enums
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pytgcalls import PyTgCalls

# ================= CONFIGURATION =================
API_ID = 36982189
API_HASH = "d3ec5feee7342b692e7b5370fb9c8db7"
BOT_TOKEN = "8544773286:AAHkDc5awfunKMaO-407F7JtcmrY1OmazRc"
OWNER_ID = 8072674531

# Link to send privately to subscribers
GROUP_LINK = "https://t.me/+AbCdEfGhIjK12345"

# Your App's Public URL (Render URL)
BASE_URL = os.environ.get("BASE_URL", "http://0.0.0.0:8080").rstrip('/')

BAD_WORDS = ["badword1", "racist", "scam", "cheat"]
WARNING_LIMIT = 3
WELCOME_DELAY = 60
DOWNLOAD_PATH = "./downloads"
PORT = int(os.environ.get("PORT", 8080))

# Initialize Clients
app = Client("SuperBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
call_py = PyTgCalls(app)

user_warnings = {}
locked_groups = []

if not os.path.exists(DOWNLOAD_PATH):
    os.makedirs(DOWNLOAD_PATH)

# ================= HELPER FUNCTIONS =================
async def vanish_msg(message, delay=0):
    """Helper to delete messages safely"""
    if delay > 0:
        await asyncio.sleep(delay)
    try:
        await message.delete()
    except:
        pass

# ================= WEB SERVER =================
async def health_check(request):
    return web.Response(text="Bot is Alive!", status=200)

async def start_web_server():
    server = web.Application()
    server.add_routes([
        web.get('/', health_check),
        web.static('/watch', DOWNLOAD_PATH)
    ])
    runner = web.AppRunner(server)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    print(f"--- Web Server running on Port {PORT} ---")

# ================= FEATURE: SECURITY & LOCK =================
@app.on_message(filters.group & ~filters.user(OWNER_ID), group=1)
async def lock_check(client, message):
    if message.chat.id in locked_groups:
        await vanish_msg(message)
        message.stop_propagation()

@app.on_message(filters.group & (filters.text | filters.caption), group=2)
async def anti_link_check(client, message):
    has_link = False
    entities = (message.entities or []) + (message.caption_entities or [])
    for entity in entities:
        if entity.type in [enums.MessageEntityType.URL, enums.MessageEntityType.TEXT_LINK]:
            has_link = True
            break
    if has_link:
        if message.from_user.id == OWNER_ID: return
        await message.delete()
        warning = await message.reply(f"🚫 {message.from_user.mention}, **NO LINKS ALLOWED!**")
        asyncio.create_task(vanish_msg(warning, 5))
        message.stop_propagation()

# ================= FEATURE: ATTRACTIVE WELCOME =================
@app.on_message(filters.new_chat_members)
async def welcome_handler(client, message):
    chat_title = message.chat.title
    asyncio.create_task(vanish_msg(message, 5))
    
    for member in message.new_chat_members:
        # Detailed Group Welcome
        welcome_text = (
            f"✨ **NEW MEMBER ALERT!** ✨\n\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"👤 **User:** {member.mention}\n"
            f"🆔 **ID:** `{member.id}`\n"
            f"🏰 **Welcome to:** {chat_title}\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"🚀 *Enjoy your stay and check the rules!*"
        )
        try:
            welcome_msg = await message.reply(welcome_text)
            asyncio.create_task(vanish_msg(welcome_msg, WELCOME_DELAY))
        except: pass

        # Detailed Private DM
        try:
            dm_text = (
                f"👋 **Hello {member.first_name}!**\n"
                f"Thank you for joining **{chat_title}**.\n\n"
                f"🎁 **Exclusive Access Link:**\n👉 {GROUP_LINK}"
            )
            await client.send_message(member.id, dm_text, disable_web_page_preview=True)
        except: pass

# ================= FEATURE: STREAMABLE LINKS (FILES & URLS) =================
@app.on_message(filters.command("stream") & filters.user(OWNER_ID))
async def stream_handler(client, message):
    await vanish_msg(message)
    status = await message.reply("🔄 **Processing Stream...**")
    
    # Case 1: Reply to Video/File
    if message.reply_to_message and (message.reply_to_message.video or message.reply_to_message.document):
        await status.edit("⏳ **Downloading to Server...**")
        file_path = await client.download_media(message.reply_to_message, file_name=f"{DOWNLOAD_PATH}/")
        filename = os.path.basename(file_path)
        stream_link = f"{BASE_URL}/watch/{filename}"
        
        await status.edit(
            f"🎬 **Stream Generated!**\n\n"
            f"📂 **File:** `{filename}`\n"
            f"📺 **Link:** [Click to Watch/Stream]({stream_link})",
            disable_web_page_preview=True
        )
    # Case 2: External URL
    elif len(message.command) > 1 or (message.reply_to_message and message.reply_to_message.text):
        url = message.command[1] if len(message.command) > 1 else message.reply_to_message.text
        try:
            proc = await asyncio.create_subprocess_shell(
                f"yt-dlp --get-url -f best \"{url}\"",
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await proc.communicate()
            if stdout:
                direct = stdout.decode().strip()
                await status.edit(f"✅ **Stream Ready!**\n\n🔗 [Direct Link]({direct})")
            else:
                await status.edit("❌ Failed to extract URL.")
        except Exception as e:
            await status.edit(f"❌ Error: {e}")
    else:
        await status.edit("❌ Reply to a video or provide a link!")
        asyncio.create_task(vanish_msg(status, 5))

# ================= FEATURE: ZIP & UNZIP =================
@app.on_message(filters.command("zip") & filters.user(OWNER_ID))
async def zip_cmd(client, message):
    await vanish_msg(message)
    if not message.reply_to_message: return await message.reply("Reply to a file.")
    
    status = await message.reply("📦 **Zipping...**")
    file = await client.download_media(message.reply_to_message, file_name=f"{DOWNLOAD_PATH}/")
    zip_name = f"{file}.zip"
    
    with zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
        zipf.write(file, os.path.basename(file))
    
    await client.send_document(message.chat.id, zip_name, caption="✅ Zipped successfully.")
    os.remove(file)
    os.remove(zip_name)
    await status.delete()

@app.on_message(filters.command("unzip") & filters.user(OWNER_ID))
async def unzip_cmd(client, message):
    await vanish_msg(message)
    if not message.reply_to_message or not message.reply_to_message.document:
        return await message.reply("Reply to a `.zip` file.")
    
    password = message.text.split(None, 1)[1] if len(message.command) > 1 else None
    status = await message.reply("📂 **Unzipping...**")
    
    zip_path = await client.download_media(message.reply_to_message, file_name=f"{DOWNLOAD_PATH}/")
    extract_dir = f"{DOWNLOAD_PATH}/extracted_{datetime.datetime.now().timestamp()}"
    
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            if password: zip_ref.setpassword(password.encode())
            zip_ref.extractall(extract_dir)
        
        for root, _, files in os.walk(extract_dir):
            for f in files:
                await client.send_document(message.chat.id, os.path.join(root, f))
        await status.edit("✅ Files Extracted!")
    except Exception as e:
        await status.edit(f"❌ Error: {e}")
    
    if os.path.exists(zip_path): os.remove(zip_path)

# ================= SYSTEM COMMANDS (START/RESTART/BAN) =================
@app.on_message(filters.command("start"))
async def start_handler(client, message):
    if message.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP] and message.from_user.id == OWNER_ID:
        await vanish_msg(message)
        status = await message.reply("🔄 **System Restarting...**")
    
    
