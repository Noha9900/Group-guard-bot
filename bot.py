import os
import asyncio
import yt_dlp
from aiohttp import web
from pyrogram import Client, filters, idle, enums
from pyrogram.types import Message
from pytgcalls import PyTgCalls
from pytgcalls.types import Update
from pytgcalls.types.input_stream import VideoPiped, AudioPiped

# ================= CONFIGURATION =================
API_ID = 36982189  # Your API ID
API_HASH = "d3ec5feee7342b692e7b5370fb9c8db7"
BOT_TOKEN = "8544773286:AAHkDc5awfunKMaO-407F7JtcmrY1OmazRc"
OWNER_ID = 8072674531  # Your User ID

# NEW: Link to send privately to subscribers
GROUP_LINK = "https://t.me/+AbCdEfGhIjK12345" 

# NEW: Your App's Public URL (Required for stream links to work)
# Example: "https://my-bot-app.onrender.com"
BASE_URL = os.environ.get("BASE_URL", "http://0.0.0.0:8080") 

BAD_WORDS = ["badword1", "racist", "scam", "cheat"]
WARNING_LIMIT = 3
WELCOME_DELAY = 20
DOWNLOAD_PATH = "./downloads"
PORT = int(os.environ.get("PORT", 8080))

# Initialize Clients
app = Client("SuperBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
call_py = PyTgCalls(app)

user_warnings = {}
locked_groups = []

if not os.path.exists(DOWNLOAD_PATH):
    os.makedirs(DOWNLOAD_PATH)

# ================= WEB SERVER =================
async def health_check(request):
    return web.Response(text="Bot is Alive!", status=200)

async def start_web_server():
    server = web.Application()
    server.add_routes([
        web.get('/', health_check),
        # NEW: Route to serve downloaded files for streaming
        web.static('/watch', DOWNLOAD_PATH)
    ])
    runner = web.AppRunner(server)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    print(f"--- Web Server running on Port {PORT} ---")

# ================= FEATURE 1: WELCOME & SUBSCRIPTION =================

# 1. Private Chat Welcome (Start Command)
@app.on_message(filters.command("start") & filters.private)
async def start_private(client, message):
    user = message.from_user
    text = (
        f"✨ **Hello, {user.mention}!** ✨\n\n"
        "🤖 **I am SuperBot**\n"
        "I am fully operational and ready to serve you.\n\n"
        "📌 **My Systems:**\n"
        "🔹 Channel & Group Management\n"
        "🔹 Media Downloader\n"
        "🔹 Streaming\n\n"
        f"🔗 **Join our Official Group here:**\n{GROUP_LINK}"
    )
    await message.reply(text, disable_web_page_preview=True)

# 2. Universal Welcome (Groups AND Channels)
@app.on_message(filters.new_chat_members)
async def welcome_handler(client, message):
    chat_id = message.chat.id
    chat_title = message.chat.title
    
    for member in message.new_chat_members:
        # A. Public Welcome
        if message.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
            welcome_text = (
                f"✨ **Welcome, {member.mention}!** ✨\n\n"
                f"🌟 Thrilled to have you in **{chat_title}**!\n"
                "──────────────────────"
            )
            try:
                welcome_msg = await message.reply(welcome_text)
                await asyncio.sleep(WELCOME_DELAY)
                await welcome_msg.delete()
            except:
                pass

        # B. Private DM with Group Link
        try:
            dm_text = (
                f"👋 **Hello {member.mention}!**\n\n"
                f"Thank you for joining **{chat_title}**.\n\n"
                f"🎁 **Here is the exclusive Group Link you need:**\n"
                f"👉 {GROUP_LINK}\n\n"
                "*(I sent this because you subscribed to our channel/group)*"
            )
            await client.send_message(member.id, dm_text, disable_web_page_preview=True)
        except Exception as e:
            print(f"Could not DM user {member.id}: {e}")

@app.on_message(filters.command("clean_ghosts") & filters.user(OWNER_ID))
async def remove_deleted_users(client, message):
    chat_id = message.chat.id
    status_msg = await message.reply("Scanning for deleted accounts...")
    count = 0
    async for member in client.get_chat_members(chat_id):
        if member.user.is_deleted:
            try:
                await client.ban_chat_member(chat_id, member.user.id)
                count += 1
            except Exception:
                pass
    await status_msg.edit(f"✅ Removed {count} deleted accounts.")

# ================= FEATURE 2: MODERATION (Groups Only) =================
@app.on_message(filters.group & filters.text & ~filters.user(OWNER_ID))
async def moderation_handler(client, message):
    if message.sender_chat:
        return

    text = message.text.lower()
    user_id = message.from_user.id
    chat_id = message.chat.id

    if chat_id in locked_groups:
        await message.delete()
        return

    if any(word in text for word in BAD_WORDS):
        if user_id not in user_warnings:
            user_warnings[user_id] = 0
        user_warnings[user_id] += 1
        current_warns = user_warnings[user_id]

        try:
            await message.delete()
        except:
            pass

        if current_warns >= WARNING_LIMIT:
            try:
                await client.ban_chat_member(chat_id, user_id)
                await message.reply(f"🚫 {message.from_user.mention} banned for exceeding warnings.")
                user_warnings[user_id] = 0
            except:
                pass
        else:
            await message.reply(f"⚠️ {message.from_user.mention}, watch your language! Warning {current_warns}/{WARNING_LIMIT}")

@app.on_message(filters.command("lock") & filters.user(OWNER_ID))
async def lock_group(client, message):
    if message.chat.id not in locked_groups:
        locked_groups.append(message.chat.id)
        await message.reply("🔒 Group is now LOCKED. Non-admins cannot speak.")
    else:
        await message.reply("Group is already locked.")

@app.on_message(filters.command("unlock") & filters.user(OWNER_ID))
async def unlock_group(client, message):
    if message.chat.id in locked_groups:
        locked_groups.remove(message.chat.id)
        await message.reply("🔓 Group UNLOCKED.")

# ================= FEATURE 3: DOWNLOADING =================
@app.on_message(filters.command("dl") & filters.user(OWNER_ID))
async def downloader(client, message):
    if len(message.command) < 2:
        return await message.reply("Please provide a link! Usage: `/dl https://...`")
    url = message.text.split(None, 1)[1]
    status_msg = await message.reply("⚡ Downloading...")

    ydl_opts = {
        'outtmpl': f'{DOWNLOAD_PATH}/%(title)s.%(ext)s',
        'format': 'bestvideo+bestaudio/best',
        'noplaylist': True,
        'quiet': True,
        'geo_bypass': True,
        'nocheckcertificate': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

        if not os.path.exists(filename):
            base_name = os.path.splitext(filename)[0]
            for ext in ['.mp4', '.mkv', '.webm']:
                if os.path.exists(base_name + ext):
                    filename = base_name + ext
                    break

        await status_msg.edit("⬆️ Uploading to Telegram...")
        await client.send_document(message.chat.id, document=filename, caption=f"Downloaded from: {url}")
        os.remove(filename)
        await status_msg.delete()
    except Exception as e:
        await status_msg.edit(f"❌ Error: {str(e)}")

# ================= FEATURE 4: POST CREATOR =================
@app.on_message(filters.command("broadcast") & filters.user(OWNER_ID))
async def broadcast_post(client, message):
    if not message.reply_to_message:
        return await message.reply("Reply to a message to broadcast it.")
    await message.reply_to_message.copy(message.chat.id)
    await message.reply("✅ Post broadcasted successfully.")

# ================= FEATURE 5: STREAMABLE LINKS =================
@app.on_message(filters.command("stream") & filters.user(OWNER_ID))
async def stream_handler(client, message):
    # Check if user replied to media
    if not message.reply_to_message:
        return await message.reply("Please reply to a video or file to generate a stream link.")
    
    media = message.reply_to_message.video or message.reply_to_message.document or message.reply_to_message.audio
    if not media:
        return await message.reply("❌ No valid media found in replied message.")

    status = await message.reply("📥 Downloading media to server...")
    
    try:
        # Download the file
        file_path = await message.reply_to_message.download(file_name=f"{DOWNLOAD_PATH}/")
        file_name = os.path.basename(file_path)
        
        # Generate the Stream Link
        # Uses the BASE_URL defined at the top
        stream_link = f"{BASE_URL}/watch/{file_name}"
        
        await status.edit(
            f"✅ **Stream Link Generated!**\n\n"
            f"🔗 **Link:** {stream_link}\n\n"
            f"⚠️ *Link expires in 30 minutes.*"
        )
        
        # Auto-delete file after 30 minutes to save server space
        await asyncio.sleep(1800)
        if os.path.exists(file_path):
            os.remove(file_path)
            
    except Exception as e:
        await status.edit(f"❌ Error: {e}")

# ================= RUNNER =================
async def main():
    print("--- Starting SuperBot 24/7 ---")
    await start_web_server()
    await app.start()
    await call_py.start()
    print("--- Bot is Online ---")
    await idle()
    await app.stop()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main()) 
