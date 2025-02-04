from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from datetime import datetime
import logging

# توکن ربات خود را در اینجا قرار دهید
TOKEN = "7464967230:AAEyFh1o_whGxXCoKdZGrGKFDsvasK6n7-4"

user_last_message = {}

# فعال‌سازی لاگ برای دیباگ راحت‌تر
logging.basicConfig(level=logging.INFO)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "سلام! من مدیر گروه هستم 😎\nلطفاً برای دریافت پیام‌های خصوصی، یک گفتگوی خصوصی با من شروع کنید."
    )

async def restrict_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat.id
    user_id = update.message.from_user.id
    current_time = datetime.now().hour

    # گرفتن وضعیت کاربر در گروه
    chat_member = await context.bot.get_chat_member(chat_id, user_id)
    user_status = chat_member.status  # می‌تواند 'creator', 'administrator', 'member' و غیره باشد.

    # اگر کاربر مالک یا ادمین است، محدودیت‌ها اعمال نشود
    if user_status in ['creator', 'administrator']:
        return

    # حذف پیام‌های خارج از ساعت مجاز
    if not (9 <= current_time < 21):
        await update.message.delete()
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text="⏳ ارسال پیام فقط از ساعت 9 صبح تا 9 شب مجاز است.",
                parse_mode="HTML"
            )
        except Exception as e:
            logging.error(f"خطا در ارسال پیام خصوصی به کاربر {user_id}: {e}")
            # ارسال پیام در گروه به عنوان آخرین راهکار
            await update.message.reply_text(
                f"{update.message.from_user.mention_html()} ⏳ ارسال پیام فقط از ساعت 9 صبح تا 9 شب مجاز است.",
                parse_mode="HTML"
            )
        return

    # بررسی ارسال یک پیام در روز
    today = datetime.now().date()
    if user_id in user_last_message and user_last_message[user_id] == today:
        await update.message.delete()
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text="🚫 شما فقط یک بار در روز می‌توانید پیام بفرستید!",
                parse_mode="HTML"
            )
        except Exception as e:
            logging.error(f"خطا در ارسال پیام خصوصی به کاربر {user_id}: {e}")
            # ارسال پیام در گروه به عنوان آخرین راهکار
            await update.message.reply_text(
                f"{update.message.from_user.mention_html()} 🚫 شما فقط یک بار در روز می‌توانید پیام بفرستید!",
                parse_mode="HTML"
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
