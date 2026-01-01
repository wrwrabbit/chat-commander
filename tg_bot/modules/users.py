from io import BytesIO
from time import sleep
from typing import Optional

from telegram import Chat, Message, Update
from telegram.error import BadRequest, TelegramError
from telegram.ext import MessageHandler, filters, ContextTypes
from telegram._messageorigin import MessageOriginUser

import tg_bot.modules.sql.users_sql as sql
from tg_bot import application, OWNER_ID, LOGGER
from tg_bot.modules.helper_funcs.filters import CustomFilters
from tg_bot.modules.helper_funcs.handlers import create_handler

USERS_GROUP = 4


async def get_user_id(username):
    # ensure valid userid
    if len(username) <= 5:
        return None

    if username.startswith('@'):
        username = username[1:]

    users = sql.get_userid_by_name(username)

    if not users:
        return None

    elif len(users) == 1:
        return users[0].user_id

    else:
        for user_obj in users:
            try:
                userdat = await application.bot.get_chat(user_obj.user_id)
                if userdat.username == username:
                    return userdat.id

            except BadRequest as excp:
                if excp.message == 'Chat not found':
                    pass
                else:
                    LOGGER.exception("Error extracting user ID")

    return None


async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    to_send = update.effective_message.text.split(None, 1)
    if len(to_send) >= 2:
        chats = sql.get_all_chats() or []
        failed = 0
        for chat in chats:
            try:
                await context.bot.send_message(int(chat.chat_id), to_send[1])
                sleep(0.1)
            except TelegramError:
                failed += 1
                LOGGER.warning("Couldn't send broadcast to %s, group name %s", str(chat.chat_id), str(chat.chat_name))

        await update.effective_message.reply_text("Broadcast complete. {} groups failed to receive the message, probably "
                                            "due to being kicked.".format(failed))


async def log_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await sql.ensure_bot_in_db(context.bot)
    
    chat = update.effective_chat  # type: Optional[Chat]
    msg = update.effective_message  # type: Optional[Message]
    is_channel = msg.sender_chat is not None
    if not is_channel:
        sql.update_user(msg.from_user.id, is_channel, msg.from_user.username, chat.id, chat.title)
    else:
        sql.update_user(msg.sender_chat.id, is_channel, msg.sender_chat.username, chat.id, chat.title)
    if msg.reply_to_message:
        repl_msg = msg.reply_to_message
        is_channel = repl_msg.sender_chat is not None
        if not is_channel:
            sql.update_user(repl_msg.from_user.id, is_channel, repl_msg.from_user.username, chat.id, chat.title)
        else:
            sql.update_user(repl_msg.sender_chat.id, is_channel, repl_msg.sender_chat.username, chat.id, chat.title)
    if msg.forward_origin:
        sql.update_user(msg.forward_origin.sender_user.id, False, msg.forward_origin.sender_user.username)


async def chats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    all_chats = sql.get_all_chats() or []
    chatfile = 'List of chats.\n'
    for chat in all_chats:
        chatfile += "{} - ({})\n".format(chat.chat_name, chat.chat_id)

    with BytesIO(str.encode(chatfile)) as output:
        output.name = "chatlist.txt"
        await update.effective_message.reply_document(document=output, filename="chatlist.txt",
                                                caption="Here is the list of chats in my database.")


def __user_info__(user_id, is_channel):
    num_chats = sql.get_user_num_chats(user_id, is_channel)
    return """I've seen them in <code>{}</code> chats in total.""".format(num_chats)


def __stats__():
    return "{} users, across {} chats".format(sql.num_users(), sql.num_chats())


def __gdpr__(user_id, is_channel):
    sql.del_user(user_id, is_channel)


def __migrate__(old_chat_id, new_chat_id):
    sql.migrate_chat(old_chat_id, new_chat_id)


__help__ = """
*SUDO администратор:*
    - /chatlist - присылает список всех чатов текст файлом.
*Владелец только:*
    - /broadcast <сообщение> - рассылка сообщения по всем чатам.
""" 

__mod_name__ = "Пользователи"

BROADCAST_HANDLER = create_handler("broadcast", broadcast, filters=filters.User(OWNER_ID))
USER_HANDLER = MessageHandler(filters.ALL & filters.ChatType.GROUPS, log_user)
CHATLIST_HANDLER = create_handler("chatlist", chats, filters=CustomFilters.sudo_filter)

application.add_handler(USER_HANDLER, USERS_GROUP)
application.add_handler(BROADCAST_HANDLER)
application.add_handler(CHATLIST_HANDLER)
