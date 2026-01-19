import os
import sys
import asyncio
import datetime
import yt_dlp
import zipfile
from aiohttp import web
from pyrogram import Client, filters, idle, enums
from pyrogram.types import Message

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

# Initialize Client
app = Client("SuperBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

user_warnings = {}
locked_groups = []

if not os.path.exists(DOWNLOAD_PATH):
    os.makedirs(DOWNLOAD_PATH)

# ================= HELPER FUNCTIONS =================
async def vanish_msg(message, delay=0):
    """Safely delete messages after a delay"""
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

# ================= FEATURE: ATTRACTIVE WELCOME =================
@app.on_message(filters.new_chat_members)
async def welcome_handler(client, message):
    chat_title = message.chat.title
    asyncio.create_task(vanish_msg(message, 5))
    
    for member in message.new_chat_members:
        # Detailed and Attractive Group Welcome
        welcome_text = (
            f"✨ **NEW ADVENTURER JOINED!** ✨\n\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"👤 **User:** {member.mention}\n"
            f"🆔 **ID:** `{member.id}`\n"
            f"🏰 **Welcome to:** {chat_title}\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"🚀 *Enjoy your stay and stay active!*"
        )
        try:
            welcome_msg = await message.reply(welcome_text)
            asyncio.create_task(vanish_msg(welcome_msg, WELCOME_DELAY))
        except:
            pass

        # Detailed Private DM
        try:
            dm_text = (
                f"👋 **Hello {member.first_name}!**\n"
                f"Thank you for joining **{chat_title}**.\n\n"
                f"🎁 **Here is your exclusive Group Link:**\n👉 {GROUP_LINK}"
            )
            await client.send_message(member.id, dm_text, disable_web_page_preview=True)
        except:
            pass

# ================= FEATURE: STREAMABLE LINKS =================
@app.on_message(filters.command("stream") & filters.user(OWNER_ID))
async def stream_handler(client, message):
    await vanish_msg(message)
    status = await message.reply("🔄 **Generating Stream Link...**")
    
    # Handle Video/File uploads
    if message.reply_to_message and (message.reply_to_message.video or message.reply_to_message.document):
        await status.edit("⏳ **Downloading to server for streaming...**")
        file_path = await client.download_media(message.reply_to_message, file_name=f"{DOWNLOAD_PATH}/")
        filename = os.path.basename(file_path)
        stream_link = f"{BASE_URL}/watch/{filename}"
        
        await status.edit(
            f"🎬 **Stream Ready!**\n\n"
            f"📂 **File:** `{filename}`\n"
            f"📺 **Direct Link:** [Click Here to Stream]({stream_link})",
            disable_web_page_preview=True
        )
    # Handle External URLs
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
                await status.edit(f"✅ **External Stream Ready!**\n\n🔗 [Direct Stream Link]({direct})")
            else:
                await status.edit("❌ Failed to extract streamable link.")
        except Exception as e:
            await status.edit(f"❌ Error: {e}")
    else:
        await status.edit("❌ Please reply to a video or provide a URL.")
        asyncio.create_task(vanish_msg(status, 5))

# ================= FEATURE: ZIP & UNZIP =================
@app.on_message(filters.command("zip") & filters.user(OWNER_ID))
async def zip_cmd(client, message):
    await vanish_msg(message)
    if not message.reply_to_message:
        return await message.reply("Reply to a file to zip.")
    
    status = await message.reply("📦 **Creating Zip Archive...**")
    file = await client.download_media(message.reply_to_message, file_name=f"{DOWNLOAD_PATH}/")
    zip_name = f"{file}.zip"
    
    with zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
        zipf.write(file, os.path.basename(file))
    
    await client.send_document(message.chat.id, zip_name, caption="✅ Successfully Zipped.")
    os.remove(file)
    os.remove(zip_name)
    await status.delete()

@app.on_message(filters.command("unzip") & filters.user(OWNER_ID))
async def unzip_cmd(client, message):
    await vanish_msg(message)
    if not message.reply_to_message or not message.reply_to_message.document:
        return await message.reply("Reply to a `.zip` file to extract.")
    
    password = message.text.split(None, 1)[1] if len(message.command) > 1 else None
    status = await message.reply("📂 **Extracting Archive...**")
    
    zip_path = await client.download_media(message.reply_to_message, file_name=f"{DOWNLOAD_PATH}/")
    extract_dir = f"{DOWNLOAD_PATH}/ext_{datetime.datetime.now().timestamp()}"
    
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            if password:
                zip_ref.setpassword(password.encode())
            zip_ref.extractall(extract_dir)
        
        # Upload extracted files
        for root, _, files in os.walk(extract_dir):
            for f in files:
                await client.send_document(message.chat.id, os.path.join(root, f))
        await status.edit("✅ Extraction Complete!")
    except Exception as e:
        await status.edit(f"❌ Extraction failed: {e}")
    
    if os.path.exists(zip_path):
        os.remove(zip_path)

# ================= MODERATION & SECURITY =================
@app.on_message(filters.group & ~filters.user(OWNER_ID), group=1)
async def security_logic(client, message):
    if message.chat.id in locked_groups:
        await vanish_msg(message)
        message.stop_propagation()

@app.on_message(filters.group & (filters.text | filters.caption), group=2)
async def anti_link_logic(client, message):
    if message.from_user.id == OWNER_ID: return
    entities = (message.entities or []) + (message.caption_entities or [])
    if any(e.type in [enums.MessageEntityType.URL, enums.MessageEntityType.TEXT_LINK] for e in entities):
        await message.delete()
        w = await message.reply(f"🚫 {message.from_user.mention}, Links are not allowed!")
        asyncio.create_task(vanish_msg(w, 5))

# ================= SYSTEM HANDLERS =================
@app.on_message(filters.command("start"))
async def start_handler(client, message):
    if message.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP] and message.from_user.id == OWNER_ID:
        await vanish_msg(message)
        status = await message.reply("🔄 **Restarting System...**")
        await asyncio.sleep(2)
        os.execl(sys.executable, sys.executable, *sys.argv)
    else:
        await message.reply(f"✨ **Hello {message.from_user.first_name}!**\nI am SuperBot.")

# ================= RUNNER =================
async def main():
    await start_web_server()
    await app.start()
    print("--- Bot Started Successfully ---")
    await idle()
    await app.stop()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
    
