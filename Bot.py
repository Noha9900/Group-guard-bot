Import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, ChatMemberHandler
import time

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Replace 'YOUR_BOT_TOKEN' with your actual bot token
TOKEN = 'YOUR_BOT_TOKEN'

# List of admin user IDs
ADMIN_IDS = [123456789]  # Replace with your Telegram user IDs

# In-memory storage for warnings and locks (for demo purposes)
warnings = {}
locked_groups = {}

def is_admin(user_id):
    return user_id in ADMIN_IDS

# Welcome new members
def welcome_new_member(update: Update, context: CallbackContext):
    for member in update.message.new_chat_members:
        username = member.username or member.first_name
        chat_id = update.effective_chat.id
        message = f"🎉 Welcome {username}! Glad to have you here."
        sent_message = update.message.reply_text(message)
        # Delete welcome message after 20 seconds
        time.sleep(20)
        context.bot.delete_message(chat_id=chat_id, message_id=sent_message.message_id)

# Warn users for bad words
BAD_WORDS = ['hate', 'kill', 'racist', 'religion harassment', 'admin', 'murder']  # Extend as needed

def check_bad_words(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    message_text = update.message.text.lower()
    chat_id = update.effective_chat.id

    if any(bad_word in message_text for bad_word in BAD_WORDS):
        warnings[user_id] = warnings.get(user_id, 0) + 1
        warn_count = warnings[user_id]
        if warn_count >= 3:
            if is_admin(user_id):
                update.message.reply_text("Admins cannot be warned or banned.")
            else:
                context.bot.kick_chat_member(chat_id, user_id)
                update.message.reply_text(f"User {update.effective_user.first_name} has been banned for repeated bad behavior.")
        else:
            update.message.reply_text(f"Warning {warn_count}/3: Please refrain from using inappropriate language.")

# Remove deleted members
def remove_deleted_members(update: Update, context: CallbackContext):
    # Not directly supported; need to monitor member status
    pass

# Lock group with password
def lock_group(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return
    if len(context.args) != 1:
        update.message.reply_text("Usage: /lock <password>")
        return
    password = context.args[0]
    chat_id = update.effective_chat.id
    locked_groups[chat_id] = password
    update.message.reply_text(f"Group locked with password.")

def join_group(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    if chat_id in locked_groups:
        # Check password in message or via command
        pass

# Main function
def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    # Handlers
    dp.add_handler(ChatMemberHandler(welcome_new_member, ChatMemberHandler.CHAT_MEMBER))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, check_bad_words))
    # Add more handlers for other features

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
