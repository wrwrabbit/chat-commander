import html
import re

from telegram import Update
from telegram.ext import  MessageHandler, ContextTypes, filters
from telegram.helpers import mention_html

from tg_bot import application, SUDO_USERS
from tg_bot.modules.helper_funcs.chat_status import user_admin, bot_can_delete
from tg_bot.modules.helper_funcs.handlers import create_handler
from tg_bot.modules.log_channel import loggable
from tg_bot.modules.sql import regex_name_bans_sql as sql

@user_admin
@bot_can_delete
@loggable
async def regexpnameban(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    args = context.args
    message = update.effective_message
    chat = update.effective_chat

    if not args:
        await message.reply_text("Regexp value is missing")
        return ""

    regex = args[0]
    sql.add_regex_bans(chat.id, regex)
    await message.reply_text("Regex name " + regex + " was added to name ban list")
    return (f"<b>{html.escape(chat.title)}:</b>\n#REGEX_BAN\n<b>Admin:</b> "
            f"{mention_html(update.effective_user.id, update.effective_user.first_name)}\n"
            f"<b>Regex:</b> {html.escape(regex)}")

@user_admin
async def listregexpnameban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    res = sql.get_regex_bans(update.effective_chat.id)
    if res:
        res = [x.regex_to_ban for x in res]
        await update.effective_message.reply_text("Regexp banned in this chat: " + ' || '.join(res))
    else:
        await update.effective_message.reply_text("There are no regexp in name ban")

# @run_async
@user_admin
@loggable
async def regexpnameunban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.effective_message.reply_text("Regexp value is missing")
        return

    regex = args[0]
    chat = update.effective_chat
    if sql.delete_regex_ban(chat.id, regex):
        await update.effective_message.reply_text("Regexp name " + regex + " was removed from name ban list")
    else:
        await update.effective_message.reply_text("This regex was not found in ban list")

    return (f"<b>{html.escape(chat.title)}:</b>\n#REGEX_UNBAN\n"
            f"<b>Admin:</b> {mention_html(update.effective_user.id, update.effective_user.first_name)}\n"
            f"<b>Regex:</b> {html.escape(regex)}")


@user_admin
@bot_can_delete
@loggable
async def g_regexpnameban(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    args = context.args
    if update.effective_user.id not in SUDO_USERS:
        await update.effective_message.reply_text("Only SUDO users can use this command")
        return ""

    if not args:
        await update.effective_message.reply_text("Regexp value is missing")
        return ""

    regex = args[0]
    sql.add_regex_global_bans(regex)
    await update.effective_message.reply_text("Regex " + regex + " was added to global name ban list")
    return (f"<b>GLOBAL:</b>\n#GLOBAL_REGEX_BAN\n"
            f"<b>Admin:</b> {mention_html(update.effective_user.id, update.effective_user.first_name)}\n"
            f"<b>Regex:</b> {html.escape(regex)}")

@user_admin
async def g_listregexpnameban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in SUDO_USERS:
        await update.effective_message.reply_text("Only SUDO users can use this command")
        return

    res = sql.get_regex_global_bans()
    if res:
        res = [x.regex_to_ban for x in res]
        await update.effective_message.reply_text("Regexp banned globally: " + ' || '.join(res))
    else:
        await update.effective_message.reply_text("There are no regexp in ban globally")

# @run_async
@user_admin
@loggable
async def g_regexpnameunban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if update.effective_user.id not in SUDO_USERS:
        await update.effective_message.reply_text("Only SUDO users can use this command")
        return

    if not args:
        await update.effective_message.reply_text("Regexp value is missing")
        return

    regex = args[0]
    if sql.delete_regex_global_ban(regex):
        await update.effective_message.reply_text("Regexp " + regex + " was removed from global name ban list")
    else:
        await update.effective_message.reply_text("This regex was not found in global ban list")

    return (f"<b>GLOBAL:</b>\n#GLOBAL_REGEX_UNBAN\n"
            f"<b>Admin:</b> {mention_html(update.effective_user.id, update.effective_user.first_name)}\n"
            f"<b>Regex:</b> {html.escape(regex)}")


# @run_async
async def remove_banned_nicknames(update: Update, context: ContextTypes.DEFAULT_TYPE):
    joined_names = update.effective_message.new_chat_members
    chat = update.effective_chat

    if not joined_names:
        return

    regexes = [x.regex_to_ban for x in sql.get_regex_bans(chat.id)]
    regexes_global = [x.regex_to_ban for x in sql.get_regex_global_bans()]

    for user in joined_names:
        for regex in regexes:
            pattern = re.compile(regex)
            is_banned = (
                    (user.first_name and pattern.match(user.first_name)) or
                    (user.last_name and pattern.match(user.last_name))
            )
            if is_banned:
                await update.effective_message.reply_text("#бан_банан 🍌 тебе!")
                await chat.ban_member(user.id)
                break

        for regex in regexes_global:
            is_banned = user.username and re.match(regex, user.username)

            if is_banned:
                await update.effective_message.reply_text("#бан_банан 🍌 тебе!")
                await chat.ban_member(user.id)
                break

__help__ = """
*Только администратор:*
Блокирует новых участников чата, имя или фамилия которых соответствуют одному из добавленных шаблонов 
регулярных выражений\.
Regexp проверяет как имя, так и фамилию\.
 \- /name\_regexpban\_add [регулярное выражение] \- добавить регулярное выражение
 \- /name\_regexpban\_list \- перечислить все регулярные выражения
 \- /name\_regexpban\_del [регулярное выражение] \- удалить регулярное выражение

 \- /g\_name\_regexpban\_add [регулярное выражение] \- добавить глобальное регулярное выражение
 \- /g\_name\_regexpban\_list \- перечислить все глобальные регулярные выражения
 \- /g\_name\_regexpban\_del [регулярное выражение] \- удалить глобальное регулярное выражение
"""

__mod_name__ = "Regexp имя бан"

REGEXPNAMEBAN_HANDLER = create_handler("name_regexpban_add", regexpnameban, filters=filters.ChatType.GROUPS)
LISTREGEXPNAMEBAN_HANDLER = create_handler("name_regexpban_list", listregexpnameban,
                                           filters=filters.ChatType.GROUPS)
UNBANREGEXPNAMEBAN_HANDLER = create_handler("name_regexpban_del", regexpnameunban,
                                            filters=filters.ChatType.GROUPS)

G_REGEXPNAMEBAN_HANDLER = create_handler("g_name_regexpban_add", g_regexpnameban,
                                         filters=filters.ChatType.GROUPS)
G_LISTREGEXPNAMEBAN_HANDLER = create_handler("g_name_regexpban_list", g_listregexpnameban,
                                             filters=filters.ChatType.GROUPS)
G_UNBANREGEXPNAMEBAN_HANDLER = create_handler("g_name_regexpban_del", g_regexpnameunban,
                                              filters=filters.ChatType.GROUPS)

application.add_handler(REGEXPNAMEBAN_HANDLER)
application.add_handler(LISTREGEXPNAMEBAN_HANDLER)
application.add_handler(UNBANREGEXPNAMEBAN_HANDLER)

application.add_handler(G_REGEXPNAMEBAN_HANDLER)
application.add_handler(G_LISTREGEXPNAMEBAN_HANDLER)
application.add_handler(G_UNBANREGEXPNAMEBAN_HANDLER)

PERM_GROUP = 6

application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, remove_banned_nicknames), PERM_GROUP)
