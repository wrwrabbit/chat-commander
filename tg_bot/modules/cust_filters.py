import re
from typing import Optional

import telegram
from telegram import InlineKeyboardMarkup, Message, Chat
from telegram import Update
from telegram.constants import ParseMode, MessageLimit
from telegram.error import BadRequest
from telegram.ext import MessageHandler, ApplicationHandlerStop, ContextTypes
from telegram.helpers import escape_markdown

from tg_bot import application, LOGGER
from tg_bot.modules.helper_funcs.chat_status import user_admin
from tg_bot.modules.helper_funcs.extraction import extract_text
from tg_bot.modules.helper_funcs.filters import CustomFilters
from tg_bot.modules.helper_funcs.handlers import create_handler
from tg_bot.modules.disable import DisableAbleCommandHandler
from tg_bot.modules.helper_funcs.misc import build_keyboard
from tg_bot.modules.helper_funcs.string_handling import split_quotes, button_markdown_parser_v2
from tg_bot.modules.sql import cust_filters_sql as sql

HANDLER_GROUP = 10
BASIC_FILTER_STRING = "*Filters in this chat\\:*\n"  # MARKDOWN_V2: escape colon


async def list_handlers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat  # type: Optional[Chat]
    all_handlers = sql.get_chat_triggers(chat.id)

    if not all_handlers:
        await update.effective_message.reply_text("No filters are active here!")
        return

    filter_list = BASIC_FILTER_STRING
    for keyword in all_handlers:
        entry = " \\- {}\n".format(escape_markdown(keyword, version=2))  # Escape dash for MARKDOWN_V2
        if len(entry) + len(filter_list) > MessageLimit.MAX_TEXT_LENGTH:
            await update.effective_message.reply_text(filter_list, parse_mode=ParseMode.MARKDOWN_V2)
            filter_list = entry
        else:
            filter_list += entry

    if not filter_list == BASIC_FILTER_STRING:
        await update.effective_message.reply_text(filter_list, parse_mode=ParseMode.MARKDOWN_V2)


