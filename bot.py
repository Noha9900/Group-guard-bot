import os
import sys  # Added for Restart functionality
import asyncio
import datetime
import yt_dlp
from aiohttp import web
from pyrogram import Client, filters, idle, enums
from pyrogram.types import Message
from pytgcalls import PyTgCalls

# ================= CONFIGURATION =================
API_ID = 36982189
API_HASH = "d3ec5feee7342b692e7b5370fb9c8db7"
BOT_TOKEN = "8544773286:AAHkDc5awfunKMaO-407F7JtcmrY1OmazRc"
OWNER_ID = 8072674531

# Link to send privately to subscribers
GROUP_LINK = "https://t.me/+AbCdEfGhIjK12345"

# Your App's Public URL
BASE_URL = os.environ.get("BASE_URL", "http://0.0.0.0:8080")

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
    """Helper to delete messages (commands or status updates) safely"""
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

# ================= FEATURE: STRICT GROUP LOCK =================
@app.on_message(filters.group & ~filters.user(OWNER_ID), group=1)
async def lock_check(client, message):
    if message.chat.id in locked_groups:
        await vanish_msg(message)
        message.stop_propagation()

# ================= FEATURE: ANTI-LINK SYSTEM =================
@app.on_message(filters.group & (filters.text | filters.caption), group=2)
async def anti_link_check(client, message):
    has_link = False
    entities = (message.entities or []) + (message.caption_entities or [])
    
    for entity in entities:
        if entity.type in [enums.MessageEntityType.URL, enums.MessageEntityType.TEXT_LINK]:
            has_link = True
            break
            
    if not has_link:
        text = message.text or message.caption or ""
        if "http" in text or "t.me" in text or "www." in text:
            has_link = True

    if has_link:
        user_id = message.from_user.id
        if user_id == OWNER_ID:
            return

        try:
            member = await client.get_chat_member(message.chat.id, user_id)
            if member.status in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]:
                return 
        except:
            pass 

        # Delete and Warn
        try:
            await message.delete()
            warning = await message.reply(
                f"🚫 {message.from_user.mention}, **NO LINKS ALLOWED!**\nOnly Admins can post links here."
            )
            # Delete warning after 5 seconds
            asyncio.create_task(vanish_msg(warning, 5))
            message.stop_propagation()
        except Exception as e:
            print(f"Error deleting link: {e}")

# ================= FEATURE 1: WELCOME, START & RESTART =================

@app.on_message(filters.command("start"))
async def start_handler(client, message):
    # If in Group (Owner Only) -> RESTART BOT
    if message.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        if message.from_user.id == OWNER_ID:
            # Delete the /start command immediately
            await vanish_msg(message)
            
            # Send Restart Status
            status = await message.reply("🔄 **System Restarting...**\nBot is reloading.")
            
            # Delete status after 2 seconds then Restart
            await asyncio.sleep(2)
            await status.delete()
            
            # Restart the script
            os.execl(sys.executable, sys.executable, *sys.argv)
        return

    # If in Private -> Normal Welcome
    user = message.from_user
    text = (
        f"✨ **Greetings, {user.mention}!** ✨\n\n"
        "🤖 **I am SuperBot**\n"
        "I am your advanced automated assistant.\n\n"
        "📌 **My Capabilities:**\n"
        "🔹 **Group Security:** Anti-Link, Anti-spam & Locking\n"
        "🔹 **Media:** Direct Stream Links\n"
        "🔹 **Analysis:** Advanced User Reports\n\n"
        f"🔗 **Join our Official Community:**\n{GROUP_LINK}"
    )
    await message.reply(text, disable_web_page_preview=True)

@app.on_message(filters.new_chat_members)
async def welcome_handler(client, message):
    chat_title = message.chat.title
    asyncio.create_task(vanish_msg(message, 5)) # Delete "User joined" service message
    
    for member in message.new_chat_members:
        if message.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
            welcome_text = (
                f"🎉 **WELCOME TO {chat_title.upper()}!** 🎉\n\n"
                f"👋 **Hello {member.mention}!**\n"
                f"🚀 *Make yourself at home!*"
            )
            try:
                welcome_msg = await message.reply(welcome_text)
                asyncio.create_task(vanish_msg(welcome_msg, WELCOME_DELAY))
            except:
                pass

        # Send DM
        try:
            dm_text = (
                f"👋 **Hello {member.mention}!**\n"
                f"Thank you for joining **{chat_title}**.\n\n"
                f"🎁 **Here is the exclusive Group Link:**\n👉 {GROUP_LINK}"
            )
            await client.send_message(member.id, dm_text, disable_web_page_preview=True)
        except:
            pass

