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
# FIX: Use Render's dynamic port, or default to 10000
PORT = int(os.environ.get("PORT", 10000))
BASE_URL = os.environ.get("BASE_URL", "https://group-guard-bot.onrender.com").rstrip('/')

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

# ================= WEB SERVER FIX =================
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
    # FIX: Bind to 0.0.0.0 and the assigned PORT for Render to detect the service
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    print(f"--- Web Server Started on Port {PORT} ---")

# ================= ADMIN & MODERATION FEATURES =================

@app.on_message(filters.command("cleanup") & filters.group)
async def cleanup_deleted(client, message):
    asyncio.create_task(vanish_msg(message))
    if not await is_admin(client, message.chat.id, message.from_user.id): return
    status_msg = await message.reply("🔍 **Scanning for deleted accounts...**")
    deleted_count = 0
    async for member in client.get_chat_members(message.chat.id):
        if member.user.is_deleted:
            try:
                await client.ban_chat_member(message.chat.id, member.user.id)
                await client.unban_chat_member(message.chat.id, member.user.id)
                deleted_count += 1
            except FloodWait as e: await asyncio.sleep(e.value)
            except: pass
    await status_msg.edit(f"✅ Removed `{deleted_count}` deleted accounts.")
    asyncio.create_task(vanish_msg(status_msg, 5))

@app.on_message(filters.command("status") & filters.group)
async def status_report(client, message):
    asyncio.create_task(vanish_msg(message))
    if not await is_admin(client, message.chat.id, message.from_user.id): return
    status_msg = await message.reply("📊 **Generating Audit...**")
    active_list, inactive_list = [], []
    async for member in client.get_chat_members(message.chat.id):
        u = member.user
        if u.is_deleted: continue
        uname = f"@{u.username}" if u.username else "No Username"
        ustatus = str(u.status).replace("UserStatus.", "").lower() if u.status else "hidden"
        last_seen = u.last_online_date if hasattr(u, 'last_online_date') and u.last_online_date else "N/A"
        line = f"{u.id:<15} | {uname:<20} | {ustatus:<12} | {last_seen}"
        if ustatus in ["online", "recently"]: active_list.append(line)
        else: inactive_list.append(line)
    report = f"Audit: {message.chat.title}\nActive Users:\n" + "\n".join(active_list) + "\n\nInactive:\n" + "\n".join(inactive_list)
    bio = io.BytesIO(report.encode()); bio.name = f"Audit_{message.chat.id}.txt"
    await client.send_document(OWNER_ID, bio, caption=f"📑 Audit for {message.chat.title}")
    await status_msg.edit("✅ Audit sent to Admin DM.")
    asyncio.create_task(vanish_msg(status_msg, 5))

@app.on_message(filters.group & (filters.text | filters.caption), group=-1)
async def anti_link(client, message):
    if await is_admin(client, message.chat.id, message.from_user.id): return
    entities = (message.entities or []) + (message.caption_entities or [])
    if any(e.type in [enums.MessageEntityType.URL, enums.MessageEntityType.TEXT_LINK] for e in entities):
        asyncio.create_task(vanish_msg(message, 0))
        uid = message.from_user.id
        user_warnings[uid] = user_warnings.get(uid, 0) + 1
        w = await message.reply(f"⚠️ {message.from_user.mention} No links! ({user_warnings[uid]}/3)")
        asyncio.create_task(vanish_msg(w, 5))
        if user_warnings[uid] >= 3: await client.ban_chat_member(message.chat.id, uid)

@app.on_message(filters.command(["lock", "unlock"]))
async def group_lock_unlock(client, message):
    asyncio.create_task(vanish_msg(message))
    if not await is_admin(client, message.chat.id, message.from_user.id): return
    if message.command[0] == "lock":
        await client.set_chat_permissions(message.chat.id, ChatPermissions(can_send_messages=False))
        await message.reply("🔒 Group Locked.")
    else:
        await client.set_chat_permissions(message.chat.id, ChatPermissions(can_send_messages=True))
        await message.reply("🔓 Group Unlocked.")

# ================= RUNNER =================
async def main():
    # START WEB SERVER FIRST - Required by Render
    await start_web_server()
    await app.start()
    print("--- SuperBot Online & Port Detected ---")
    await idle()
    await app.stop()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
    