@user_admin
async def filters(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat  # type: Optional[Chat]
    msg = update.effective_message  # type: Optional[Message]
    args = msg.text.split(None, 1)  # use python's maxsplit to separate Cmd, keyword, and reply_text

    if len(args) < 2:
        return

    extracted = split_quotes(args[1])
    if len(extracted) < 1:
        return
    # set trigger -> lower, so as to avoid adding duplicate filters with different cases
    keyword = extracted[0].lower()

    is_sticker = False
    is_document = False
    is_image = False
    is_voice = False
    is_audio = False
    is_video = False
    buttons = []

    # determine what the contents of the filter are - text, image, sticker, etc
    if len(extracted) >= 2:
        offset = len(extracted[1]) - len(msg.text)  # set correct offset relative to command + notename
        content, buttons = button_markdown_parser_v2(extracted[1], entities=msg.parse_entities(), offset=offset)
        content = content.strip()
        if not content:
            await msg.reply_text("There is no note message - You can't JUST have buttons, you need a message to go with it!")
            return

    elif msg.reply_to_message and msg.reply_to_message.sticker:
        content = msg.reply_to_message.sticker.file_id
        is_sticker = True

    elif msg.reply_to_message and msg.reply_to_message.document:
        content = msg.reply_to_message.document.file_id
        is_document = True

    elif msg.reply_to_message and msg.reply_to_message.photo:
        content = msg.reply_to_message.photo[-1].file_id  # last elem = best quality
        is_image = True

    elif msg.reply_to_message and msg.reply_to_message.audio:
        content = msg.reply_to_message.audio.file_id
        is_audio = True

    elif msg.reply_to_message and msg.reply_to_message.voice:
        content = msg.reply_to_message.voice.file_id
        is_voice = True

    elif msg.reply_to_message and msg.reply_to_message.video:
        content = msg.reply_to_message.video.file_id
        is_video = True

    else:
        await msg.reply_text("You didn't specify what to reply with!")
        return

    # Add the filter to database
    # Note: In async version, we use a single handler that checks all filters from database
    # No need to create/remove individual handlers for each keyword
    sql.add_filter(chat.id, keyword, content, is_sticker, is_document, is_image, is_audio, is_voice, is_video,
                   buttons)

    await msg.reply_text("Handler '{}' added!".format(keyword))
    raise ApplicationHandlerStop


@user_admin
async def stop_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat  # type: Optional[Chat]
    args = update.effective_message.text.split(None, 1)

    if len(args) < 2:
        return

    chat_filters = sql.get_chat_triggers(chat.id)

    if not chat_filters:
        await update.effective_message.reply_text("No filters are active here!")
        return

    for keyword in chat_filters:
        if keyword == args[1]:
            sql.remove_filter(chat.id, args[1])
            await update.effective_message.reply_text("Yep, I'll stop replying to that.")
            raise ApplicationHandlerStop

    await update.effective_message.reply_text("That's not a current filter - run /filters for all active filters.")


async def reply_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat  # type: Optional[Chat]
    message = update.effective_message  # type: Optional[Message]
    to_match = extract_text(message)
    if not to_match:
        return

    chat_filters = sql.get_chat_triggers(chat.id)
    for keyword in chat_filters:
        pattern = r"( |^|[^\w])" + re.escape(keyword) + r"( |$|[^\w])"
        if re.search(pattern, to_match, flags=re.IGNORECASE):
            filt = sql.get_filter(chat.id, keyword)
            if filt.is_sticker:
                await message.reply_sticker(filt.reply)
            elif filt.is_document:
                await message.reply_document(filt.reply)
            elif filt.is_image:
                await message.reply_photo(filt.reply)
            elif filt.is_audio:
                await message.reply_audio(filt.reply)
            elif filt.is_voice:
                await message.reply_voice(filt.reply)
            elif filt.is_video:
                await message.reply_video(filt.reply)
            elif filt.has_markdown:
                buttons = sql.get_buttons(chat.id, filt.keyword)
                keyb = build_keyboard(buttons)
                keyboard = InlineKeyboardMarkup(keyb)

                try:
                    await message.reply_text(filt.reply, parse_mode=ParseMode.MARKDOWN_V2,
                                       disable_web_page_preview=True,
                                       reply_markup=keyboard)
                except BadRequest as excp:
                    if excp.message == "Unsupported url protocol":
                        await message.reply_text("You seem to be trying to use an unsupported url protocol. Telegram "
                                           "doesn't support buttons for some protocols, such as tg://. Please try "
                                           "again, or ask in @MarieSupport for help.")
                    elif excp.message == "Reply message not found":
                        await context.bot.send_message(chat.id, filt.reply, parse_mode=ParseMode.MARKDOWN_V2,
                                         disable_web_page_preview=True,
                                         reply_markup=keyboard)
                    elif "can't parse entities" in excp.message.lower() or "parse error" in excp.message.lower():
                        # Fallback to HTML if MARKDOWN_V2 parsing fails (for legacy filters)
                        try:
                            await message.reply_text(filt.reply, parse_mode=ParseMode.HTML,
                                           disable_web_page_preview=True,
                                           reply_markup=keyboard)
                        except BadRequest:
                            # Last resort: send without formatting
                            await message.reply_text(filt.reply, disable_web_page_preview=True, reply_markup=keyboard)
                    else:
                        await message.reply_text("This note could not be sent, as it is incorrectly formatted. Ask in "
                                           "@MarieSupport if you can't figure out why!")
                        LOGGER.warning("Message %s could not be parsed", str(filt.reply))
                        LOGGER.exception("Could not parse filter %s in chat %s", str(filt.keyword), str(chat.id))

            else:
                # LEGACY - all new filters will have has_markdown set to True.
                await message.reply_text(filt.reply)
            break


def __stats__():
    return "{} filters, across {} chats.".format(sql.num_filters(), sql.num_chats())


def __migrate__(old_chat_id, new_chat_id):
    sql.migrate_chat(old_chat_id, new_chat_id)


def __chat_settings__(chat_id, user_id):
    cust_filters = sql.get_chat_triggers(chat_id)
    # Escape period for MARKDOWN_V2 (used with ParseMode.MARKDOWN_V2 in __main__.py)
    return r"There are `{}` custom filters here\.".format(len(cust_filters))


__help__ = r"""
 Автоответы \(фильтры\) отвечают на сообщения содержащие ключевые слова\.
 
 \- /filters: список всех активных фильтров в этом чате\.

\*Только администратор:\*
 \- /filter \<ключевое слово\> \<ответное сообщение\>: добавить фильтр в этот чат\. Теперь бот будет отвечать на сообщения, \
в которых упоминается 'ключевое слово'\. Если вы ответите данной командой на стикер то 'ответное сообщение' будет этот стикер\. ПРИМЕЧАНИЕ: все \
ключевые слова должны быть написаны строчными буквами\. Если вы хотите, чтобы ваше ключевое слово было предложением, используйте кавычки\. например: /filter "привет лох" Как дела?
 \- /stop \<ключевое слово\>: остановить этот фильтр\.
"""

__mod_name__ = "Автоответы"

FILTER_HANDLER = create_handler("filter", filters)
STOP_HANDLER = create_handler("stop", stop_filter)
LIST_HANDLER = DisableAbleCommandHandler("filters", list_handlers, admin_ok=True)
CUST_FILTER_HANDLER = MessageHandler(CustomFilters.has_text, reply_filter)

application.add_handler(FILTER_HANDLER)
application.add_handler(STOP_HANDLER)
application.add_handler(LIST_HANDLER)
application.add_handler(CUST_FILTER_HANDLER, HANDLER_GROUP)
