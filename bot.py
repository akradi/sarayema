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
        "time": f"{update.effective_user.mention_html()} ⏳ ارسال پیام فقط از ساعت 9 صبح تا 9 شب (به وقت تورنتو) مجاز است.",
        "message_limit": f"{update.effective_user.mention_html()} 🚫 شما فقط یک بار در روز می‌توانید پیام بفرستید!",
        "muted": f"{update.effective_user.mention_html()} 🚫 به دلیل رعایت نکردن قوانین، شما تا {int(MUTE_DURATION.total_seconds() // 3600)} ساعت آینده نمی‌توانید پیام ارسال کنید.",
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
            # حذف پیام خطا بعد از 10 ثانیه
            asyncio.create_task(delete_message_after_delay(error_message, 10))
        except Exception as e:
            logging.error(f"خطا در ارسال پیام خطا: {e}")

        # به‌روزرسانی زمان آخرین پیام خطا
        user_last_error[user_id] = datetime.now()

    # ثبت نقض کاربر
    await register_violation(update, context)

async def register_violation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    # افزایش تعداد نقض‌های کاربر
    user_violations[user_id] = user_violations.get(user_id, 0) + 1

    if user_violations[user_id] >= MAX_VIOLATIONS:
        # بی‌صدا کردن کاربر به مدت تعیین‌شده
        until_date = datetime.now() + MUTE_DURATION
        try:
            await context.bot.restrict_chat_member(
                chat_id=chat_id,
                user_id=user_id,
                permissions=ChatPermissions(can_send_messages=False),
                until_date=until_date
            )
            # ذخیره اطلاعات کاربر بی‌صدا شده
            muted_users[user_id] = until_date

            # ارسال پیام اطلاع‌رسانی به کاربر (سایلنت)
            try:
                mute_message = await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"{update.effective_user.mention_html()} 🚫 به دلیل رعایت نکردن قوانین، شما تا {int(MUTE_DURATION.total_seconds() // 3600)} ساعت آینده نمی‌توانید پیام ارسال کنید.",
                    parse_mode="HTML",
                    disable_notification=True
                )
                # حذف پیام اطلاع‌رسانی بعد از 10 ثانیه
                asyncio.create_task(delete_message_after_delay(mute_message, 10))
            except Exception as e:
                logging.error(f"خطا در ارسال پیام بی‌صدا کردن: {e}")
        except Exception as e:
            logging.error(f"خطا در بی‌صدا کردن کاربر: {e}")

        # ریست کردن تعداد نقض‌های کاربر
        user_violations[user_id] = 0
        user_last_error[user_id] = None

async def delete_message_after_delay(message, delay):
    await asyncio.sleep(delay)
    try:
        await message.delete()
    except Exception as e:
        logging.error(f"خطا در حذف پیام پس از تأخیر: {e}")

# افزودن تابع لغو محدودیت
async def lift_restriction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    # بررسی اینکه کاربر استفاده‌کننده ادمین است یا نه
    user_status = await context.bot.get_chat_member(chat_id, update.effective_user.id)
    if user_status.status not in ['creator', 'administrator']:
        await update.message.reply_text("🚫 شما مجوز لازم برای لغو محدودیت کاربران را ندارید.")
        return

    # دریافت شناسه کاربری که قرار است محدودیتش لغو شود
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
        # تنظیم مجوزها
        permissions = ChatPermissions(
            can_send_messages=True,
            can_send_polls=True,
            can_send_other_messages=True,
            can_add_web_page_previews=True,
            can_invite_users=True,
            can_change_info=False,
            can_pin_messages=False
        )

        # لغو محدودیت کاربر
        await context.bot.restrict_chat_member(
            chat_id=chat_id,
            user_id=user_id,
            permissions=permissions
        )

        # حذف کاربر از لیست بی‌صدا شده‌ها
        if user_id in muted_users:
            del muted_users[user_id]

        await update.message.reply_text(f"✅ محدودیت کاربر برداشته شد.")
    except Exception as e:
        await update.message.reply_text(f"❌ خطا در لغو محدودیت کاربر: {e}")

# افزودن تابع برای جلوگیری از اضافه کردن ربات توسط کاربران غیر ادمین
async def check_bot_addition(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    new_members = update.message.new_chat_members

    for member in new_members:
        if member.is_bot:
            adder_id = update.message.from_user.id

            # بررسی اینکه کاربر اضافه‌کننده ادمین است یا نه
            try:
                adder_status = await context.bot.get_chat_member(chat_id, adder_id)
                if adder_status.status not in ['creator', 'administrator']:
                    # حذف ربات جدید
                    try:
                        await context.bot.ban_chat_member(chat_id, member.id)
                        await context.bot.unban_chat_member(chat_id, member.id)

                        # ارسال پیام خطا به کاربر
                        violation_type = "add_bot"
                        await handle_violation(update, context, violation_type)
                    except Exception as e:
                        logging.error(f"خطا در حذف ربات اضافه‌شده: {e}")
            except Exception as e:
                logging.error(f"خطا در بررسی وضعیت اضافه‌کننده: {e}")

def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("unmute", lift_restriction))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, restrict_messages))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, check_bot_addition))

    print("✅ ربات در حال اجرا است...")
    app.run_polling()

if __name__ == "__main__":
    main()
