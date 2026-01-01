import html

from telegram import Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes, filters
from telegram.constants import ChatType
from telegram.helpers import mention_html

from tg_bot import application, BAN_STICKER, LOGGER
from tg_bot.modules.helper_funcs.chat_status import bot_admin, user_admin, is_user_ban_protected, can_restrict, \
    is_user_admin, is_user_in_chat
from tg_bot.modules.helper_funcs.extraction import extract_user_and_text, extract_user_and_text_and_is_channel
from tg_bot.modules.helper_funcs.string_handling import extract_time
from tg_bot.modules.helper_funcs.handlers import create_handler
from tg_bot.modules.log_channel import loggable


@bot_admin
@can_restrict
@user_admin
@loggable
async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    args = context.args
    chat = update.effective_chat
    user = update.effective_user
    message = update.effective_message

    user_id, reason, is_channel = await extract_user_and_text_and_is_channel(message, args)

    if not is_channel:
        if not user_id:
            await message.reply_text("You don't seem to be referring to a user.")
            return ""

        try:
            member = await chat.get_member(user_id)
        except BadRequest as excp:
            if excp.message == "User not found":
                await message.reply_text("I can't seem to find this user")
                return ""
            else:
                raise

        if await is_user_ban_protected(chat, user_id, context, member):
            await message.reply_text("I really wish I could ban admins...")
            return ""

        if user_id == context.bot.id:
            await message.reply_text("I'm not gonna BAN myself, are you crazy?")
            return ""

        log = "<b>{}:</b>" \
              "\n#BANNED" \
              "\n<b>Admin:</b> {}" \
              "\n<b>User:</b> {} (<code>{}</code>)".format(html.escape(chat.title),
                                                           mention_html(user.id, user.first_name),
                                                           mention_html(member.user.id, member.user.first_name),
                                                           member.user.id)
        if reason:
            log += "\n<b>Reason:</b> {}".format(reason)

        try:
            await chat.ban_member(user_id)
            await context.bot.send_sticker(chat.id, BAN_STICKER)
            await message.reply_text("#бан_банан 🍌")
            return log

        except BadRequest as excp:
            if excp.message == "Reply message not found":
                # Do not reply
                await message.reply_text('Banned!', quote=False)
                return log
            else:
                LOGGER.warning(update)
                LOGGER.exception("ERROR banning user %s in chat %s (%s) due to %s", user_id, chat.title, chat.id,
                                 excp.message)
                await message.reply_text("Well damn, I can't ban that user.")
    else:
        log = "<b>{}:</b>" \
              "\n#BANNED" \
              "\n<b>Admin:</b> {}" \
              "\n<b>User:</b> {} (<code>{}</code>)".format(html.escape(chat.title),
                                                           mention_html(user.id, user.first_name),
                                                           mention_html(user_id, str(user_id)),
                                                           user_id)
        if reason:
            log += "\n<b>Reason:</b> {}".format(reason)

        try:
            await chat.ban_sender_chat(user_id)
            await context.bot.send_sticker(chat.id, BAN_STICKER)
            await message.reply_text("#бан_банан 🍌")
            return log

        except BadRequest as excp:
            if excp.message == "Reply message not found":
                # Do not reply
                await message.reply_text('Banned!', quote=False)
                return log
            else:
                LOGGER.warning(update)
                LOGGER.exception("ERROR banning user %s in chat %s (%s) due to %s", user_id, chat.title, chat.id,
                                 excp.message)
                await message.reply_text("Well damn, I can't ban that user.")

    return ""


