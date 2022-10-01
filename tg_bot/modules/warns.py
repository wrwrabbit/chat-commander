import html
import re
from typing import Optional, List

import telegram
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ParseMode, User, CallbackQuery
from telegram import Message, Chat, Update, Bot
from telegram.error import BadRequest
from telegram.ext import CommandHandler, run_async, DispatcherHandlerStop, MessageHandler, Filters, CallbackQueryHandler
from telegram.utils.helpers import mention_html

from tg_bot import dispatcher, BAN_STICKER
from tg_bot.modules.disable import DisableAbleCommandHandler
from tg_bot.modules.helper_funcs.chat_status import is_user_admin, bot_admin, user_admin_no_reply, user_admin, \
    can_restrict
from tg_bot.modules.helper_funcs.extraction import extract_text, extract_user_and_text, extract_user, \
    extract_user_and_is_channel, extract_user_and_text_and_is_channel
from tg_bot.modules.helper_funcs.filters import CustomFilters
from tg_bot.modules.helper_funcs.misc import split_message
from tg_bot.modules.helper_funcs.string_handling import split_quotes
from tg_bot.modules.log_channel import loggable
from tg_bot.modules.sql import warns_sql as sql

WARN_HANDLER_GROUP = 9
CURRENT_WARNING_FILTER_STRING = "<b>Current warning filters in this chat:</b>\n"


