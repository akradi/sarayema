from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
from datetime import datetime

TOKEN = "توکن_ربات_را_اینجا_بگذار"

user_last_message = {}

def start(update, context):
    update.message.reply_text("سلام! من مدیر گروه هستم 😎")

def restrict_messages(update, context):
    chat_id = update.message.chat.id
    user_id = update.message.from_user.id
    current_time = datetime.now().hour

    # فقط بین 9 صبح تا 9 شب پیام مجازه
    if not (9 <= current_time < 21):
        update.message.reply_text("⏳ ارسال پیام فقط از ساعت 9 صبح تا 9 شب مجاز است.")
        return

    # بررسی ارسال یک پیام در روز
    today = datetime.now().date()
    if user_id in user_last_message and user_last_message[user_id] == today:
        update.message.reply_text("🚫 شما فقط یک بار در روز می‌توانید پیام بفرستید!")
        return

    user_last_message[user_id] = today

def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher
    
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, restrict_messages))
    
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
