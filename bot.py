import os
import sys
import asyncio
import datetime
import yt_dlp
import zipfile
import pyptlib.util
from aiohttp import web
from pyrogram import Client, filters, idle, enums
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pytgcalls import PyTgCalls

# ================= CONFIGURATION =================
API_ID = 36982189
API_HASH = "d3ec5feee7342b692e7b5370fb9c8db7"
BOT_TOKEN = "8544773286:AAHkDc5awfunKMaO-407F7JtcmrY1OmazRc"
OWNER_ID = 8072674531
GROUP_LINK = "https://t.me/+AbCdEfGhIjK12345"
# Ensure BASE_URL does not end with /
BASE_URL = os.environ.get("BASE_URL", "http://0.0.0.0:8080").rstrip('/')
DOWNLOAD_PATH = "./downloads"
PORT = int(os.environ.get("PORT", 8080))

app = Client("SuperBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
call_py = PyTgCalls(app)

user_warnings = {}
locked_groups = []

if not os.path.exists(DOWNLOAD_PATH):
    os.makedirs(DOWNLOAD_PATH)

# ================= HELPER FUNCTIONS =================
async def vanish_msg(message, delay=0):
    if delay > 0: await asyncio.sleep(delay)
    try: await message.delete()
    except: pass

# ================= WEB SERVER =================
async def health_check(request):
    return web.Response(text="Bot is Alive!", status=200)

async def start_web_server():
    server = web.Application()
    server.add_routes([
        web.get('/', health_check),
        web.static('/watch', DOWNLOAD_PATH) # Files accessible at BASE_URL/watch/filename
    ])
    runner = web.AppRunner(server)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()

# ================= FIXED: ATTRACTIVE WELCOME =================
@app.on_message(filters.new_chat_members)
async def welcome_handler(client, message):
    chat_title = message.chat.title
    asyncio.create_task(vanish_msg(message, 5)) 
    
    for member in message.new_chat_members:
        # Attractive Group Welcome
        welcome_text = (
            f"✨ **NEW ADVENTURER JOINED!** ✨\n\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"👋 **Welcome:** {member.mention}\n"
            f"🆔 **ID:** `{member.id}`\n"
            f"🏰 **Group:** {chat_title}\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"🚀 *Enjoy your stay and stay active!*"
        )
        try:
            welcome_msg = await message.reply(welcome_text)
            asyncio.create_task(vanish_msg(welcome_msg, 60))
        except: pass

        # Private DM
        try:
            await client.send_message(
                member.id, 
                f"🌟 **Welcome to the Family, {member.first_name}!**\n\n"
                f"You've joined **{chat_title}**. We are glad to have you here.\n"
                f"🔗 **Main Hub:** {GROUP_LINK}",
                disable_web_page_preview=True
            )
        except: pass

# ================= FIXED: STREAM COMMAND (FILES & LINKS) =================
@app.on_message(filters.command("stream") & filters.user(OWNER_ID))
async def stream_handler(client, message):
    await vanish_msg(message)
    status = await message.reply("📡 **Processing Stream Link...**")

    # If replying to a video/file
    if message.reply_to_message and (message.reply_to_message.video or message.reply_to_message.document):
        media = message.reply_to_message.video or message.reply_to_message.document
        await status.edit("⏳ **Downloading to Server...**")
        file_path = await client.download_media(message.reply_to_message, file_name=f"{DOWNLOAD_PATH}/")
        filename = os.path.basename(file_path)
        
        # Create a direct stream link using your web server
        stream_link = f"{BASE_URL}/watch/{filename}"
        await status.edit(
            f"🎬 **File Stream Ready!**\n\n"
            f"📂 **Name:** `{filename}`\n"
            f"🔗 **Stream Link:** [Watch/Download]({stream_link})",
            disable_web_page_preview=True
        )
    
    # If it's a YouTube/External link
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
                await status.edit(f"✅ **External Stream Ready!**\n\n🔗 [Click to Play Stream]({direct})")
            else:
                await status.edit("❌ Failed to extract stream.")
        except Exception as e:
            await status.edit(f"❌ Error: {e}")
    else:
        await status.edit("❌ Reply to a video or provide a link!")
        asyncio.create_task(vanish_msg(status, 5))

# ================= NEW FEATURE: ZIP & UNZIP =================
@app.on_message(filters.command("zip") & filters.user(OWNER_ID))
async def zip_cmd(client, message):
    await vanish_msg(message)
    if not message.reply_to_message:
        return await message.reply("Reply to a file to zip it.")
    
    status = await message.reply("📦 **Zipping...**")
    file = await client.download_media(message.reply_to_message, file_name=f"{DOWNLOAD_PATH}/")
    zip_name = f"{file}.zip"
    
    with zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
        zipf.write(file, os.path.basename(file))
    
    await client.send_document(message.chat.id, zip_name, caption="✅ Compressed successfully.")
    os.remove(file)
    os.remove(zip_name)
    await status.delete()

@app.on_message(filters.command("unzip") & filters.user(OWNER_ID))
async def unzip_cmd(client, message):
    await vanish_msg(message)
    if not message.reply_to_message or not message.reply_to_message.document:
        return await message.reply("Reply to a `.zip` file.")
    
    password = message.text.split(None, 1)[1] if len(message.command) > 1 else None
    status = await message.reply("📂 **Extracting...**")
    
    zip_path = await client.download_media(message.reply_to_message, file_name=f"{DOWNLOAD_PATH}/")
    extract_dir = f"{DOWNLOAD_PATH}/extracted_{datetime.datetime.now().timestamp()}"
    
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            if password:
                zip_ref.setpassword(password.encode())
            zip_ref.extractall(extract_dir)
        
        for root, dirs, files in os.walk(extract_dir):
            for f in files:
                await client.send_document(message.chat.id, os.path.join(root, f))
        await status.edit("✅ Extracted and Sent!")
    except Exception as e:
        await status.edit(f"❌ Extraction failed: {e}")
    
    # Cleanup
    if os.path.exists(zip_path): os.remove(zip_path)

# (Keep all your existing Anti-link, Ban, Start handlers here...)

# ================= RUNNER =================
async def main():
    print("--- Starting SuperBot 24/7 ---")
    await start_web_server()
    await app.start()
    print("--- Bot is Online ---")
    await idle()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
    
