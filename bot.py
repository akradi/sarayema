from telegram import Update, ChatPermissions
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from datetime import datetime, timedelta
import pytz

# تعریف منطقه زمانی تورنتو
toronto_tz = pytz.timezone("America/Toronto")

# ذخیره کاربران بی‌صدا شده
muted_users = {}

async def mute_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_status = await context.bot.get_chat_member(chat_id, update.effective_user.id)
    
    if user_status.status not in ['creator', 'administrator']:
        await update.message.reply_text("🚫 شما اجازه بی‌صدا کردن کاربران را ندارید.")
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
    
    muted_users[user_id] = datetime.now(toronto_tz)
    await context.bot.restrict_chat_member(chat_id, user_id, ChatPermissions())
    await update.message.reply_text(f"🔇 کاربر {user_id} بی‌صدا شد.")

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
    
    permissions = ChatPermissions(
        can_send_messages=True,
        can_send_media_messages=True,
        can_send_polls=True,
        can_send_other_messages=True,
        can_add_web_page_previews=True,
        can_invite_users=True
    )
    
    await context.bot.restrict_chat_member(chat_id=chat_id, user_id=user_id, permissions=permissions)
    muted_users.pop(user_id, None)
    await update.message.reply_text(f"✅ محدودیت کاربر {user_id} برداشته شد.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    now = datetime.now(toronto_tz)
    
    if not (9 <= now.hour < 21):
        await update.message.delete()
        return
    
    last_message_time = muted_users.get(user_id)
    if last_message_time and now - last_message_time < timedelta(days=1):
        await update.message.delete()
        return
    
    muted_users[user_id] = now

app = Application.builder().token("7464967230:AAEyFh1o_whGxXCoKdZGrGKFDsvasK6n7-4").build()
app.add_handler(CommandHandler("mute", mute_user))
app.add_handler(CommandHandler("unmute", lift_restriction))
app.add_handler(MessageHandler(filters.ALL, handle_message))

app.run_polling()
