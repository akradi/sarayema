from telegram import (
    Update, ChatPermissions, InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ContextTypes, filters, CallbackQueryHandler, ChatMemberHandler
)
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo
import asyncio
import logging
import json
import os
import firebase_admin
from firebase_admin import credentials, db

logging.basicConfig(level=logging.INFO)
TOKEN = os.getenv("TOKEN")

# لیست شناسه‌های کاربری مجاز (شناسه عددی تلگرام شما)
AUTHORIZED_USERS = [123456789, 987654321]  # شناسه‌های عددی خود و کاربران دیگر را جایگزین کنید

user_last_message = {}
user_violations = {}
user_last_error = {}
muted_users = {}
group_chats = {}  # دیکشنری از شناسهٔ گروه‌ها به نام آن‌ها

MAX_VIOLATIONS = 3
MUTE_DURATION = timedelta(hours=1)

# منطقه زمانی تورنتو
toronto_tz = ZoneInfo('America/Toronto')

# تنظیمات Firebase
firebase_credentials = os.getenv('FIREBASE_CREDENTIALS')
firebase_database_url = os.getenv('FIREBASE_DATABASE_URL')

if not (firebase_credentials and firebase_database_url):
    logging.error("متغیرهای محیطی FIREBASE_CREDENTIALS و FIREBASE_DATABASE_URL تنظیم نشده‌اند.")
    exit(1)

cred = credentials.Certificate(json.loads(firebase_credentials))
firebase_admin.initialize_app(cred, {
    'databaseURL': firebase_database_url
})

def save_group(chat_id, chat_title):
    ref = db.reference(f'group_chats/{chat_id}')
    ref.set({'chat_title': chat_title})

def delete_group(chat_id):
    ref = db.reference(f'group_chats/{chat_id}')
    ref.delete()

