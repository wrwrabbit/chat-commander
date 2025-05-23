import html
from typing import Optional

from telegram import Message, Chat, Update, User
from telegram.error import BadRequest
from telegram.ext import filters, MessageHandler, ContextTypes
from telegram.helpers import mention_html

from tg_bot import application
from tg_bot.modules.helper_funcs.chat_status import is_user_admin, user_admin, can_restrict
from tg_bot.modules.helper_funcs.handlers import create_handler
from tg_bot.modules.log_channel import loggable
from tg_bot.modules.sql import antiflood_sql as sql

FLOOD_GROUP = 3


@loggable
async def check_flood(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    user = update.effective_user  # type: Optional[User]
    chat = update.effective_chat  # type: Optional[Chat]
    msg = update.effective_message  # type: Optional[Message]

    is_channel = update.effective_message.sender_chat is not None

    if not user:  # ignore channels
        return ""

    # ignore admins
    if await is_user_admin(chat, user.id, context):
        sql.update_flood(str(chat.id), None, is_channel)
        return ""

    should_ban = sql.update_flood(str(chat.id), user.id, is_channel)
    if not should_ban:
        return ""

    try:
        if not is_channel:
            await chat.ban_member(user.id)
            await msg.reply_text("I like to leave the flooding to natural disasters. But you, you were just a "
                           "disappointment. Get out.")

            return "<b>{}:</b>" \
                   "\n#BANNED" \
                   "\n<b>User:</b> {}" \
                   "\nFlooded the group.".format(html.escape(chat.title),
                                                 mention_html(str(user.id), user.first_name))
        else:
            sender_chat = update.effective_message.sender_chat
            await chat.ban_sender_chat(sender_chat.id)
            await msg.reply_text("I like to leave the flooding to natural disasters. But you, you were just a "
                           "disappointment. Get out.")

            return "<b>{}:</b>" \
                   "\n#BANNED" \
                   "\n<b>User:</b> {}" \
                   "\nFlooded the group.".format(html.escape(chat.title),
                                                 mention_html(str(sender_chat.id), sender_chat.username))

    except BadRequest:
        await msg.reply_text("I can't kick people here, give me permissions first! Until then, I'll disable antiflood.")
        sql.set_flood(chat.id, 0)
        return "<b>{}:</b>" \
               "\n#INFO" \
               "\nDon't have kick permissions, so automatically disabled antiflood.".format(chat.title)


@user_admin
@can_restrict
@loggable
async def set_flood(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    args = context.args  # Автоматически разбивает строку по пробелам
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]
    message = update.effective_message  # type: Optional[Message]

    if len(args) >= 1:
        val = args[0].lower()
        if val == "off" or val == "no" or val == "0":
            sql.set_flood(chat.id, 0)
            await message.reply_text("Antiflood has been disabled.")
            return "<b>{}:</b>" \
                   "\n#SETFLOOD" \
                   "\n<b>Admin:</b> {}" \
                   "\nDisabled antiflood.".format(html.escape(chat.title),
                                                  mention_html(str(user.id), user.first_name))

        elif val.isdigit():
            amount = int(val)
            if amount <= 0:
                sql.set_flood(chat.id, 0)
                await message.reply_text("Antiflood has been disabled.")
                return "<b>{}:</b>" \
                       "\n#SETFLOOD" \
                       "\n<b>Admin:</b> {}" \
                       "\nDisabled antiflood.".format(html.escape(chat.title),
                                                      mention_html(str(user.id), user.first_name))

            elif amount < 3:
                await message.reply_text("Antiflood has to be either 0 (disabled), or a number bigger than 3!")
                return ""

            else:
                sql.set_flood(chat.id, amount)
                await message.reply_text("Antiflood has been updated and set to {}".format(amount))
                return "<b>{}:</b>" \
                       "\n#SETFLOOD" \
                       "\n<b>Admin:</b> {}" \
                       "\nSet antiflood to <code>{}</code>.".format(html.escape(chat.title),
                                                                    mention_html(str(user.id), user.first_name), amount)

        else:
            await message.reply_text("Unrecognised argument - please use a number, 'off', or 'no'.")

    return ""

@user_admin
async def flood(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat  # type: Optional[Chat]

    limit = sql.get_flood_limit(chat.id)
    if limit == 0:
        await update.effective_message.reply_text("I'm not currently enforcing flood control!")
    else:
        await update.effective_message.reply_text(
            "I'm currently banning users if they send more than {} consecutive messages.".format(limit))


def __migrate__(old_chat_id, new_chat_id):
    sql.migrate_chat(old_chat_id, new_chat_id)


def __chat_settings__(chat_id, user_id):
    limit = sql.get_flood_limit(chat_id)
    if limit == 0:
        return "*Not* currently enforcing flood control\."
    else:
        return "Antiflood is set to `{}` messages\.".format(limit)


__help__ = """
 \- /flood: показать текущую настройку контроля флуда

*Только администратор:*
 \- /setflood \<int/'no'/'off'\>: : включает или отключает контроль флуда\. int \- это количество сообщений подряд от одного пользователя будет считаться флудом\.
"""

__mod_name__ = "Антифлуд"

FLOOD_BAN_HANDLER = MessageHandler(filters.ALL & ~filters.UpdateType.EDITED_MESSAGE & filters.ChatType.GROUPS, check_flood)
SET_FLOOD_HANDLER = create_handler("setflood", set_flood, filters=filters.ChatType.GROUPS)
FLOOD_HANDLER = create_handler("flood", flood, filters=filters.ChatType.GROUPS)

application.add_handler(FLOOD_BAN_HANDLER, FLOOD_GROUP)
application.add_handler(SET_FLOOD_HANDLER)
application.add_handler(FLOOD_HANDLER)
