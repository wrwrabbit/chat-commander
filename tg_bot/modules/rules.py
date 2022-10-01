from typing import Optional

from telegram import Message, Update, Bot, User
from telegram import ParseMode, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.error import BadRequest
from telegram.ext import CommandHandler, run_async, Filters
from telegram.utils.helpers import escape_markdown

import tg_bot.modules.sql.rules_sql as sql
from tg_bot import dispatcher
from tg_bot.modules.helper_funcs.chat_status import user_admin
from tg_bot.modules.helper_funcs.string_handling import markdown_parser


# @run_async
def get_rules(bot: Bot, update: Update):
    chat_id = update.effective_chat.id
    rules = sql.get_rules(chat_id)
    if rules:
        update.effective_message.reply_text(rules, parse_mode=ParseMode.MARKDOWN)
    else:
        update.effective_message.reply_text("The group admins haven't set any rules for this chat yet. "
                                            "This probably doesn't  mean it's lawless though...!")


# @run_async
@user_admin
def set_rules(bot: Bot, update: Update):
    chat_id = update.effective_chat.id
    msg = update.effective_message  # type: Optional[Message]
    raw_text = msg.text
    args = raw_text.split(None, 1)  # use python's maxsplit to separate cmd and args
    if len(args) == 2:
        txt = args[1]
        offset = len(txt) - len(raw_text)  # set correct offset relative to command
        markdown_rules = markdown_parser(txt, entities=msg.parse_entities(), offset=offset)

        sql.set_rules(chat_id, markdown_rules)
        update.effective_message.reply_text("Successfully set rules for this group.")


# @run_async
@user_admin
def clear_rules(bot: Bot, update: Update):
    chat_id = update.effective_chat.id
    sql.set_rules(chat_id, "")
    update.effective_message.reply_text("Successfully cleared rules!")


def __stats__():
    return "{} chats have rules set.".format(sql.num_chats())


def __import_data__(chat_id, data):
    # set chat rules
    rules = data.get('info', {}).get('rules', "")
    sql.set_rules(chat_id, rules)


def __migrate__(old_chat_id, new_chat_id):
    sql.migrate_chat(old_chat_id, new_chat_id)


def __chat_settings__(chat_id, user_id):
    return "This chat has had it's rules set: `{}`".format(bool(sql.get_rules(chat_id)))


__help__ = """
 - /rules: получить правила для этого чата.

*Только администратор:*
 - /setrules <текст правил>: установить правила для этого чата.
 - /clearrules: очистить правила для этого чата
"""

__mod_name__ = "Правила чата"

GET_RULES_HANDLER = CommandHandler("rules", get_rules, filters=Filters.chat_type.groups)
SET_RULES_HANDLER = CommandHandler("setrules", set_rules, filters=Filters.chat_type.groups)
RESET_RULES_HANDLER = CommandHandler("clearrules", clear_rules, filters=Filters.chat_type.groups)

dispatcher.add_handler(GET_RULES_HANDLER)
dispatcher.add_handler(SET_RULES_HANDLER)
dispatcher.add_handler(RESET_RULES_HANDLER)
