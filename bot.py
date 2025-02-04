from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from datetime import datetime
from zoneinfo import ZoneInfo  # برای مناطق زمانی
import asyncio  # برای استفاده از sleep

# توکن ربات خود را در اینجا قرار دهید
TOKEN = "7464967230:AAEyFh1o_whGxXCoKdZGrGKFDsvasK6n7-4"

user_last_message = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("سلام! من مدیر گروه هستم 😎")

async def restrict_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat.id
    user_id = update.message.from_user.id

    # گرفتن وضعیت کاربر در گروه
    chat_member = await context.bot.get_chat_member(chat_id, user_id)
    user_status = chat_member.status

    # اگر کاربر مالک یا ادمین است، محدودیت‌ها اعمال نشود
    if user_status in ['creator', 'administrator']:
        return

    # زمان فعلی بر اساس منطقه زمانی تورنتو
    toronto_tz = ZoneInfo('America/Toronto')
    current_time = datetime.now(toronto_tz)
    current_hour = current_time.hour
    today = current_time.date()

    # حذف پیام‌های خارج از ساعت مجاز
    if not (9 <= current_hour < 21):
        # حذف پیام کاربر
        await update.message.delete()
        # ارسال پیام خطا به صورت پیام جدید
        error_message = await context.bot.send_message(
            chat_id=chat_id,
            text=f"{update.message.from_user.mention_html()} ⏳ ارسال پیام فقط از ساعت 9 صبح تا 9 شب (به وقت تورنتو) مجاز است.",
            parse_mode="HTML"
        )
        # حذف پیام خطا بعد از 10 ثانیه
        await asyncio.sleep(10)
        await error_message.delete()
        return

    # بررسی ارسال یک پیام در روز
    if user_id in user_last_message and user_last_message[user_id] == today:
        # حذف پیام کاربر
        await update.message.delete()
        # ارسال پیام خطا به صورت پیام جدید
        error_message = await context.bot.send_message(
            chat_id=chat_id,
            text=f"{update.message.from_user.mention_html()} 🚫 شما فقط یک بار در روز می‌توانید پیام بفرستید!",
            parse_mode="HTML"
        )
        # حذف پیام خطا بعد از 10 ثانیه
        await asyncio.sleep(10)
        await error_message.delete()
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
