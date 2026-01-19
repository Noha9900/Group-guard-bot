import os
import asyncio
import datetime
import yt_dlp
from aiohttp import web
from pyrogram import Client, filters, idle, enums
from pyrogram.types import Message
from pytgcalls import PyTgCalls

# ================= CONFIGURATION =================
API_ID = 36982189  # Your API ID
API_HASH = "d3ec5feee7342b692e7b5370fb9c8db7"
BOT_TOKEN = "8544773286:AAHkDc5awfunKMaO-407F7JtcmrY1OmazRc"
OWNER_ID = 8072674531  # Your User ID

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

# ================= FEATURE: STRICT GROUP LOCK (High Priority) =================
@app.on_message(filters.group & ~filters.user(OWNER_ID), group=1)
async def lock_check(client, message):
    if message.chat.id in locked_groups:
        try:
            await message.delete()
        except:
            pass
        message.stop_propagation()

# ================= FEATURE: ANTI-LINK SYSTEM (NEW) =================
@app.on_message(filters.group & (filters.text | filters.caption), group=2)
async def anti_link_check(client, message):
    # 1. Check if message contains a Link entity (URL or Text Link)
    has_link = False
    entities = (message.entities or []) + (message.caption_entities or [])
    
    for entity in entities:
        if entity.type in [enums.MessageEntityType.URL, enums.MessageEntityType.TEXT_LINK]:
            has_link = True
            break
            
    # Fallback: Check for raw text (e.g., if entity detection fails)
    if not has_link:
        text = message.text or message.caption or ""
        if "http" in text or "t.me" in text or "www." in text:
            has_link = True

    # 2. If Link found, check if User is Admin
    if has_link:
        user_id = message.from_user.id
        
        # Always allow the Bot Owner
        if user_id == OWNER_ID:
            return

        # Check if user is a Group Admin
        try:
            member = await client.get_chat_member(message.chat.id, user_id)
            if member.status in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]:
                return # User is admin, allow the link
        except:
            pass # If check fails, assume user is not admin and delete

        # 3. User is NOT Admin -> Delete and Warn
        try:
            await message.delete()
            warning = await message.reply(
                f"🚫 {message.from_user.mention}, **NO LINKS ALLOWED!**\n\nOnly Admins can post links here."
            )
            # Delete the warning after 5 seconds to keep chat clean
            await asyncio.sleep(5)
            await warning.delete()
            # Stop other handlers (like bad words) since msg is deleted
            message.stop_propagation()
        except Exception as e:
            print(f"Error deleting link: {e}")

# ================= FEATURE 1: WELCOME & CLEANUP =================

@app.on_message(filters.command("start") & filters.private)
async def start_private(client, message):
    user = message.from_user
    text = (
        f"✨ **Greetings, {user.mention}!** ✨\n\n"
        "🤖 **I am SuperBot**\n"
        "I am your advanced automated assistant.\n\n"
        "📌 **My Capabilities:**\n"
        "🔹 **Group Security:** Anti-Link, Anti-spam & Locking\n"
        "🔹 **Media:** Direct Stream Links (No Download)\n"
        "🔹 **Analysis:** Advanced User Reports\n\n"
        f"🔗 **Join our Official Community:**\n{GROUP_LINK}"
    )
    await message.reply(text, disable_web_page_preview=True)

@app.on_message(filters.new_chat_members)
async def welcome_handler(client, message):
    chat_id = message.chat.id
    chat_title = message.chat.title

    asyncio.create_task(delete_service_message(message))
    
    for member in message.new_chat_members:
        if message.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
            welcome_text = (
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🎉 **WELCOME TO {chat_title.upper()}!** 🎉\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"👋 **Hello {member.mention}!**\n"
                f"We are absolutely thrilled to have you here.\n\n"
                f"🔰 **User ID:** `{member.id}`\n"
                f"📅 **Joined:** Just now\n\n"
                f"💡 **Things to do here:**\n"
                f"• Read the pinned rules.\n"
                f"• Respect other members.\n"
                f"• Enjoy the content!\n\n"
                f"🚀 *Make yourself at home!*"
            )
            try:
                welcome_msg = await message.reply(welcome_text)
                await asyncio.sleep(WELCOME_DELAY)
                await welcome_msg.delete()
            except:
                pass

        try:
            dm_text = (
                f"👋 **Hello {member.mention}!**\n\n"
                f"Thank you for joining **{chat_title}**.\n\n"
                f"🎁 **Here is the exclusive Group Link:**\n"
                f"👉 {GROUP_LINK}\n\n"
                "*(I sent this automatically because you joined our community)*"
            )
            await client.send_message(member.id, dm_text, disable_web_page_preview=True)
        except Exception as e:
            pass

@app.on_message(filters.left_chat_member)
async def leave_handler(client, message):
    try:
        await message.delete()
    except:
        pass

