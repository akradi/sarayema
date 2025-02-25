from telegram import Update, ChatPermissions
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo
import asyncio
import logging

logging.basicConfig(level=logging.INFO)
TOKEN = "7464967230:AAEyFh1o_whGxXCoKdZGrGKFDsvasK6n7-4"

user_last_message = {}
user_violations = {}
user_last_error = {}
muted_users = {}

MAX_VIOLATIONS = 3
MUTE_DURATION = timedelta(hours=1)

# منطقه زمانی تورنتو
toronto_tz = ZoneInfo('America/Toronto')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("سلام! من مدیر گروه هستم 😎")

async def restrict_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    try:
        chat_member = await context.bot.get_chat_member(chat_id, user_id)
        user_status = chat_member.status
    except Exception as e:
        logging.error(f"خطا در دریافت وضعیت کاربر: {e}")
        return

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

    # بررسی تعداد پیام‌های ارسالی در روز
    last_message_date = user_last_message.get(user_id)
    if last_message_date == today:
        try:
            await update.message.delete()
        except Exception as e:
            logging.error(f"خطا در حذف پیام کاربر: {e}")
        await handle_violation(update, context, violation_type="message_limit")
        return

    user_last_message[user_id] = today
    user_violations[user_id] = (0, today)
    user_last_error[user_id] = None

async def handle_violation(update: Update, context: ContextTypes.DEFAULT_TYPE, violation_type):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    current_time = datetime.now(toronto_tz)
    today = current_time.date()

    violation_messages = {
        "time": f"{update.effective_user.mention_html()} عزیز \n⏳ ارسال پیام در این گروه فقط از ساعت ۹ صبح تا ۹ شب به وقت تورنتو مجاز است.",
        "message_limit": f"{update.effective_user.mention_html()} 🚫 شما فقط یک بار در روز می‌توانید پیام بفرستید!",
        "muted": f"{update.effective_user.mention_html()} 🚫 به دلیل رعایت نکردن قوانین، شما تا\n {int(MUTE_DURATION.total_seconds() // 3600)} ساعت آینده\n نمی‌توانید پیام ارسال کنید.",
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
            logging.error(f"خطا در ارسال پیام خطا: {e}")
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
            logging.error(f"خطا در بی‌صدا کردن کاربر: {e}")
        # پس از مسدودسازی، شمارش اخطارها را ریست کن
        user_violations[user_id] = (0, today)
        user_last_error[user_id] = None

async def delete_message_after_delay(message, delay):
    await asyncio.sleep(delay)
    try:
        await message.delete()
    except Exception as e:
        logging.error(f"خطا در حذف پیام پس از تأخیر: {e}")

async def lift_restriction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_status = await context.bot.get_chat_member(chat_id, update.effective_user.id)
    if user_status.status not in ['creator', 'administrator']:
        await update.message.reply_text("🚫 شما مجوز لازم برای لغو محدودیت کاربران را ندارید.")
        return

    if update.message.reply_to_message:
        user_id = update.message.reply_to_message.from_user.id
    elif context.args:
        try:
            user_id = int(context.args[0])
        except ValueError:
            await update.message.reply_text("❗ شناسه کاربر نامعتبر است.")
            return
    else:
        await update.message.reply_text("❗ لطفاً به پیام کاربر ریپلای کنید یا شناسه عددی کاربر را وارد کنید.")
        return

    try:
        permissions = ChatPermissions(
            can_send_messages=True,
            can_send_polls=True,
            can_send_other_messages=True,
            can_add_web_page_previews=True,
            can_invite_users=True,
            can_change_info=False,
            can_pin_messages=False
        )
        await context.bot.restrict_chat_member(
            chat_id=chat_id,
            user_id=user_id,
            permissions=permissions
        )
        if user_id in muted_users:
            del muted_users[user_id]
        await update.message.reply_text(f"✅ محدودیت کاربر برداشته شد.")
    except Exception as e:
        await update.message.reply_text(f"❌ خطا در لغو محدودیت کاربر: {e}")

async def check_bot_addition(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    new_members = update.message.new_chat_members

    for member in new_members:
        if member.is_bot:
            adder_id = update.message.from_user.id
            try:
                adder_status = await context.bot.get_chat_member(chat_id, adder_id)
                if adder_status.status not in ['creator', 'administrator']:
                    try:
                        await context.bot.ban_chat_member(chat_id, member.id)
                        await context.bot.unban_chat_member(chat_id, member.id)
                        await handle_violation(update, context, violation_type="add_bot")
                    except Exception as e:
                        logging.error(f"خطا در حذف ربات اضافه‌شده: {e}")
            except Exception as e:
                logging.error(f"خطا در بررسی وضعیت اضافه‌کننده: {e}")

def reset_violations(context: ContextTypes.DEFAULT_TYPE):
    user_violations.clear()
    logging.info("شمارش اخطارها ریست شد.")

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("unmute", lift_restriction))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, restrict_messages))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, check_bot_addition))

    # تنظیم منطقه زمانی
    toronto_tz = ZoneInfo('America/Toronto')

    # زمان ریست: ساعت 00:00 به وقت تورنتو
    reset_time = time(hour=0, minute=0, tzinfo=toronto_tz)

    # افزودن وظیفه زمان‌بندی‌شده
    app.job_queue.run_daily(reset_violations, time=reset_time)

    print("✅ ربات در حال اجرا است...")
    app.run_polling()

if __name__ == "__main__":
    main()
