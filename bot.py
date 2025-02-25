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

logging.basicConfig(level=logging.INFO)
TOKEN = "7464967230:AAEyFh1o_whGxXCoKdZGrGKFDsvasK6n7-4"

# لیست شناسه‌های کاربری مجاز (شناسه عددی تلگرام شما)
AUTHORIZED_USERS = [27905383]  # شناسه عددی خود و کاربران دیگر را جایگزین کنید

user_last_message = {}
user_violations = {}
user_last_error = {}
muted_users = {}
group_chats = {}  # دیکشنری از شناسهٔ گروه‌ها به نام آن‌ها

MAX_VIOLATIONS = 3
MUTE_DURATION = timedelta(hours=1)

# منطقه زمانی تورنتو
toronto_tz = ZoneInfo('America/Toronto')

GROUPS_FILE = 'groups.json'

def load_groups():
    global group_chats
    if os.path.exists(GROUPS_FILE):
        with open(GROUPS_FILE, 'r') as f:
            group_chats = json.load(f)
            # تبدیل کلیدها به اعداد صحیح
            group_chats = {int(k): v for k, v in group_chats.items()}
    else:
        group_chats = {}

def save_groups():
    with open(GROUPS_FILE, 'w') as f:
        json.dump(group_chats, f)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("سلام! من مدیر گروه هستم 😎")

async def restrict_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    chat_id = chat.id
    user_id = update.effective_user.id

    # ذخیره نام و شناسهٔ گروه در دیکشنری گروه‌ها
    if chat.type in ['group', 'supergroup']:
        if chat_id not in group_chats:
            group_chats[chat_id] = chat.title
            save_groups()

    # بررسی اینکه آیا کاربر در حالت ارسال پیام برای پخش است
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

    # اگر کاربر در لیست کاربران مجاز است، محدودیت‌ها را اعمال نکن
    if user_id in AUTHORIZED_USERS:
        return

    # بررسی وضعیت کاربر
    try:
        chat_member = await context.bot.get_chat_member(chat_id, user_id)
        user_status = chat_member.status
    except Exception as e:
        logging.error(f"خطا در دریافت وضعیت کاربر: {e}")
        return

    # اگر کاربر ادمین یا سازنده گروه است، محدودیت‌ها را اعمال نکن
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

async def track_group_changes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    chat_id = chat.id

    new_status = update.my_chat_member.new_chat_member.status

    if new_status in ['member', 'administrator']:
        # ربات به گروه اضافه شده است
        group_chats[chat_id] = chat.title
        save_groups()
        logging.info(f"Added to group {chat.title} (ID: {chat_id})")
    elif new_status in ['kicked', 'left']:
        # ربات از گروه حذف شده است
        if chat_id in group_chats:
            del group_chats[chat_id]
            save_groups()
            logging.info(f"Removed from group {chat.title} (ID: {chat_id})")

def reset_violations(context: ContextTypes.DEFAULT_TYPE):
    user_violations.clear()
    logging.info("شمارش اخطارها ریست شد.")

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in AUTHORIZED_USERS:
        await update.message.reply_text("🚫 شما مجوز لازم برای استفاده از این فرمان را ندارید.")
        return

    if not group_chats:
        await update.message.reply_text("❗ هیچ گروهی برای ارسال وجود ندارد.")
        return

    # ساختن کلیدهای تعاملی برای انتخاب گروه‌ها
    keyboard = []
    for chat_id, chat_title in group_chats.items():
        keyboard.append([InlineKeyboardButton(chat_title, callback_data=f"toggle_{chat_id}")])
    keyboard.append([InlineKeyboardButton("✅ ارسال به گروه‌های انتخاب‌شده", callback_data="confirm")])
    keyboard.append([InlineKeyboardButton("🔘 انتخاب همه", callback_data="select_all"), InlineKeyboardButton("⚪ لغو انتخاب همه", callback_data="deselect_all")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    context.user_data['broadcast'] = {
        'state': 'selecting_chats',
        'selected_chats': set()
    }

    await update.message.reply_text("لطفاً گروه‌های مورد نظر را انتخاب کنید:", reply_markup=reply_markup)

async def broadcast_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if 'broadcast' not in context.user_data or context.user_data['broadcast']['state'] != 'selecting_chats':
        await query.edit_message_text("❗ زمان شما برای انتخاب گروه‌ها به پایان رسیده است.")
        return

    data = query.data
    user_data = context.user_data['broadcast']

    if data.startswith("toggle_"):
        chat_id = int(data.split("_")[1])
        if chat_id in user_data['selected_chats']:
            user_data['selected_chats'].remove(chat_id)
        else:
            user_data['selected_chats'].add(chat_id)
    elif data == "select_all":
        user_data['selected_chats'] = set(group_chats.keys())
    elif data == "deselect_all":
        user_data['selected_chats'].clear()
    elif data == "confirm":
        if not user_data['selected_chats']:
            await query.answer("❗ لطفاً حداقل یک گروه را انتخاب کنید.", show_alert=True)
            return
        user_data['state'] = 'waiting_message'
        await query.edit_message_text("✅ لطفاً پیام خود را ارسال کنید تا به گروه‌های انتخاب‌شده ارسال شود.")
        return

    # به‌روزرسانی کلیدهای تعاملی با وضعیت انتخاب‌ها
    keyboard = []
    for chat_id, chat_title in group_chats.items():
        if chat_id in user_data['selected_chats']:
            button_text = f"✅ {chat_title}"
        else:
            button_text = chat_title
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"toggle_{chat_id}")])

    keyboard.append([InlineKeyboardButton("✅ ارسال به گروه‌های انتخاب‌شده", callback_data="confirm")])
    keyboard.append([InlineKeyboardButton("🔘 انتخاب همه", callback_data="select_all"), InlineKeyboardButton("⚪ لغو انتخاب همه", callback_data="deselect_all")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_reply_markup(reply_markup=reply_markup)

def main():
    load_groups()
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("unmute", lift_restriction))
    app.add_handler(CommandHandler("broadcast", broadcast_command))
    app.add_handler(CallbackQueryHandler(broadcast_callback))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, restrict_messages))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, check_bot_addition))
    app.add_handler(ChatMemberHandler(track_group_changes, ChatMemberHandler.MY_CHAT_MEMBER))

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
