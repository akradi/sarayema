from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from datetime import datetime

TOKEN = "7464967230:AAEyFh1o_whGxXCoKdZGrGKFDsvasK6n7-4"

user_last_message = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("سلام! من مدیر گروه هستم 😎")

async def restrict_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat.id
    user_id = update.message.from_user.id
    message_id = update.message.message_id
    current_time = datetime.now().hour

    # حذف پیام‌های خارج از ساعت مجاز
    if not (9 <= current_time < 21):
        await update.message.delete()
        await context.bot.send_message(
            chat_id=user_id,
            text="⏳ ارسال پیام فقط از ساعت 9 صبح تا 9 شب مجاز است."
        )
        return

    # بررسی ارسال یک پیام در روز
    today = datetime.now().date()
    if user_id in user_last_message and user_last_message[user_id] == today:
        await update.message.delete()
        await context.bot.send_message(
            chat_id=user_id,
            text="🚫 شما فقط یک بار در روز می‌توانید پیام بفرستید!"
        )
        return

    user_last_message[user_id] = today

def main():
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, restrict_messages))
    
    print("✅ ربات در حال اجرا است...")
    app.run_polling()

if __name__ == "__main__":
    main()