@app.on_message(filters.left_chat_member)
async def leave_handler(client, message):
    await vanish_msg(message)

# ================= FEATURE 2: MODERATION & REPORTS =================

@app.on_message(filters.command("ban") & filters.user(OWNER_ID))
async def ban_user(client, message):
    await vanish_msg(message) # Vanish command
    
    if not message.reply_to_message:
        temp = await message.reply("❌ Reply to a user.")
        return asyncio.create_task(vanish_msg(temp, 3))
        
    try:
        await client.ban_chat_member(message.chat.id, message.reply_to_message.from_user.id)
        succ = await message.reply(f"🚫 **Banned** {message.reply_to_message.from_user.mention}.")
        asyncio.create_task(vanish_msg(succ, 5))
    except Exception as e:
        err = await message.reply(f"❌ Error: {e}")
        asyncio.create_task(vanish_msg(err, 5))

@app.on_message(filters.command("unban") & filters.user(OWNER_ID))
async def unban_user(client, message):
    await vanish_msg(message) # Vanish command

    if not message.reply_to_message:
        temp = await message.reply("❌ Reply to a user.")
        return asyncio.create_task(vanish_msg(temp, 3))

    try:
        await client.unban_chat_member(message.chat.id, message.reply_to_message.from_user.id)
        succ = await message.reply(f"✅ **Unbanned** {message.reply_to_message.from_user.mention}.")
        asyncio.create_task(vanish_msg(succ, 5))
    except Exception as e:
        err = await message.reply(f"❌ Error: {e}")
        asyncio.create_task(vanish_msg(err, 5))

@app.on_message(filters.command("scan_members") & filters.user(OWNER_ID))
async def scan_members(client, message):
    # 1. Vanish the command immediately
    await vanish_msg(message)

    # 2. Show temporary status in group
    status_msg = await message.reply("📊 **Scanning Members...**\nResult will be sent to your DM.")
    
    chat_id = message.chat.id
    online_count = 0
    offline_count = 0
    report_lines = []
    
    report_lines.append(f"FULL MEMBER REPORT FOR: {message.chat.title}")
    report_lines.append(f"Generated on: {datetime.datetime.now()}")
    report_lines.append("=========================================")
    
    async for member in client.get_chat_members(chat_id):
        user = member.user
        status_text = "OFFLINE"
        last_seen = "Unknown"

        if user.status == enums.UserStatus.ONLINE:
            status_text = "ONLINE (Active)"
            last_seen = "Now"
            online_count += 1
        else:
            status_text = "OFFLINE (Inactive)"
            offline_count += 1
            if user.last_online_date:
                last_seen = user.last_online_date.strftime("%Y-%m-%d %H:%M:%S")
            else:
                last_seen = "Hidden"
            
        report_lines.append(f"ID: {user.id} | Name: {user.first_name} | Status: {status_text} | Last Seen: {last_seen}")
    
    filename = f"Report_{chat_id}.txt"
    with open(filename, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))
        
    summary = (
        f"✅ **Scan Complete!**\n"
        f"📂 **Group:** {message.chat.title}\n"
        f"🟢 **Active:** {online_count} | 🔴 **Inactive:** {offline_count}\n"
        f"👥 **Total:** {online_count + offline_count}"
    )
    
    # 3. Send File to DM ONLY (Not Group)
    try:
        await client.send_document(OWNER_ID, document=filename, caption=summary)
        # Update group status to sent
        await status_msg.edit("✅ **Report sent to your Private Messages!**")
    except Exception as e:
        await status_msg.edit(f"❌ Failed to send DM. Check settings.")
    
    if os.path.exists(filename):
        os.remove(filename)

    # 4. Vanish the status message from group after 4 seconds
    asyncio.create_task(vanish_msg(status_msg, 4))