# Not async
def warn(user_id, username, is_channel, chat: Chat, reason: str, message: Message, warner: User = None) -> str:
    if is_user_admin(chat, user_id):
        message.reply_text("А с какой стати вы собрались предупреждать админа?")
        return ""

    if warner:
        warner_tag = mention_html(warner.id, warner.first_name)
    else:
        warner_tag = "Автопредупреждение."

    limit, soft_warn = sql.get_warn_setting(chat.id)
    num_warns, reasons = sql.warn_user(user_id, is_channel, chat.id, reason)
    if num_warns >= limit:
        sql.reset_warns(user_id, is_channel, chat.id)
        if not is_channel:
            if soft_warn:  # kick
                chat.unban_member(user_id)
                reply = "{} предупреждений, {} удален из чата".format(limit, mention_html(user_id, username))
            else:  # ban
                chat.ban_member(user_id)
                reply = "{} предупреждений, {} забанен!".format(limit, mention_html(user_id, username))
        else:
            chat.ban_sender_chat(user_id)
            reply = "{} предупреждений, {} забанен!".format(limit, mention_html(user_id, username))

        for warn_reason in reasons:
            reply += "\n - {}".format(html.escape(warn_reason))

        message.bot.send_sticker(chat.id, BAN_STICKER)  # banhammer marie sticker
        keyboard = []
        log_reason = "<b>{}:</b>" \
                     "\n#WARN_BAN" \
                     "\n<b>Админ:</b> {}" \
                     "\n<b>Пользователь:</b> {} (<code>{}</code>)" \
                     "\n<b>Причина:</b> {}" \
                     "\n<b>Кол. предупреждений:</b> <code>{}/{}</code>".format(html.escape(chat.title),
                                                                               warner_tag,
                                                                               mention_html(user_id, username),
                                                                               user_id, reason, num_warns, limit)

    else:
        keyboard = InlineKeyboardMarkup(
            [[InlineKeyboardButton("Аннулировать предупреждения", callback_data="rm_warn({},{})".format(user_id, is_channel))]])

        reply = "У {} есть {}/{} предупреждений...".format(mention_html(user_id, username), num_warns,
                                                           limit)
        if reason:
            reply += "\nПричина последнего предупреждения:\n{}".format(html.escape(reason))

        log_reason = "<b>{}:</b>" \
                     "\n#WARN" \
                     "\n<b>Админ:</b> {}" \
                     "\n<b>Пользователь:</b> {} (<code>{}</code>)" \
                     "\n<b>Причина:</b> {}" \
                     "\n<b>Кол. предуп.:</b> <code>{}/{}</code>".format(html.escape(chat.title),
                                                                        warner_tag,
                                                                        mention_html(user_id, username),
                                                                        user_id, reason, num_warns, limit)

    try:
        message.reply_text(reply, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    except BadRequest as excp:
        if excp.message == "Reply message not found":
            # Do not reply
            message.reply_text(reply, reply_markup=keyboard, parse_mode=ParseMode.HTML, quote=False)
        else:
            raise
    return log_reason


# @run_async
@user_admin_no_reply
@bot_admin
@loggable
def button(bot: Bot, update: Update) -> str:
    query = update.callback_query  # type: Optional[CallbackQuery]
    user = update.effective_user  # type: Optional[User]
    data = query.data[8:-1]
    user_id, is_channel = (int(data.split(",")[0]), data.split(",")[1] == 'True')
    chat = update.effective_chat  # type: Optional[Chat]
    res = sql.remove_warn(user_id, is_channel, chat.id)
    if res:
        update.effective_message.edit_text(
            "Предупреждение удалил админ.",
            parse_mode=ParseMode.HTML)
        if not is_channel:
            user_member = chat.get_member(user_id)
            return "<b>{}:</b>" \
                   "\n#UNWARN" \
                   "\n<b>Админ:</b> {}" \
                   "\n<b>Пользователь:</b> {} (<code>{}</code>)".format(html.escape(chat.title),
                                                                        mention_html(user.id, user.first_name),
                                                                        mention_html(user_member.user.id,
                                                                                     user_member.user.first_name),
                                                                        user_member.user.id)
        else:
            return "<b>{}:</b>" \
                   "\n#UNWARN" \
                   "\n<b>Админ:</b> {}" \
                   "\n<b>Пользователь:</b> {} (<code>{}</code>)".format(html.escape(chat.title),
                                                                        mention_html(user.id, user.first_name),
                                                                        mention_html(user_id,
                                                                                     str(user_id)),
                                                                        user_id)
    else:
        update.effective_message.edit_text(
            "У пользователя нет предупреждений.",
            parse_mode=ParseMode.HTML)
    return ""


# @run_async
@user_admin
@can_restrict
@loggable
def warn_user(bot: Bot, update: Update) -> str:
    args = update.effective_message.text.split(" ")[1:]
    message = update.effective_message  # type: Optional[Message]
    chat = update.effective_chat  # type: Optional[Chat]
    warner = update.effective_user  # type: Optional[User]

    user_id, reason, is_channel = extract_user_and_text_and_is_channel(message, args)

    if user_id:
        if not is_channel:
            if message.reply_to_message and message.reply_to_message.from_user.id == user_id:
                return warn(user_id, message.reply_to_message.from_user.first_name, is_channel, chat, reason,
                            message.reply_to_message, warner)
            else:
                return warn(user_id, chat.get_member(user_id).user.first_name, is_channel, chat, reason, message,
                            warner)
        else:
            if message.reply_to_message and message.reply_to_message.sender_chat.id == user_id:
                return warn(user_id, message.reply_to_message.sender_chat.username, is_channel, chat, reason,
                            message.reply_to_message, warner)
            else:
                return warn(user_id, message.sender_chat.username, is_channel, chat, reason, message, warner)
    else:
        message.reply_text("Нет данных пользователя")
    return ""


# @run_async
@user_admin
@bot_admin
@loggable
def reset_warns(bot: Bot, update: Update) -> str:
    args = update.effective_message.text.split(" ")[1:]
    message = update.effective_message  # type: Optional[Message]
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]

    user_id, is_channel = extract_user_and_is_channel(message, args)

    if user_id:
        sql.reset_warns(user_id, is_channel, chat.id)
        message.reply_text("Предупреждения аннулированы!")
        if not is_channel:
            warned = chat.get_member(user_id).user
            return "<b>{}:</b>" \
                   "\n#RESETWARNS" \
                   "\n<b>Админ:</b> {}" \
                   "\n<b>Пользователь:</b> {} (<code>{}</code>)".format(html.escape(chat.title),
                                                                        mention_html(user.id, user.first_name),
                                                                        mention_html(warned.id, warned.first_name),
                                                                        warned.id)
        else:
            return "<b>{}:</b>" \
                   "\n#RESETWARNS" \
                   "\n<b>Админ:</b> {}" \
                   "\n<b>Пользователь:</b> {} (<code>{}</code>)".format(html.escape(chat.title),
                                                                        mention_html(user.id, user.first_name),
                                                                        mention_html(user_id, str(user_id)),
                                                                        user_id)
    else:
        message.reply_text("Нет данных пользователя")
    return ""


