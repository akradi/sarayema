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
import base64
import firebase_admin
from firebase_admin import credentials, db

logging.basicConfig(level=logging.INFO)
TOKEN = os.getenv("TOKEN")

# لیست شناسه‌های کاربری مجاز
AUTHORIZED_USERS = [27905383]  # شناسه‌های عددی خود و کاربران دیگر را جایگزین کنید

user_last_message = {}
user_violations = {}
user_last_error = {}
muted_users = {}
group_chats = {}

MAX_VIOLATIONS = 3
MUTE_DURATION = timedelta(hours=1)

# منطقه زمانی تورنتو
toronto_tz = ZoneInfo('America/Toronto')

# تنظیمات Firebase
firebase_credentials_b64 = os.getenv('FIREBASE_CREDENTIALS_B64')
firebase_database_url = os.getenv('FIREBASE_DATABASE_URL')

if not (TOKEN and firebase_credentials_b64 and firebase_database_url):
    logging.error("یکی از متغیرهای محیطی TOKEN، FIREBASE_CREDENTIALS_B64 یا FIREBASE_DATABASE_URL تنظیم نشده است.")
    exit(1)

firebase_credentials_json = base64.b64decode(firebase_credentials_b64).decode('utf-8')
cred = credentials.Certificate(json.loads(firebase_credentials_json))
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

async def lift_restriction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    # بررسی اینکه کاربر ادمین است یا خیر
    chat_member = await context.bot.get_chat_member(chat_id, user_id)
    if chat_member.status not in ['creator', 'administrator']:
        await update.message.reply_text("🚫 شما مجوز لازم برای لغو محدودیت کاربران را ندارید.")
        return

    # بررسی اینکه آیا پیام به یک پیام کاربر ریپلای شده است یا خیر
    if update.message.reply_to_message:
        target_user_id = update.message.reply_to_message.from_user.id
    elif context.args:
        try:
            target_user_id = int(context.args[0])
        except ValueError:
            await update.message.reply_text("❗ شناسه کاربر نامعتبر است.")
            return
    else:
        await update.message.reply_text("❗ لطفاً به پیام کاربر پاسخ دهید یا شناسه عددی کاربر را وارد کنید.")
        return

    try:
        permissions = ChatPermissions(
            can_send_messages=True,
            can_send_media_messages=True,
            can_send_polls=True,
            can_send_other_messages=True,
            can_add_web_page_previews=True,
            can_change_info=False,
            can_invite_users=True,
            can_pin_messages=False
        )
        await context.bot.restrict_chat_member(
            chat_id=chat_id,
            user_id=target_user_id,
            permissions=permissions
        )
        await update.message.reply_text("✅ محدودیت کاربر برداشته شد.")
    except Exception as e:
        await update.message.reply_text(f"❌ خطا در لغو محدودیت کاربر: {e}")

# سایر توابع مربوط به ربات (restrict_messages، handle_violation، register_violation و غیره)
# لطفاً اطمینان حاصل کنید که این توابع نیز در کد شما وجود دارند.

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