# Bad Words Handler
@app.on_message(filters.group & filters.text & ~filters.user(OWNER_ID), group=3)
async def moderation_handler(client, message):
    if message.sender_chat: return
    text = message.text.lower()
    user_id = message.from_user.id
    chat_id = message.chat.id

    if any(word in text for word in BAD_WORDS):
        if user_id not in user_warnings: user_warnings[user_id] = 0
        user_warnings[user_id] += 1
        await vanish_msg(message)
        
        if user_warnings[user_id] >= WARNING_LIMIT:
            try:
                await client.ban_chat_member(chat_id, user_id)
                w = await message.reply(f"🚫 {message.from_user.mention} banned.")
                asyncio.create_task(vanish_msg(w, 5))
                user_warnings[user_id] = 0
            except: pass
        else:
            w = await message.reply(f"⚠️ {message.from_user.mention}, warning {user_warnings[user_id]}/{WARNING_LIMIT}")
            asyncio.create_task(vanish_msg(w, 5))

@app.on_message(filters.command("lock") & filters.user(OWNER_ID))
async def lock_group(client, message):
    await vanish_msg(message)
    if message.chat.id not in locked_groups:
        locked_groups.append(message.chat.id)
        msg = await message.reply("🔒 **Group LOCKED.**")
    else:
        msg = await message.reply("Already locked.")
    asyncio.create_task(vanish_msg(msg, 5))

@app.on_message(filters.command("unlock") & filters.user(OWNER_ID))
async def unlock_group(client, message):
    await vanish_msg(message)
    if message.chat.id in locked_groups:
        locked_groups.remove(message.chat.id)
        msg = await message.reply("🔓 **Group UNLOCKED.**")
        asyncio.create_task(vanish_msg(msg, 5))

# ================= FEATURE 3: DOWNLOADING =================
@app.on_message(filters.command("dl") & filters.user(OWNER_ID))
async def downloader(client, message):
    await vanish_msg(message) # Vanish Command
    if len(message.command) < 2:
        temp = await message.reply("Provide a link!")
        return asyncio.create_task(vanish_msg(temp, 3))
        
    url = message.text.split(None, 1)[1]
    status_msg = await message.reply("⚡ Downloading...")
    ydl_opts = {'outtmpl': f'{DOWNLOAD_PATH}/%(title)s.%(ext)s', 'format': 'best', 'noplaylist': True, 'quiet': True}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
        await status_msg.edit("⬆️ Uploading...")
        await client.send_document(message.chat.id, document=filename)
        os.remove(filename)
        await status_msg.delete() # Remove status
    except Exception as e:
        await status_msg.edit(f"Error: {str(e)}")
        asyncio.create_task(vanish_msg(status_msg, 5))

# ================= FEATURE 4: BROADCAST =================
@app.on_message(filters.command("broadcast") & filters.user(OWNER_ID))
async def broadcast_post(client, message):
    # 1. Delete the /broadcast command
    await vanish_msg(message)

    if not message.reply_to_message:
        temp = await message.reply("Reply to a message to broadcast.")
        return asyncio.create_task(vanish_msg(temp, 3))
    
    # 2. Copy the message to the group (Broadcast content stays)
    await message.reply_to_message.copy(message.chat.id)
    
    # 3. Send confirmation and then vanish it
    conf = await message.reply("✅ Broadcast sent.")
    asyncio.create_task(vanish_msg(conf, 3))

# ================= FEATURE 5: STREAMABLE LINKS =================
@app.on_message(filters.command("stream") & filters.user(OWNER_ID))
async def stream_handler(client, message):
    await vanish_msg(message) # Vanish command
    
    url = ""
    if len(message.command) > 1:
        url = message.text.split(None, 1)[1]
    elif message.reply_to_message and message.reply_to_message.text:
        url = message.reply_to_message.text
    else:
        temp = await message.reply("❌ Usage: `/stream [Link]`")
        return asyncio.create_task(vanish_msg(temp, 3))

    status = await message.reply("🔄 **Fetching Link...**")
    
    try:
        proc = await asyncio.create_subprocess_shell(
            f"yt-dlp --get-url -f best \"{url}\"",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        
        if stdout:
            direct_link = stdout.decode().strip()
            # This result stays (it's the requested content)
            await status.edit(
                f"✅ **Stream Generated!**\n\n🔗 **Original:** {url}\n📺 **Direct:** [Click Here]({direct_link})",
                disable_web_page_preview=True
            )
        else:
            await status.edit("❌ Error extracting link.")
            asyncio.create_task(vanish_msg(status, 5))
            
    except Exception as e:
        await status.edit(f"❌ Error: {e}")
        asyncio.create_task(vanish_msg(status, 5))

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