# @run_async
def warns(bot: Bot, update: Update):
    args = update.effective_message.text.split(" ")[1:]
    message = update.effective_message  # type: Optional[Message]
    chat = update.effective_chat  # type: Optional[Chat]
    user_id, is_channel = extract_user_and_is_channel(message, args) or (update.effective_user.id, False)
    result = sql.get_warns(user_id, is_channel, chat.id)

    if result and result[0] != 0:
        num_warns, reasons = result
        limit, soft_warn = sql.get_warn_setting(chat.id)

        if reasons:
            text = "У пользователя {}/{} предупреждений, по след. причинам:".format(num_warns, limit)
            for reason in reasons:
                text += "\n - {}".format(reason)

            msgs = split_message(text)
            for msg in msgs:
                update.effective_message.reply_text(msg)
        else:
            update.effective_message.reply_text(
                "У пользователя {}/{} предупреждений, без указанных причин.".format(num_warns, limit))
    else:
        update.effective_message.reply_text("У пользователя нет предупреждений")


# Dispatcher handler stop - do not async
@user_admin
def add_warn_filter(bot: Bot, update: Update):
    chat = update.effective_chat  # type: Optional[Chat]
    msg = update.effective_message  # type: Optional[Message]

    args = msg.text.split(None, 1)  # use python's maxsplit to separate Cmd, keyword, and reply_text

    if len(args) < 2:
        return

    extracted = split_quotes(args[1])

    if len(extracted) >= 2:
        # set trigger -> lower, so as to avoid adding duplicate filters with different cases
        keyword = extracted[0].lower()
        content = extracted[1]

    else:
        return

    # Note: perhaps handlers can be removed somehow using sql.get_chat_filters
    for handler in dispatcher.handlers.get(WARN_HANDLER_GROUP, []):
        if handler.filters == (keyword, chat.id):
            dispatcher.remove_handler(handler, WARN_HANDLER_GROUP)

    sql.add_warn_filter(chat.id, keyword, content)

    update.effective_message.reply_text("Warn handler added for '{}'!".format(keyword))
    raise DispatcherHandlerStop


@user_admin
def remove_warn_filter(bot: Bot, update: Update):
    chat = update.effective_chat  # type: Optional[Chat]
    msg = update.effective_message  # type: Optional[Message]

    args = msg.text.split(None, 1)  # use python's maxsplit to separate Cmd, keyword, and reply_text

    if len(args) < 2:
        return

    extracted = split_quotes(args[1])

    if len(extracted) < 1:
        return

    to_remove = extracted[0]

    chat_filters = sql.get_chat_warn_triggers(chat.id)

    if not chat_filters:
        msg.reply_text("No warning filters are active here!")
        return

    for filt in chat_filters:
        if filt == to_remove:
            sql.remove_warn_filter(chat.id, to_remove)
            msg.reply_text("Yep, I'll stop warning people for that.")
            raise DispatcherHandlerStop

    msg.reply_text("That's not a current warning filter - run /warnlist for all active warning filters.")


# @run_async
def list_warn_filters(bot: Bot, update: Update):
    chat = update.effective_chat  # type: Optional[Chat]
    all_handlers = sql.get_chat_warn_triggers(chat.id)

    if not all_handlers:
        update.effective_message.reply_text("No warning filters are active here!")
        return

    filter_list = CURRENT_WARNING_FILTER_STRING
    for keyword in all_handlers:
        entry = " - {}\n".format(html.escape(keyword))
        if len(entry) + len(filter_list) > telegram.MAX_MESSAGE_LENGTH:
            update.effective_message.reply_text(filter_list, parse_mode=ParseMode.HTML)
            filter_list = entry
        else:
            filter_list += entry

    if not filter_list == CURRENT_WARNING_FILTER_STRING:
        update.effective_message.reply_text(filter_list, parse_mode=ParseMode.HTML)


