import html
from typing import Optional, List

from telegram import Message, Chat, Update, Bot, User
from telegram.error import BadRequest
from telegram.ext import Filters, MessageHandler, CommandHandler, run_async
from telegram.utils.helpers import mention_html

from tg_bot import dispatcher
from tg_bot.modules.helper_funcs.chat_status import is_user_admin, user_admin, can_restrict
from tg_bot.modules.log_channel import loggable
from tg_bot.modules.sql import antiflood_sql as sql

FLOOD_GROUP = 3


# @run_async
@loggable
def check_flood(bot: Bot, update: Update) -> str:
    user = update.effective_user  # type: Optional[User]
    chat = update.effective_chat  # type: Optional[Chat]
    msg = update.effective_message  # type: Optional[Message]

    is_channel = update.effective_message.sender_chat is not None

    if not user:  # ignore channels
        return ""

    # ignore admins
    if is_user_admin(chat, user.id):
        sql.update_flood(chat.id, None, is_channel)
        return ""

    should_ban = sql.update_flood(chat.id, user.id, is_channel)
    if not should_ban:
        return ""

    try:
        if not is_channel:
            chat.ban_member(user.id)
            msg.reply_text("I like to leave the flooding to natural disasters. But you, you were just a "
                           "disappointment. Get out.")

            return "<b>{}:</b>" \
                   "\n#BANNED" \
                   "\n<b>User:</b> {}" \
                   "\nFlooded the group.".format(html.escape(chat.title),
                                                 mention_html(user.id, user.first_name))
        else:
            sender_chat = update.effective_message.sender_chat
            chat.ban_sender_chat(sender_chat.id)
            msg.reply_text("I like to leave the flooding to natural disasters. But you, you were just a "
                           "disappointment. Get out.")

            return "<b>{}:</b>" \
                   "\n#BANNED" \
                   "\n<b>User:</b> {}" \
                   "\nFlooded the group.".format(html.escape(chat.title),
                                                 mention_html(sender_chat.id, sender_chat.username))

    except BadRequest:
        msg.reply_text("I can't kick people here, give me permissions first! Until then, I'll disable antiflood.")
        sql.set_flood(chat.id, 0)
        return "<b>{}:</b>" \
               "\n#INFO" \
               "\nDon't have kick permissions, so automatically disabled antiflood.".format(chat.title)


# @run_async
@user_admin
@can_restrict
@loggable
def set_flood(bot: Bot, update: Update) -> str:
    args = update.effective_message.text.split(" ")[1:]
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]
    message = update.effective_message  # type: Optional[Message]

    if len(args) >= 1:
        val = args[0].lower()
        if val == "off" or val == "no" or val == "0":
            sql.set_flood(chat.id, 0)
            message.reply_text("Antiflood has been disabled.")

        elif val.isdigit():
            amount = int(val)
            if amount <= 0:
                sql.set_flood(chat.id, 0)
                message.reply_text("Antiflood has been disabled.")
                return "<b>{}:</b>" \
                       "\n#SETFLOOD" \
                       "\n<b>Admin:</b> {}" \
                       "\nDisabled antiflood.".format(html.escape(chat.title), mention_html(user.id, user.first_name))

            elif amount < 3:
                message.reply_text("Antiflood has to be either 0 (disabled), or a number bigger than 3!")
                return ""

            else:
                sql.set_flood(chat.id, amount)
                message.reply_text("Antiflood has been updated and set to {}".format(amount))
                return "<b>{}:</b>" \
                       "\n#SETFLOOD" \
                       "\n<b>Admin:</b> {}" \
                       "\nSet antiflood to <code>{}</code>.".format(html.escape(chat.title),
                                                                    mention_html(user.id, user.first_name), amount)

        else:
            message.reply_text("Unrecognised argument - please use a number, 'off', or 'no'.")

    return ""


# @run_async
def flood(bot: Bot, update: Update):
    chat = update.effective_chat  # type: Optional[Chat]

    limit = sql.get_flood_limit(chat.id)
    if limit == 0:
        update.effective_message.reply_text("I'm not currently enforcing flood control!")
    else:
        update.effective_message.reply_text(
            "I'm currently banning users if they send more than {} consecutive messages.".format(limit))


def __migrate__(old_chat_id, new_chat_id):
    sql.migrate_chat(old_chat_id, new_chat_id)


def __chat_settings__(chat_id, user_id):
    limit = sql.get_flood_limit(chat_id)
    if limit == 0:
        return "*Not* currently enforcing flood control."
    else:
        return "Antiflood is set to `{}` messages.".format(limit)


__help__ = """
 - /flood: показать текущую настройку контроля флуда

*Только администратор:*
 - /setflood <int/'no'/'off'>: : включает или отключает контроль флуда. int - это количество сообщений подряд от одного пользователя будет считаться флудом.
"""

__mod_name__ = "Антифлуд"

FLOOD_BAN_HANDLER = MessageHandler(Filters.all & ~Filters.status_update & Filters.chat_type.groups, check_flood)
SET_FLOOD_HANDLER = CommandHandler("setflood", set_flood, pass_args=True, filters=Filters.chat_type.groups)
FLOOD_HANDLER = CommandHandler("flood", flood, filters=Filters.chat_type.groups)

dispatcher.add_handler(FLOOD_BAN_HANDLER, FLOOD_GROUP)
dispatcher.add_handler(SET_FLOOD_HANDLER)
dispatcher.add_handler(FLOOD_HANDLER)
