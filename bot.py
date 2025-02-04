from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from datetime import datetime
from zoneinfo import ZoneInfo  # برای مناطق زمانی
import asyncio  # برای استفاده از sleep
import logging

# توکن ربات خود را در اینجا قرار دهید
TOKEN = "7464967230:AAEyFh1o_whGxXCoKdZGrGKFDsvasK6n7-4"

user_last_message = {}
logging.basicConfig(level=logging.INFO)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.info("دستور /start دریافت شد.")
    await update.message.reply_text(
        "سلام! من مدیر گروه هستم 😎\nلطفاً برای دریافت پیام‌های خصوصی، یک گفتگوی خصوصی با من شروع کنید."
    )

async def restrict_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    # زمان فعلی بر اساس منطقه زمانی تورنتو
    toronto_tz = ZoneInfo('America/Toronto')
    current_dt = datetime.now(toronto_tz)
    current_hour = current_dt.hour
    today = current_dt.date()

    logging.info(f"پیام جدید از کاربر {user_id} در ساعت {current_hour} به وقت تورنتو.")

    # گرفتن وضعیت کاربر در گروه
    try:
        chat_member = await context.bot.get_chat_member(chat_id, user_id)
        user_status = chat_member.status
        logging.info(f"وضعیت کاربر: {user_status}")
    except Exception as e:
        logging.error(f"خطا در دریافت وضعیت کاربر: {e}")
        return

    # اگر کاربر مالک یا ادمین است، محدودیت‌ها اعمال نشود
    if user_status in ['creator', 'administrator']:
        logging.info("کاربر ادمین یا مالک است؛ محدودیت‌ها اعمال نمی‌شود.")
        return

    # حذف پیام‌های خارج از ساعت مجاز
    if not (9 <= current_hour < 21):
        try:
            await update.message.delete()
            error_message = await update.message.reply_text(
                f"{update.effective_user.mention_html()} ⏳ ارسال پیام فقط از ساعت 9 صبح تا 9 شب (به وقت تورنتو) مجاز است.",
                parse_mode="HTML"
            )
            logging.info("پیام کاربر حذف شد و پیام خطا ارسال شد.")
            # حذف پیام خطا بعد از 10 ثانیه
            await asyncio.sleep(10)
            await error_message.delete()
            logging.info("پیام خطا حذف شد.")
        except Exception as e:
            logging.error(f"خطا در حذف پیام یا ارسال پیام خطا: {e}")
        return

    # بررسی ارسال یک پیام در روز
    if user_id in user_last_message and user_last_message[user_id] == today:
        try:
            await update.message.delete()
            error_message = await update.message.reply_text(
                f"{update.effective_user.mention_html()} 🚫 شما فقط یک بار در روز می‌توانید پیام بفرستید!",
                parse_mode="HTML"
            )
            logging.info("پیام کاربر به دلیل ارسال بیش از یک پیام در روز حذف شد و پیام خطا ارسال شد.")
            # حذف پیام خطا بعد از 10 ثانیه
            await asyncio.sleep(10)
            await error_message.delete()
            logging.info("پیام خطا حذف شد.")
        except Exception as e:
            logging.error(f"خطا در حذف پیام یا ارسال پیام خطا: {e}")
        return

    user_last_message[user_id] = today
    logging.info("پیام کاربر پذیرفته شد.")

def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, restrict_messages))

    print("✅ ربات در حال اجرا است...")
    app.run_polling()

if __name__ == "__main__":
    main()
