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
        # تنظیم مجوزها بدون پارامتر مشکل‌دار
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
