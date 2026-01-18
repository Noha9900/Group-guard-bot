import os
import asyncio
import yt_dlp
from aiohttp import web
from pyrogram import Client, filters, idle
from pyrogram.types import Message
# SWITCHING BACK TO STABLE IMPORTS
from pytgcalls import PyTgCalls
from pytgcalls.types import Update
from pytgcalls.types.input_stream import VideoPiped, AudioPiped

# ================= CONFIGURATION =================
API_ID = 12345678  # Your API ID
API_HASH = "your_api_hash_here"
BOT_TOKEN = "your_bot_token_here"
OWNER_ID = 123456789  # Your User ID

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
    server.add_routes([web.get('/', health_check)])
    runner = web.AppRunner(server)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    print(f"--- Web Server running on Port {PORT} ---")

# ================= FEATURE 1: GROUP MANAGEMENT =================
@app.on_message(filters.new_chat_members)
async def welcome_handler(client, message):
    for member in message.new_chat_members:
        welcome_msg = await message.reply(f"Welcome {member.mention} to the group! 🌟")
        await asyncio.sleep(WELCOME_DELAY)
        try:
            await welcome_msg.delete()
            await message.delete()
        except Exception:
            pass

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

@app.on_message(filters.command("stats") & filters.user(OWNER_ID))
async def count_users(client, message):
    total = await client.get_chat_members_count(message.chat.id)
    await message.reply(f"📊 Total Members: {total}")

# ================= FEATURE 2: MODERATION =================
@app.on_message(filters.group & filters.text & ~filters.user(OWNER_ID))
async def moderation_handler(client, message):
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
                await message.reply("⚠️ user exceeded warnings but I lack permission to ban.")
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

# ================= FEATURE 5: STREAMING (STABLE v1.2.0) =================
@app.on_message(filters.command("stream") & filters.user(OWNER_ID))
async def stream_handler(client, message):
    if not message.reply_to_message or not message.reply_to_message.video:
        return await message.reply("Please reply to a video file to stream it!")

    status = await message.reply("📥 Downloading media for stream...")
    file_path = await message.reply_to_message.download(file_name=DOWNLOAD_PATH + "/")
    await status.edit("▶️ Starting Stream...")

    try:
        # Using VideoPiped (Stable v1.2.0 method)
        await call_py.join_group_call(
            message.chat.id,
            VideoPiped(file_path)
        )
    except Exception as e:
        await status.edit(f"Error joining call: {e}")

# ================= RUNNER =================
async def main():
    print("--- Starting PowerBot 24/7 ---")
    await start_web_server()
    await app.start()
    await call_py.start()
    print("--- Bot is Online ---")
    await idle()
    await app.stop()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
