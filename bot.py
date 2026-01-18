import os
import asyncio
import yt_dlp
from pyrogram import Client, filters, idle
from pyrogram.types import Message
from pytgcalls import PyTgCalls
from pytgcalls.types import MediaStream

# ================= CONFIGURATION =================
# Replace these with your actual values
API_ID = 12345678  # Your API ID
API_HASH = "your_api_hash_here"
BOT_TOKEN = "your_bot_token_here"
OWNER_ID = 123456789 # Your Telegram User ID (for admin commands)

# Settings
BAD_WORDS = ["badword1", "racist", "scam", "cheat"]
WARNING_LIMIT = 3
WELCOME_DELAY = 20  # Seconds
DOWNLOAD_PATH = "./downloads"

# Initialize Clients
app = Client("SuperBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
call_py = PyTgCalls(app)

# In-memory database (for warnings/locks)
user_warnings = {}
locked_groups = []

# Ensure download directory exists
if not os.path.exists(DOWNLOAD_PATH):
    os.makedirs(DOWNLOAD_PATH)

# ================= FEATURE 1: GROUP MANAGEMENT =================

@app.on_message(filters.new_chat_members)
async def welcome_handler(client, message):
    """Welcomes new members and auto-cleans the message."""
    for member in message.new_chat_members:
        # Send Welcome
        welcome_msg = await message.reply(f"Welcome {member.mention} to the group! 🌟")
        
        # Wait and Clean up
        await asyncio.sleep(WELCOME_DELAY)
        try:
            await welcome_msg.delete()  # Delete bot's welcome
            await message.delete()      # Feature 5: Delete the "User Joined" tag
        except Exception:
            pass

@app.on_message(filters.command("clean_ghosts") & filters.user(OWNER_ID))
async def remove_deleted_users(client, message):
    """Feature 2: Remove deleted accounts."""
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
    """Feature 7: Count active users."""
    total = await client.get_chat_members_count(message.chat.id)
    await message.reply(f"📊 Total Members: {total}")

# ================= FEATURE 2: MODERATION & LOCKING =================

@app.on_message(filters.group & filters.text & ~filters.user(OWNER_ID))
async def moderation_handler(client, message):
    """Feature 3: Bad words monitor."""
    text = message.text.lower()
    user_id = message.from_user.id
    chat_id = message.chat.id

    # 1. Check if Group is Locked (Feature 4)
    if chat_id in locked_groups:
        # In a real bot, you'd check a database for "authorized" users
        await message.delete()
        return

    # 2. Check for Bad Words
    if any(word in text for word in BAD_WORDS):
        # Initialize warning count if new
        if user_id not in user_warnings:
            user_warnings[user_id] = 0
        
        user_warnings[user_id] += 1
        current_warns = user_warnings[user_id]
        
        # Delete the bad message
        try:
            await message.delete()
        except:
            pass

        if current_warns >= WARNING_LIMIT:
            # Ban User
            try:
                await client.ban_chat_member(chat_id, user_id)
                await message.reply(f"🚫 {message.from_user.mention} banned for exceeding warnings.")
                user_warnings[user_id] = 0
            except:
                await message.reply("⚠️ user exceeded warnings but I lack permission to ban.")
        else:
            # Warn User
            await message.reply(f"⚠️ {message.from_user.mention}, watch your language! Warning {current_warns}/{WARNING_LIMIT}")

@app.on_message(filters.command("lock") & filters.user(OWNER_ID))
async def lock_group(client, message):
    """Feature 4: Locks the group."""
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
    """Feature 4: Hyper fast downloader using yt-dlp."""
    if len(message.command) < 2:
        return await message.reply("Please provide a link! Usage: `/dl https://...`")
    
    url = message.text.split(None, 1)[1]
    
    # Visual Feedback
    if url.endswith(".html") or url.endswith(".htm"):
        status_msg = await message.reply("🔎 Analyzing HTML page for video content...")
    else:
        status_msg = await message.reply("⚡ Downloading...")
    
    # Configure yt-dlp
    ydl_opts = {
        'outtmpl': f'{DOWNLOAD_PATH}/%(title)s.%(ext)s',
        'format': 'bestvideo+bestaudio/best', 
        'noplaylist': True,
        'quiet': True,
        'geo_bypass': True,
        'nocheckcertificate': True,
    }
    
    try:
        # Download
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
        
        # Fallback check if extension changed
        if not os.path.exists(filename):
            base_name = os.path.splitext(filename)[0]
            for ext in ['.mp4', '.mkv', '.webm']:
                if os.path.exists(base_name + ext):
                    filename = base_name + ext
                    break
        
        # Upload
        await status_msg.edit("⬆️ Uploading to Telegram...")
        await client.send_document(message.chat.id, document=filename, caption=f"Downloaded from: {url}")
        
        # Cleanup
        os.remove(filename)
        await status_msg.delete()
        
    except Exception as e:
        await status_msg.edit(f"❌ Error: {str(e)}")

# ================= FEATURE 4: POST CREATOR =================

@app.on_message(filters.command("broadcast") & filters.user(OWNER_ID))
async def broadcast_post(client, message):
    """Creates a post from a reply."""
    if not message.reply_to_message:
        return await message.reply("Reply to a message to broadcast it.")
    
    # This copies the message (text/media/buttons) and sends it back
    await message.reply_to_message.copy(message.chat.id)
    await message.reply("✅ Post broadcasted successfully.")

# ================= FEATURE 5: STREAMING (Fixed for PyTgCalls v2) =================

@app.on_message(filters.command("stream") & filters.user(OWNER_ID))
async def stream_handler(client, message):
    """Streams video/audio to the group call."""
    if not message.reply_to_message or not message.reply_to_message.video:
        return await message.reply("Please reply to a video file to stream it!")

    status = await message.reply("📥 Downloading media for stream...")
    
    # Download the file
    file_path = await message.reply_to_message.download(file_name=DOWNLOAD_PATH + "/")
    
    await status.edit("▶️ Starting Stream...")
    
    try:
        # NEW CODE for PyTgCalls v2.0+
        await call_py.play(
            message.chat.id,
            MediaStream(
                file_path,
                video_flags=MediaStream.Flags.IGNORE_ERRORS
            )
        )
    except Exception as e:
        await status.edit(f"Error joining call: {e}")

# ================= RUNNER =================

async def main():
    print("--- Starting PowerBot 24/7 ---")
    await app.start()
    await call_py.start()
    print("--- Bot is Online ---")
    await idle()
    await app.stop()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
