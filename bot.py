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
TOKEN = os.getenv("7464967230:AAEyFh1o_whGxXCoKdZGrGKFDsvasK6n7-4")

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

# تنظیمات Firebase
firebase_credentials = os.getenv('FIREBASE_CREDENTIALS')
cred = credentials.Certificate(json.loads(firebase_credentials))
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://your-project-id.firebaseio.com/'  # آدرس دیتابیس خود را وارد کنید
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
    chat_id =
