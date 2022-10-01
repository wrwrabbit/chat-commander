import html
from typing import Optional

from telegram import Message, Update, Bot, User
from telegram import ParseMode, MAX_MESSAGE_LENGTH
from telegram.utils.helpers import escape_markdown

import tg_bot.modules.sql.userinfo_sql as sql
from tg_bot import dispatcher, SUDO_USERS
from tg_bot.modules.disable import DisableAbleCommandHandler
from tg_bot.modules.helper_funcs.extraction import extract_user_and_is_channel
from tg_bot.modules.helper_funcs.chat_status import user_admin


# @run_async
def about_bio(bot: Bot, update: Update):
    args = update.effective_message.text.split(" ")[1:]
    message = update.effective_message  # type: Optional[Message]

    user_id, is_channel = extract_user_and_is_channel(message, args)
    if user_id:
        user = bot.get_chat(user_id)
    else:
        user = message.from_user

    info = sql.get_user_bio(user.id, is_channel)

    if info:
        update.effective_message.reply_text("*{}*:\n{}".format(user.first_name or user.username, escape_markdown(info)),
                                            parse_mode=ParseMode.MARKDOWN)
    elif message.reply_to_message:
        username = user.first_name or user.username
        update.effective_message.reply_text("{} hasn't had a message set about themselves yet!".format(username))
    else:
        update.effective_message.reply_text("You haven't had a bio set about yourself yet!")

@user_admin
# @run_async
def set_about_bio(bot: Bot, update: Update):
    message = update.effective_message  # type: Optional[Message]
    sender = update.effective_user  # type: Optional[User]
    if message.reply_to_message:
        repl_message = message.reply_to_message
        is_channel = repl_message.sender_chat is not None
        if not is_channel:
            user_id = repl_message.from_user.id
            if user_id == message.from_user.id:
                message.reply_text("Ha, you can't set your own bio! You're at the mercy of others here...")
                return
            elif user_id == bot.id and sender.id not in SUDO_USERS:
                message.reply_text("Erm... yeah, I only trust sudo users to set my bio.")
                return

            text = message.text
            bio = text.split(None, 1)  # use python's maxsplit to only remove the cmd, hence keeping newlines.
            if len(bio) == 2:
                if len(bio[1]) < MAX_MESSAGE_LENGTH // 4:
                    sql.set_user_bio(user_id, is_channel, bio[1])
                    message.reply_text("Updated {}'s bio!".format(repl_message.from_user.first_name))
                else:
                    message.reply_text(
                        "A bio needs to be under {} characters! You tried to set {}.".format(
                            MAX_MESSAGE_LENGTH // 4, len(bio[1])))
        else:
            user_id = repl_message.sender_chat.id
            text = message.text
            bio = text.split(None, 1)  # use python's maxsplit to only remove the cmd, hence keeping newlines.
            if len(bio) == 2:
                if len(bio[1]) < MAX_MESSAGE_LENGTH // 4:
                    sql.set_user_bio(user_id, is_channel, bio[1])
                    message.reply_text("Updated {}'s bio!".format(repl_message.from_user.first_name))
                else:
                    message.reply_text(
                        "A bio needs to be under {} characters! You tried to set {}.".format(
                            MAX_MESSAGE_LENGTH // 4, len(bio[1])))

    else:
        message.reply_text("Reply to someone's message to set their bio!")


def __user_info__(user_id, is_channel):
    bio = html.escape(sql.get_user_bio(user_id, is_channel) or "")
    if bio:
        return "<b>What others say:</b>\n{bio}\n".format(bio=bio)
    else:
        return ""


def __gdpr__(user_id):
    sql.clear_user_bio(user_id)


__help__ = """
 - /bio: получить заметку вашу или другого пользователя.

 *Только администратор:*
 - /setbio <текст>: при ответе на сообщение будет сохранена заметка о пользователе пользователя (ваша заметка о нём)
"""

__mod_name__ = "Заметки о юзере"

SET_BIO_HANDLER = DisableAbleCommandHandler("setbio", set_about_bio)
GET_BIO_HANDLER = DisableAbleCommandHandler("bio", about_bio, pass_args=True)

dispatcher.add_handler(SET_BIO_HANDLER)
dispatcher.add_handler(GET_BIO_HANDLER)