# @run_async
@loggable
def reply_filter(bot: Bot, update: Update) -> str:
    chat = update.effective_chat  # type: Optional[Chat]
    message = update.effective_message  # type: Optional[Message]

    chat_warn_filters = sql.get_chat_warn_triggers(chat.id)
    to_match = extract_text(message)
    if not to_match:
        return ""

    for keyword in chat_warn_filters:
        pattern = r"( |^|[^\w])" + re.escape(keyword) + r"( |$|[^\w])"
        if re.search(pattern, to_match, flags=re.IGNORECASE):
            user = update.effective_user  # type: Optional[User]
            is_channel = update.effective_message.sender_chat is not None
            warn_filter = sql.get_warn_filter(chat.id, keyword)
            if not is_channel:
                return warn(user.id, user.first_name, is_channel, chat, warn_filter.reply, message)
            else:
                return warn(update.effective_message.sender_chat.id, update.effective_message.sender_chat.username,
                            is_channel, chat, warn_filter.reply, message)
    return ""


# @run_async
@user_admin
@loggable
def set_warn_limit(bot: Bot, update: Update) -> str:
    args = update.effective_message.text.split(" ")[1:]
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]
    msg = update.effective_message  # type: Optional[Message]

    if args:
        if args[0].isdigit():
            if int(args[0]) < 3:
                msg.reply_text("The minimum warn limit is 3!")
            else:
                sql.set_warn_limit(chat.id, int(args[0]))
                msg.reply_text("Updated the warn limit to {}".format(args[0]))
                return "<b>{}:</b>" \
                       "\n#SET_WARN_LIMIT" \
                       "\n<b>Admin:</b> {}" \
                       "\nSet the warn limit to <code>{}</code>".format(html.escape(chat.title),
                                                                        mention_html(user.id, user.first_name), args[0])
        else:
            msg.reply_text("Give me a number as an arg!")
    else:
        limit, soft_warn = sql.get_warn_setting(chat.id)

        msg.reply_text("The current warn limit is {}".format(limit))
    return ""


# @run_async
@user_admin
def set_warn_strength(bot: Bot, update: Update):
    args = update.effective_message.text.split(" ")[1:]
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]
    msg = update.effective_message  # type: Optional[Message]

    if args:
        if args[0].lower() in ("on", "yes"):
            sql.set_warn_strength(chat.id, False)
            msg.reply_text("Сейчас чересчур много предупреждений приведут к бану!")
            return "<b>{}:</b>\n" \
                   "<b>Админ:</b> {}\n" \
                   "Включил строгий режим предупреждений. Нарушители будут забаннены.".format(html.escape(chat.title),
                                                                                              mention_html(user.id,
                                                                                                           user.first_name))

        elif args[0].lower() in ("off", "no"):
            sql.set_warn_strength(chat.id, True)
            msg.reply_text(
                "Сейчас чересчур много предупреждений приведут к удалению. Пользователи смогут вернуться в чат.")
            return "<b>{}:</b>\n" \
                   "<b>Админ:</b> {}\n" \
                   "Выключил строгий режим предупреждений. Нарушители будут просто удалены.".format(
                html.escape(chat.title),
                mention_html(user.id,
                             user.first_name))

        else:
            msg.reply_text("Я только принимаю on/yes/no/off!")
    else:
        limit, soft_warn = sql.get_warn_setting(chat.id)
        if soft_warn:
            msg.reply_text("Предупреждения приведут к *удалению* пользователей.",
                           parse_mode=ParseMode.MARKDOWN)
        else:
            msg.reply_text("Предупреждения приведут к *бану* пользователей.",
                           parse_mode=ParseMode.MARKDOWN)
    return ""


def __stats__():
    return "Всего {} предупреждений, по {} чатам.\n" \
           "{} фильтров предупреждения, по {} чатам.".format(sql.num_warns(), sql.num_warn_chats(),
                                                             sql.num_warn_filters(), sql.num_warn_filter_chats())