@bot_admin
@can_restrict
@user_admin
@loggable
async def temp_ban(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    args = context.args
    chat = update.effective_chat
    user = update.effective_user
    message = update.effective_message

    user_id, reason = await extract_user_and_text(message, args)

    if not user_id:
        await message.reply_text("You don't seem to be referring to a user.")
        return ""

    try:
        member = await chat.get_member(user_id)
    except BadRequest as excp:
        if excp.message == "User not found":
            await message.reply_text("I can't seem to find this user")
            return ""
        else:
            raise

    if await is_user_ban_protected(chat, user_id, context, member):
        await message.reply_text("I really wish I could ban admins...")
        return ""

    if user_id == context.bot.id:
        await message.reply_text("I'm not gonna BAN myself, are you crazy?")
        return ""

    if not reason:
        await message.reply_text("You haven't specified a time to ban this user for!")
        return ""

    split_reason = reason.split(None, 1)

    time_val = split_reason[0].lower()
    if len(split_reason) > 1:
        reason = split_reason[1]
    else:
        reason = ""

    bantime = await extract_time(message, time_val)

    if not bantime:
        # extract_time already sends error message to user
        return ""

    log = "<b>{}:</b>" \
          "\n#TEMP BANNED" \
          "\n<b>Admin:</b> {}" \
          "\n<b>User:</b> {} (<code>{}</code>)" \
          "\n<b>Time:</b> {}".format(html.escape(chat.title),
                                     mention_html(user.id, user.first_name),
                                     mention_html(member.user.id, member.user.first_name),
                                     member.user.id,
                                     time_val)
    if reason:
        log += "\n<b>Reason:</b> {}".format(reason)

    try:
        await chat.ban_member(user_id, until_date=bantime)
        await context.bot.send_sticker(chat.id, BAN_STICKER)  # banhammer marie sticker
        await message.reply_text("#бан_банан 🍌! Пользователь будет забанен на протяжении {}.".format(time_val))
        return log

    except BadRequest as excp:
        if excp.message == "Reply message not found":
            # Do not reply
            await message.reply_text("Banned! User will be banned for {}.".format(time_val), quote=False)
            return log
        else:
            LOGGER.warning(update)
            LOGGER.exception("ERROR banning user %s in chat %s (%s) due to %s", user_id, chat.title, chat.id,
                             excp.message)
            await message.reply_text("Well damn, I can't ban that user.")

    return ""


@bot_admin
@can_restrict
@user_admin
@loggable
async def kick(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    args = context.args
    chat = update.effective_chat
    user = update.effective_user
    message = update.effective_message

    user_id, reason = await extract_user_and_text(message, args)

    if not user_id:
        return ""

    try:
        member = await chat.get_member(user_id)
    except BadRequest as excp:
        if excp.message == "User not found":
            await message.reply_text("I can't seem to find this user")
            return ""
        else:
            raise

    if await is_user_ban_protected(chat, user_id, context, member):
        await message.reply_text("I really wish I could kick admins...")
        return ""

    if user_id == context.bot.id:
        await message.reply_text("Yeahhh I'm not gonna do that")
        return ""

    log = "<b>{}:</b>" \
          "\n#KICKED" \
          "\n<b>Admin:</b> {}" \
          "\n<b>User:</b> {} (<code>{}</code>)".format(html.escape(chat.title),
                                                       mention_html(user.id, user.first_name),
                                                       mention_html(member.user.id, member.user.first_name),
                                                       member.user.id)
    if reason:
        log += "\n<b>Reason:</b> {}".format(reason)

    if chat.type == ChatType.GROUP:
        await chat.ban_member(user_id)
    else:
        res = await chat.unban_member(user_id)
        if not res:
            await message.reply_text("Well damn, I can't kick that user.")
            return ""

    await context.bot.send_sticker(chat.id, BAN_STICKER)
    await message.reply_text("Kicked!")
    return log


@bot_admin
@can_restrict
async def kickme(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_message.from_user.id
    chat = update.effective_chat
    
    if await is_user_admin(chat, user_id, context):
        await update.effective_message.reply_text("I wish I could... but you're an admin.")
        return

    try:
        if chat.type == ChatType.GROUP:
            # В обычных группах unban_member не работает, используем ban_member для удаления
            await chat.ban_member(user_id)
        else:
            # В супергруппах/каналах unban_member удаляет пользователя без добавления в черный список
            res = await chat.unban_member(user_id)
            if not res:
                await update.effective_message.reply_text("Huh? I can't :/")
                return
        
        await update.effective_message.reply_text("No problem.")
    except BadRequest:
        await update.effective_message.reply_text("Huh? I can't :/")



@bot_admin
@can_restrict
@user_admin
@loggable
async def unban(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    args = context.args
    message = update.effective_message
    user = update.effective_user
    chat = update.effective_chat

    user_id, reason, is_channel = await extract_user_and_text_and_is_channel(message, args)

    if not is_channel:
        if not user_id:
            return ""

        try:
            member = await chat.get_member(user_id)
        except BadRequest as excp:
            if excp.message == "User not found":
                await message.reply_text("I can't seem to find this user")
                return ""
            else:
                raise

        if user_id == context.bot.id:
            await message.reply_text("How would I unban myself if I wasn't here...?")
            return ""

        if await is_user_in_chat(chat, user_id, context):
            await message.reply_text("Why are you trying to unban someone that's already in the chat?")
            return ""

        if chat.type == ChatType.GROUP:
            await message.reply_text("Unban is not available for regular groups. Please invite the user back manually using an invite link.")
            return ""

        await chat.unban_member(user_id)
        await message.reply_text("Yep, this user can join!")

        log = "<b>{}:</b>" \
              "\n#UNBANNED" \
              "\n<b>Admin:</b> {}" \
              "\n<b>User:</b> {} (<code>{}</code>)".format(html.escape(chat.title),
                                                           mention_html(user.id, user.first_name),
                                                           mention_html(member.user.id, member.user.first_name),
                                                           member.user.id)
        if reason:
            log += "\n<b>Reason:</b> {}".format(reason)
        return log
    else:
        log = "<b>{}:</b>" \
              "\n#UNBANNED" \
              "\n<b>Admin:</b> {}" \
              "\n<b>User:</b> {} (<code>{}</code>)".format(html.escape(chat.title),
                                                           mention_html(user.id, user.first_name),
                                                           mention_html(user_id, str(user_id)),
                                                           user_id)
        if reason:
            log += "\n<b>Reason:</b> {}".format(reason)

        try:
            await chat.unban_sender_chat(user_id)
            await message.reply_text("Yep, this user can join!")
            return log

        except BadRequest as excp:
            if excp.message == "Reply message not found":
                # Do not reply
                await message.reply_text("Unbanned!", quote=False)
                return log
            else:
                LOGGER.warning(update)
                LOGGER.exception("ERROR unbanning channel %s in chat %s (%s) due to %s", user_id, chat.title, chat.id,
                                 excp.message)
                await message.reply_text("Well damn, I can't unban that channel.")

    return ""


__help__ = r"""
 \- /kickme: удаляет из чата пользователя, давшего команду

*Только администратор:*
 \- /ban \<имя пользователя\>: забанить пользователя \(удалить из чата и отправить в чёрный список\)\. \(через имя пользователя или ответ\)
 \- /tban \<имя пользователя\> x\(m/h/d\): банит пользователя на x минут/часов/дней\. \(через имя пользователя или ответ\)\. m \= минуты, h \= часы, d \= дни\.
 \- /unban \<имя пользователя\>: разбанить пользователя\. \(через имя пользователя или ответ\)
 \- /kick \<имя пользователя\>: удаляет пользователя из чата \(через имя пользователя или ответ\)
"""

__mod_name__ = "Баны"

BAN_HANDLER = create_handler("ban", ban, filters=filters.ChatType.GROUPS)
TEMPBAN_HANDLER = create_handler(["tban", "tempban"], temp_ban, filters=filters.ChatType.GROUPS)
KICK_HANDLER = create_handler("kick", kick, filters=filters.ChatType.GROUPS)
UNBAN_HANDLER = create_handler("unban", unban, filters=filters.ChatType.GROUPS)
KICKME_HANDLER = create_handler("kickme", kickme, filters=filters.ChatType.GROUPS)

application.add_handler(BAN_HANDLER)
application.add_handler(TEMPBAN_HANDLER)
application.add_handler(KICK_HANDLER)
application.add_handler(UNBAN_HANDLER)
application.add_handler(KICKME_HANDLER)