async def delete_service_message(message):
    try:
        await asyncio.sleep(5) 
        await message.delete()
    except:
        pass

# ================= FEATURE 2: MODERATION & REPORTS =================

@app.on_message(filters.command("ban") & filters.user(OWNER_ID))
async def ban_user(client, message):
    if not message.reply_to_message:
        return await message.reply("❌ Reply to a user to ban them.")
    try:
        await client.ban_chat_member(message.chat.id, message.reply_to_message.from_user.id)
        await message.reply(f"🚫 **Banned** {message.reply_to_message.from_user.mention}.")
    except Exception as e:
        await message.reply(f"❌ Error: {e}")

@app.on_message(filters.command("unban") & filters.user(OWNER_ID))
async def unban_user(client, message):
    if not message.reply_to_message:
        return await message.reply("❌ Reply to a user to unban them.")
    try:
        await client.unban_chat_member(message.chat.id, message.reply_to_message.from_user.id)
        await message.reply(f"✅ **Unbanned** {message.reply_to_message.from_user.mention}.")
    except Exception as e:
        await message.reply(f"❌ Error: {e}")

@app.on_message(filters.command("scan_members") & filters.user(OWNER_ID))
async def scan_members(client, message):
    status_msg = await message.reply("📊 **Scanning Members...** Report will be sent to your DM.")
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
                last_seen = "Long time ago / Hidden"
            
        report_lines.append(f"ID: {user.id} | User: @{user.username or 'None'} | Name: {user.first_name} | Status: {status_text} | Last Seen: {last_seen}")
    
    filename = f"Report_{chat_id}.txt"
    with open(filename, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))
        
    summary = (
        f"✅ **Scan Complete!**\n\n"
        f"📂 **Group:** {message.chat.title}\n"
        f"🟢 **Active:** {online_count}\n"
        f"🔴 **Inactive:** {offline_count}\n"
        f"👥 **Total:** {online_count + offline_count}\n\n"
        f"📄 *The full detailed list is attached above.*"
    )
    
    try:
        await client.send_document(OWNER_ID, document=filename, caption=summary)
        await status_msg.edit("✅ **Report sent to your Private Messages!**")
    except Exception as e:
        await status_msg.edit(f"❌ Failed to send DM. Make sure you have started the bot in private.\nError: {e}")
    
    if os.path.exists(filename):
        os.remove(filename)

# Group 3: Bad Words (Runs after Anti-Link)
@app.on_message(filters.group & filters.text & ~filters.user(OWNER_ID), group=3)
async def moderation_handler(client, message):
    if message.sender_chat:
        return
    text = message.text.lower()
    user_id = message.from_user.id
    chat_id = message.chat.id

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
        await message.reply("🔒 **Group LOCKED.**\nOnly Admins can send messages/media.")
    else:
        await message.reply("Group is already locked.")

@app.on_message(filters.command("unlock") & filters.user(OWNER_ID))
async def unlock_group(client, message):
    if message.chat.id in locked_groups:
        locked_groups.remove(message.chat.id)
        await message.reply("🔓 **Group UNLOCKED.**")

# ================= FEATURE 3: DOWNLOADING =================
@app.on_message(filters.command("dl") & filters.user(OWNER_ID))
async def downloader(client, message):
    if len(message.command) < 2:
        return await message.reply("Please provide a link!")
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
        await status_msg.delete()
    except Exception as e:
        await status_msg.edit(f"Error: {str(e)}")

# ================= FEATURE 4: BROADCAST =================
@app.on_message(filters.command("broadcast") & filters.user(OWNER_ID))
async def broadcast_post(client, message):
    if not message.reply_to_message:
        return await message.reply("Reply to a message to broadcast.")
    await message.reply_to_message.copy(message.chat.id)
    await message.reply("✅ Broadcast sent.")

# ================= FEATURE 5: STREAMABLE LINKS (NO DOWNLOAD) =================
@app.on_message(filters.command("stream") & filters.user(OWNER_ID))
async def stream_handler(client, message):
    url = ""
    if len(message.command) > 1:
        url = message.text.split(None, 1)[1]
    elif message.reply_to_message and message.reply_to_message.text:
        url = message.reply_to_message.text
    else:
        return await message.reply("❌ **Usage:** `/stream [Link]` or Reply to a link.")

    status = await message.reply("🔄 **Fetching Direct Link...**")
    
    try:
        proc = await asyncio.create_subprocess_shell(
            f"yt-dlp --get-url -f best \"{url}\"",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        
        if stdout:
            direct_link = stdout.decode().strip()
            await status.edit(
                f"✅ **Streamable Link Generated!**\n\n"
                f"🔗 **Original:** {url}\n"
                f"📺 **Direct Stream:** [Click Here]({direct_link})\n\n"
                f"*(This link is direct from source and uses no server storage)*",
                disable_web_page_preview=True
            )
        else:
            await status.edit(f"❌ Could not extract link. The site might be unsupported.")
            
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