def __import_data__(chat_id, data):
    for user_id, count in data.get('warns', {}).items():
        for x in range(int(count)):
            # TODO replace False with code after realizing import and export
            sql.warn_user(user_id, False, chat_id)


def __migrate__(old_chat_id, new_chat_id):
    sql.migrate_chat(old_chat_id, new_chat_id)


def __chat_settings__(chat_id, user_id):
    num_warn_filters = sql.num_warn_chat_filters(chat_id)
    limit, soft_warn = sql.get_warn_setting(chat_id)
    return "Этот чат имеет `{}` фильтров предупреждений. После `{}` предупреждений " \
           "пользователь будет *{}*.".format(num_warn_filters, limit, "удален" if soft_warn else "заблокирован")


__help__ = """
 - /warns <дескриптор пользователя>: получить номер пользователя и причину предупреждений.
 - /warnlist: список всех текущих фильтров предупреждений

*Только администратор:*
 - /warn <имя пользователя>: предупредить пользователя. После 3 предупреждений пользователь будет забанен в группе. Также можно использовать в ответе.
 - /resetwarn <имя пользователя>: сбросить предупреждения для пользователя. Также можно использовать в ответе.
 - /addwarn <ключевое слово> <ответное сообщение>: установить фильтр предупреждений по определенному ключевому слову. \
 Если вы хотите, чтобы ваше ключевое слово было предложением, заключите его в кавычки, например: `/addwarn "вали отсюда" грубость`
 - /nowarn <ключевое слово>: остановить фильтр предупреждений
 - /warnlimit <число>: установить лимит предупреждений
 - /strongwarn <on/yes/off/no>: Если установлено значение on, превышение лимита предупреждений приведет к бану. Иначе просто удалит из чата.
"""

__mod_name__ = "Предупреждения"

WARN_HANDLER = CommandHandler("warn", warn_user, pass_args=True, filters=Filters.chat_type.groups)
RESET_WARN_HANDLER = CommandHandler(["resetwarn", "resetwarns"], reset_warns, pass_args=True,
                                    filters=Filters.chat_type.groups)
CALLBACK_QUERY_HANDLER = CallbackQueryHandler(button, pattern=r"rm_warn")
MYWARNS_HANDLER = DisableAbleCommandHandler("warns", warns, pass_args=True, filters=Filters.chat_type.groups)
ADD_WARN_HANDLER = CommandHandler("addwarn", add_warn_filter, filters=Filters.chat_type.groups)
RM_WARN_HANDLER = CommandHandler(["nowarn", "stopwarn"], remove_warn_filter, filters=Filters.chat_type.groups)
LIST_WARN_HANDLER = DisableAbleCommandHandler(["warnlist", "warnfilters"], list_warn_filters,
                                              filters=Filters.chat_type.groups, admin_ok=True)
WARN_FILTER_HANDLER = MessageHandler(CustomFilters.has_text & Filters.chat_type.groups, reply_filter)
WARN_LIMIT_HANDLER = CommandHandler("warnlimit", set_warn_limit, pass_args=True, filters=Filters.chat_type.groups)
WARN_STRENGTH_HANDLER = CommandHandler("strongwarn", set_warn_strength, pass_args=True,
                                       filters=Filters.chat_type.groups)

dispatcher.add_handler(WARN_HANDLER)
dispatcher.add_handler(CALLBACK_QUERY_HANDLER)
dispatcher.add_handler(RESET_WARN_HANDLER)
dispatcher.add_handler(MYWARNS_HANDLER)
dispatcher.add_handler(ADD_WARN_HANDLER)
dispatcher.add_handler(RM_WARN_HANDLER)
dispatcher.add_handler(LIST_WARN_HANDLER)
dispatcher.add_handler(WARN_LIMIT_HANDLER)
dispatcher.add_handler(WARN_STRENGTH_HANDLER)
dispatcher.add_handler(WARN_FILTER_HANDLER, WARN_HANDLER_GROUP)