def load_groups():
    global group_chats
    ref = db.reference('group_chats')
    data = ref.get() or {}
    group_chats = {int(k): v['chat_title'] for k, v in data.items()}
    logging.info(f"گروه‌ها بارگذاری شدند: {group_chats}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("سلام! من مدیر گروه هستم 😎")

async def restrict_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    chat_id = chat.id
    user_id = update.effective_user.id

    # ذخیره نام و شناسهٔ گروه در group_chats
    if chat.type in ['group', 'supergroup']:
        if chat_id not in group_chats:
            group_chats[chat_id] = chat.title
            save_group(chat_id, chat.title)

    # اگر چت خصوصی است و کاربر در حالت پخش پیام است
    if chat.type == 'private':
        if 'broadcast' in context.user_data and context.user_data['broadcast']['state'] == 'waiting_message':
            selected_chats = context.user_data['broadcast']['selected_chats']
            # ارسال پیام دریافتی به گروه‌های انتخاب‌شده
            for target_chat_id in selected_chats:
                try:
                    await update.message.copy(chat_id=target_chat_id)
                except Exception as e:
                    logging.error(f"خطا در ارسال پیام به گروه {target_chat_id}: {e}")
            await update.message.reply_text("✅ پیام شما به گروه‌های انتخاب‌شده ارسال شد.")
            del context.user_data['broadcast']
            return  # ادامه ندهید

    if chat.type in ['group', 'supergroup']:
        # اگر کاربر در AUTHORIZED_USERS است، محدودیت‌ها را اعمال نکن
        if user_id in AUTHORIZED_USERS:
            return

        # بررسی وضعیت کاربر
        try:
            chat_member = await context.bot.get_chat_member(chat_id, user_id)
            user_status = chat_member.status
        except Exception as e:
            logging.error(f"خطا در دریافت وضعیت کاربر: {e}")
            return

        # اگر کاربر ادمین یا سازنده است، محدودیت‌ها را اعمال نکن
        if user_status in ['creator', 'administrator']:
            return

        current_time = datetime.now(toronto_tz)
        current_hour = current_time.hour
        today = current_time.date()

        if not (9 <= current_hour < 21):
            try:
                await update.message.delete()
            except Exception as e:
                logging.error(f"خطا در حذف پیام کاربر: {e}")
            await handle_violation(update, context, violation_type="time")
            return

        # بررسی اینکه آیا کاربر امروز پیام ارسال کرده است
        last_message_date = user_last_message.get(user_id)
        if last_message_date == today:
            try:
                await update.message.delete()
            except Exception as e:
                logging.error(f"خطا در حذف پیام کاربر: {e}")
            await handle_violation(update, context, violation_type="message_limit")
            return

        # ثبت ارسال پیام توسط کاربر
        user_last_message[user_id] = today
        user_violations[user_id] = (0, today)
        user_last_error[user_id] = None

async def handle_violation(update: Update, context: ContextTypes.DEFAULT_TYPE, violation_type):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id  # رفع خطا: افزودن مقدار به متغیر chat_id
    current_time = datetime.now(toronto_tz)
    today = current_time.date()

    violation_messages = {
        "time": f"{update.effective_user.mention_html()} عزیز \n⏳ ارسال پیام در این گروه فقط از ساعت ۹ صبح تا ۹ شب به وقت تورنتو مجاز است.",
        "message_limit": f"{update.effective_user.mention_html()} 🚫 شما فقط یک بار در روز می‌توانید پیام بفرستید!",
        "muted": f"{update.effective_user.mention_html()} 🚫 به دلیل رعایت نکردن قوانین، شما تا\n{int(MUTE_DURATION.total_seconds() // 3600)} ساعت آینده\n نمی‌توانید پیام ارسال کنید.",
        "add_bot": f"{update.effective_user.mention_html()} 🚫 فقط ادمین‌ها می‌توانند ربات اضافه کنند."
    }

    last_error_time = user_last_error.get(user_id)
    time_since_last_error = (current_time - last_error_time).total_seconds() if last_error_time else None

    if not last_error_time or time_since_last_error > 30:
        try:
            error_message = await context.bot.send_message(
                chat_id=chat_id,
                text=violation_messages[violation_type],
                parse_mode="HTML",
                disable_notification=True
            )
            asyncio.create_task(delete_message_after_delay(error_message, 7))
        except Exception as e:
            logging.error(f"خطا در ارسال پیام تخلف: {e}")
        user_last_error[user_id] = current_time

    await register_violation(update, context, today)

async def register_violation(update: Update, context: ContextTypes.DEFAULT_TYPE, today):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    violations_info = user_violations.get(user_id, (0, today))
    violations, last_violation_date = violations_info

    if last_violation_date != today:
        # اگر روز جدید است، شمارش اخطارها را ریست کن
        violations = 1
        last_violation_date = today
    else:
        violations += 1

    user_violations[user_id] = (violations, last_violation_date)

    if violations >= MAX_VIOLATIONS:
        until_date = datetime.now(toronto_tz) + MUTE_DURATION
        try:
            await context.bot.restrict_chat_member(
                chat_id=chat_id,
                user_id=user_id,
                permissions=ChatPermissions(can_send_messages=False),
                until_date=until_date
            )
            muted_users[user_id] = until_date
            try:
                mute_message = await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"{update.effective_user.mention_html()} 🚫 \nبه دلیل رعایت نکردن قوانین، شما تا {int(MUTE_DURATION.total_seconds() // 3600)} ساعت آینده\n نمی‌توانید پیام ارسال کنید.",
                    parse_mode="HTML",
                    disable_notification=True
                )
                asyncio.create_task(delete_message_after_delay(mute_message, 7))
            except Exception as e:
                logging.error(f"خطا در ارسال پیام بی‌صدا کردن: {e}")
        except Exception as e:
            logging.error(f"خطا در اعمال محدودیت کاربر: {e}")
        # پس از بی‌صدا کردن، شمارش اخطارها را ریست کن
        user_violations[user_id] = (0, today)
        user_last_error[user_id] = None

async def delete_message_after_delay(message, delay):
    await asyncio.sleep(delay)
    try:
        await message.delete()
    except Exception as e:
        logging.error(f"خطا در حذف پیام پس از تأخیر: {e}")

# بقیه کد بدون تغییر ...

def main():
    # بارگذاری گروه‌ها از Firebase
    load_groups()

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("unmute", lift_restriction))
    app.add_handler(CommandHandler("broadcast", broadcast_command))
    app.add_handler(CallbackQueryHandler(broadcast_callback))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, restrict_messages))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, check_bot_addition))
    app.add_handler(ChatMemberHandler(track_group_changes, ChatMemberHandler.MY_CHAT_MEMBER))

    # زمان ریست: ساعت 00:00 به وقت تورنتو
    reset_time = time(hour=0, minute=0, tzinfo=toronto_tz)
    app.job_queue.run_daily(reset_violations, time=reset_time)

    print("✅ ربات در حال اجرا است...")
    app.run_polling()

if __name__ == "__main__":
    main()
