import html
import re

from telegram import Update
from telegram.ext import (
    MessageHandler,
    ContextTypes,
    filters
)
from telegram.helpers import mention_html

from tg_bot import application, SUDO_USERS, LOGGER
from tg_bot.modules.helper_funcs.chat_status import (
    user_admin,
    bot_can_delete
)
from tg_bot.modules.helper_funcs.handlers import create_handler
from tg_bot.modules.log_channel import loggable
from tg_bot.modules.sql import regex_user_bans_sql as sql


@user_admin
@bot_can_delete
@loggable
async def user_ban_add_exclusion(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    args = context.args
    if not args or args[0] is None:
        await update.effective_message.reply_text("Username value is missing")
        return ""

    username = args[0]
    sql.add_ban_exclusion(username)
    await update.effective_message.reply_text(f"Username {username} was added to ban exclusions")

    return (f"<b>{html.escape(update.effective_chat.title)}:</b>\n"
            f"#BAN_EXCLUSION_ADD\n"
            f"<b>Admin:</b> {mention_html(update.effective_user.id, update.effective_user.first_name)}\n"
            f"<b>Username:</b> {html.escape(username)}")

@user_admin
@bot_can_delete
@loggable
async def userregexpadd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    args = context.args
    if not args or args[0] is None:
        await update.effective_message.reply_text("Regexp value is missing")
        return ""

    regex = args[0]
    chat_id = update.effective_chat.id
    sql.add_regex_bans(chat_id, regex)
    await update.effective_message.reply_text("Regex " + regex + " was added to ban list")

    return (f"<b>{html.escape(update.effective_chat.title)}:</b>\n"
            f"#REGEX_BAN_ADD\n"
            f"<b>Admin:</b> {mention_html(update.effective_user.id, update.effective_user.first_name)}\n"
            f"<b>Regex:</b> {html.escape(regex)}")

@user_admin
@loggable
async def user_ban_exclusion_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    res = sql.get_ban_exclusions()
    if res:
        res = [x.username_to_exclude for x in res]
        await update.effective_message.reply_text("User ban exclusions: " + ','.join(res))
    else:
        await update.effective_message.reply_text("There are no user ban exclusions")

@user_admin
@loggable
async def userregexplist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    res = sql.get_regex_bans(update.effective_chat.id)
    if res:
        res = [x.regex_to_ban for x in res]
        await update.effective_message.reply_text("Regexp banned in this chat: " + ','.join(res))
    else:
        await update.effective_message.reply_text("There are no regexp in ban")

@user_admin
@loggable
async def user_ban_delete_exclusion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args or args[0] is None:
        await update.effective_message.reply_text("Username value is missing")
        return

    username = args[0]
    if sql.delete_ban_exclusion(username):
        await update.effective_message.reply_text("Username " + username + " was removed from ban exclusions")
    else:
        await update.effective_message.reply_text("This username was not found in exclusions list")

@user_admin
@loggable
async def userregexpdelete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args  or args[0] is None:
        await update.effective_message.reply_text("Regexp value is missing")
        return

    regex = args[0]
    chat_id = update.effective_chat.id
    if sql.delete_regex_ban(chat_id, regex):
        await update.effective_message.reply_text("Regexp " + regex + " was removed from ban list")
    else:
        await update.effective_message.reply_text("This regex was not found in ban list")

@user_admin
@bot_can_delete
@loggable
async def g_userregexpadd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    if update.effective_user.id not in SUDO_USERS:
        await update.effective_message.reply_text("Only SUDO users can use this command")
        return ""

    args = context.args
    if not args:
        await update.effective_message.reply_text("Regexp value is missing")
        return ""

    regex = args[0]
    sql.add_regex_global_bans(regex)
    await update.effective_message.reply_text("Regex " + regex + " was added to global ban list")

    return (f"<b>GLOBAL:</b>\n"
            f"#GLOBAL_REGEX_BAN_ADD\n"
            f"<b>Admin:</b> {mention_html(update.effective_user.id, update.effective_user.first_name)}\n"
            f"<b>Regex:</b> {html.escape(regex)}")

@user_admin
@loggable
async def g_userregexplist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in SUDO_USERS:
        await update.effective_message.reply_text("Only SUDO users can use this command")
        return

    res = sql.get_regex_global_bans()
    if res:
        res = [x.regex_to_ban for x in res]
        await update.effective_message.reply_text("Regexp banned globally: " + ','.join(res))
    else:
        await update.effective_message.reply_text("There are no regexp in ban globally")

@user_admin
@loggable
async def g_userregexpdelete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in SUDO_USERS:
        await update.effective_message.reply_text("Only SUDO users can use this command")
        return

    args = context.args
    if not args:
        await update.effective_message.reply_text("Regexp value is missing")
        return

    regex = args[0]
    if sql.delete_regex_global_ban(regex):
        await update.effective_message.reply_text("Regexp " + regex + " was removed from global ban list")
    else:
        await update.effective_message.reply_text("This regex was not found in global ban list")


async def remove_banned_nicknames(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_members = update.effective_message.new_chat_members
    chat = update.effective_chat

    if not new_members:
        return

    regexes = [x.regex_to_ban for x in sql.get_regex_bans(chat.id)]
    regexes_global = [x.regex_to_ban for x in sql.get_regex_global_bans()]
    
    LOGGER.info(f"Chat regexes: {regexes}, Global regexes: {regexes_global}")

    for user in new_members:
        if sql.is_ban_exclusion_exists(user.username):
            continue

        for regex in regexes + regexes_global:
            if user.username and re.search(regex, user.username):
                await update.effective_message.reply_text("#бан_банан 🍌 тебе!")
                await chat.ban_member(user.id)
                break


__help__ = r"""
*Только администратор*:
Блокирует новых участников чата, ник \(имя пользователя\) которых соответствует одному из добавленных шаблонов регулярных выражений\\.
Имена пользователей обрабатываются без символа @ в начале\\. Например, имя\_пользователя вместо @имя\_пользователя
 \- `/user\_regexpban\_add` \\[регулярное выражение\\] \\- добавить регулярное выражение
 \- `/user\_regexpban\_list` \\- список регулярных выражений
 \- `/user\_regexpban\_del` \\[регулярное выражение\\] \\- удалить регулярное выражение\\. Не разблокирует уже забаненных пользователей\\.

 \- `/g\_user\_regexpban\_add` \\[регулярное выражение\\] \\- добавить глобальноре регулярное выражение
 \- `/g\_user\_regexpban\_list` \\- список глобальных регулярных выражений
 \- `/g\_user\_regexpban\_del` \\[регулярное выражение\\] \\- удалить глобальное регулярное выражение\\. Не разблокирует уже забаненных пользователей\\.

 \- `/user\_ban\_add\_exclusion` \\[username\\] \\- добавить username
 \- `/user\_ban\_exclusion\_list` \\- список username
 \- `/user\_ban\_delete\_exclusion` \\[username\\] \\- удалить username

Например: блокировать имена, состоящие из минимум трёх и более букв подряд и двух цифр \(sdf11, dfsd87\): `/regexpuserban ^\\[a-zA-Z\\]\\{3,\\}\\[0-9\\]\\{2\\}$` Если в имени \\
две буквы \(aa11\), три цифры \(aaaa111\), среди букв есть лишняя цифра\(aa1a11\), они не будут заблокированы\\.
"""

__mod_name__ = "Regexp ник бан"

REGEXPUSERBAN_HANDLER = create_handler("user_regexpban_add", userregexpadd,
                                       filters=filters.ChatType.GROUPS)
LISTREGEXPUSERBAN_HANDLER = create_handler("user_regexpban_list", userregexplist,
                                           filters=filters.ChatType.GROUPS)
UNBANREGEXPUSERBAN_HANDLER = create_handler("user_regexpban_del", userregexpdelete,
                                            filters=filters.ChatType.GROUPS)

ADD_BAN_EXCLUSION_HANDLER = create_handler("user_ban_add_exclusion", user_ban_add_exclusion,
                                           filters=filters.ChatType.GROUPS)
LIST_BAN_EXCLUSION_HANDLER = create_handler("user_ban_exclusion_list", user_ban_exclusion_list,
                                            filters=filters.ChatType.GROUPS)
DELETE_BAN_EXCLUSION_HANDLER = create_handler("user_ban_delete_exclusion", user_ban_delete_exclusion,
                                              filters=filters.ChatType.GROUPS)

G_REGEXPUSERBAN_HANDLER = create_handler("g_user_regexpban_add", g_userregexpadd,
                                         filters=filters.ChatType.GROUPS)
G_LISTREGEXPUSERBAN_HANDLER = create_handler("g_user_regexpban_list", g_userregexplist,
                                             filters=filters.ChatType.GROUPS)
G_UNBANREGEXPUSERBAN_HANDLER = create_handler("g_user_regexpban_del", g_userregexpdelete,
                                              filters=filters.ChatType.GROUPS)

# PERM_GROUP should be an integer defined in your project
PERM_GROUP = 7

application.add_handler(REGEXPUSERBAN_HANDLER)
application.add_handler(LISTREGEXPUSERBAN_HANDLER)
application.add_handler(UNBANREGEXPUSERBAN_HANDLER)

application.add_handler(ADD_BAN_EXCLUSION_HANDLER)
application.add_handler(LIST_BAN_EXCLUSION_HANDLER)
application.add_handler(DELETE_BAN_EXCLUSION_HANDLER)

application.add_handler(G_REGEXPUSERBAN_HANDLER)
application.add_handler(G_LISTREGEXPUSERBAN_HANDLER)
application.add_handler(G_UNBANREGEXPUSERBAN_HANDLER)

# MessageHandler for new_chat_members using the new filters syntax
application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, remove_banned_nicknames), PERM_GROUP)