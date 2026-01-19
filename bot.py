import os
import sys
import asyncio
import datetime
import yt_dlp
import zipfile
import io
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
PORT = int(os.environ.get("PORT", 8080))
BASE_URL = os.environ.get("BASE_URL", "http://0.0.0.0:8080").rstrip('/')

app = Client("SuperBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

user_dl_count = {}
user_warnings = {}

if not os.path.exists(DOWNLOAD_PATH):
    os.makedirs(DOWNLOAD_PATH)

# ================= HELPERS =================
async def vanish_msg(message, delay=1):
    await asyncio.sleep(delay)
    try: await message.delete()
    except: pass

async def is_admin(client, chat_id, user_id):
    if user_id == OWNER_ID: return True
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]
    except: return False

# ================= FEATURE: CLEANUP DELETED ACCOUNTS =================
@app.on_message(filters.command("cleanup") & filters.group)
async def cleanup_deleted(client, message):
    asyncio.create_task(vanish_msg(message))
    if not await is_admin(client, message.chat.id, message.from_user.id): return

    status_msg = await message.reply("🔍 **Scanning for deleted accounts...**")
    deleted_count = 0
    
    try:
        async for member in client.get_chat_members(message.chat.id):
            if member.user.is_deleted:
                try:
                    await client.ban_chat_member(message.chat.id, member.user.id)
                    await client.unban_chat_member(message.chat.id, member.user.id) # Kick only
                    deleted_count += 1
                except FloodWait as e:
                    await asyncio.sleep(e.value)
                except Exception:
                    pass
        
        await status_msg.edit(f"✅ **Cleanup Complete!**\nRemoved `{deleted_count}` deleted accounts.")
        asyncio.create_task(vanish_msg(status_msg, 5))
    except Exception as e:
        await status_msg.edit(f"❌ Error: {e}")

# ================= FEATURE: ENHANCED STATUS REPORT =================
@app.on_message(filters.command("status") & filters.group)
async def status_report(client, message):
    asyncio.create_task(vanish_msg(message))
    if not await is_admin(client, message.chat.id, message.from_user.id): return

    status_msg = await message.reply("📊 **Generating Audit...**")
    try:
        active_list = []
        inactive_list = []
        
        async for member in client.get_chat_members(message.chat.id):
            u = member.user
            if u.is_deleted: continue
            
            uname = f"@{u.username}" if u.username else "No Username"
            ustatus = str(u.status).replace("UserStatus.", "").lower() if u.status else "hidden"
            last_seen = u.last_online_date if hasattr(u, 'last_online_date') and u.last_online_date else "N/A"
            
            line = f"{u.id:<15} | {uname:<20} | {ustatus:<12} | {last_seen}"
            
            # Sort into Active vs Inactive
            if ustatus in ["online", "recently"]:
                active_list.append(line)
            else:
                inactive_list.append(line)

        report = f"Detailed Audit for: {message.chat.title}\n"
        report += f"Generated: {datetime.datetime.now()}\n\n"
        report += "🟢 ACTIVE USERS (Online/Recently)\n" + "-"*75 + "\n"
        report += "\n".join(active_list) + "\n\n"
        report += "🔴 INACTIVE USERS (Offline/Long Ago)\n" + "-"*75 + "\n"
        report += "\n".join(inactive_list)
        
        bio = io.BytesIO(report.encode())
        bio.name = f"Full_Audit_{message.chat.id}.txt"
        await client.send_document(OWNER_ID, bio, caption=f"📑 **Status Report for {message.chat.title}**")
        await status_msg.edit("✅ Audit sent to Admin DM.")
        asyncio.create_task(vanish_msg(status_msg, 5))
    except Exception as e:
        await status_msg.edit(f"❌ Error: {e}")

# ================= RUNNER =================
async def main():
    await app.start()
    print("--- SuperBot Online: Cleanup & Audit Active ---")
    await idle()

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
    
