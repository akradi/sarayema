from telegram import Update, ChatPermissions
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo  # برای مناطق زمانی
import asyncio
import logging

# تنظیم لاگ‌ها برای دیباگ بهتر
logging.basicConfig(level=logging.INFO)

# 🔒 توکن ربات خود را در اینجا قرار دهید
TOKEN = "7464967230:AAEyFh1o_whGxXCoKdZGrGKFDsvasK6n7-4"

user_last_message = {}
user_violations = {}
user_last_error = {}
muted_users = {}

MAX_VIOLATIONS = 3  # حداکثر تعداد نقض مجاز
MUTE_DURATION = timedelta(hours=1)  # مدت زمان بی‌صدا کردن کاربر


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("سلام! من مدیر گروه هستم 😎")


async def restrict_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    # گرفتن وضعیت کاربر در گروه
    try:
        chat_member = await context.bot.get_chat_member(chat_id, user_id)
        user_status = chat_member.status
    except Exception as e:
        logging.error(f"خطا در دریافت وضعیت کاربر: {e}")
        return

    # اگر کاربر مالک یا ادمین است، محدودیت‌ها اعمال نشود
    if user_status in ['creator', 'administrator']:
        return

    # زمان فعلی بر اساس منطقه زمانی تورنتو
    toronto_tz = ZoneInfo('America/Toronto')
    current_time = datetime.now(toronto_tz)
    current_hour = current_time.hour
    today = current_time.date()

    # بررسی محدودیت زمانی
    if not (9 <= current_hour < 21):
        # حذف پیام کاربر
        try:
            await update.message.delete()
        except Exception as e:
            logging.error(f"خطا در حذف پیام کاربر: {e}")
        await handle_violation(update, context, violation_type="time")
        return

    # بررسی ارسال بیش از یک پیام در روز
    if user_id in user_last_message and user_last_message[user_id] == today:
        # حذف پیام کاربر
        try:
            await update.message.delete()
        except Exception as e:
            logging.error(f"خطا در حذف پیام کاربر: {e}")
        await handle_violation(update, context, violation_type="message_limit")
        return

    # ذخیره زمان آخرین پیام کاربر
    user_last_message[user_id] = today

    # ریست کردن تعداد نقض‌های کاربر در صورت ارسال پیام مجاز
    user_violations[user_id] = 0
    user_last_error[user_id] = None


async def handle_violation(update: Update, context: ContextTypes.DEFAULT_TYPE, violation_type):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    violation_messages = {
        "time": f"{update.effective_user.mention_html()} عزیز\n⏳ ارسال پیام در این گروه فقط از ساعت ۹ صبح تا ۹ شب به وقت تورنتو مجاز است.",
        "message_limit": f"{update.effective_user.mention_html()} 🚫 شما فقط یک بار در روز می‌توانید پیام بفرستید!",
        "muted": f"{update.effective_user.mention_html()} 🚫 به دلیل رعایت نکردن قوانین، شما تا\n{int(MUTE_DURATION.total_seconds() // 3600)} ساعت آینده نمی‌توانید پیام ارسال کنید.",
        "add_bot": f"{update.effective_user.mention_html()} 🚫 فقط ادمین‌ها می‌توانند ربات اضافه کنند."
    }

    # بررسی اینکه آخرین پیام خطا چه زمانی ارسال شده
    last_error_time = user_last_error.get(user_id)
    time_since_last_error = (datetime.now() - last_error_time).total_seconds() if last_error_time else None

    if not last_error_time or time_since_last_error > 30:
        # ارسال پیام خطا به صورت سایلنت
        try:
            error_message = await context.bot.send_message(
                chat_id=chat_id,
                text=violation_messages[violation_type],
                parse_mode="HTML",
                disable_notification=True
            )
            # حذف پیام خطا بعد از 7 ثانیه
            asyncio.create_task(delete_message_after_delay(error_message, 7))
        except Exception as e:
