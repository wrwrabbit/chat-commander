from asyncio import Lock
from datetime import datetime, timedelta
import importlib
import re
from typing import Optional

from telegram import Message, Chat, Update, Bot
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.constants import ParseMode, ChatType
from telegram.error import BadRequest, TimedOut, NetworkError, ChatMigrated, TelegramError, Forbidden
from telegram.ext import ContextTypes, MessageHandler, CallbackQueryHandler, filters, ApplicationHandlerStop
from telegram.helpers import escape_markdown

from tg_bot.modules.helper_funcs.handlers import create_handler
from tg_bot import application, TOKEN, WEBHOOK, DONATION_LINK, CERT_PATH, PORT, URL, LOGGER, ALLOW_EXCL
# needed to dynamically load modules
# NOTE: Module order is not guaranteed, specify that in the config file!
from tg_bot.modules import ALL_MODULES
from tg_bot.modules.helper_funcs.chat_status import is_user_admin
from tg_bot.modules.helper_funcs.misc import paginate_modules

PM_START_TEXT = """
Hi {}, my name is {}\! If you have any questions on how to use me, read /help \- and then head to @MarieSupport\.

I\'m a group manager bot built in python3, using the python\-telegram\-bot library, and am fully opensource; \
you can find what makes me tick [here](github.com/PaulSonOfLars/tgbot)\!

Feel free to submit pull requests on github, or to contact my support group, @MarieSupport, with any bugs, questions \
or feature requests you might have :\)
I also have a news channel, @MarieNews for announcements on new features, downtime, etc\.

You can find the list of available commands with /help\.

If you\'re enjoying using me, and/or would like to help me survive in the wild, hit /donate to help fund/upgrade my \
VPS\!
"""

HELP_STRINGS = "Depricated"
_HELP_STRINGS_CACHE: Optional[str] = None
_HELP_STRING_TEMPLATE: str = """
Hey there\! My name is *{bot_name}*\.
I'm a modular group management bot with a few fun extras\! Have a look at the following for an idea of some of \\
the things I can help you with\.

*Main* commands available:
 \- /start: start the bot\.
 \- /help: PM's you this message\.
 \- /help \<module name\>: PM's you info about that module\.
 \- /donate: information about how to donate\!
 \- /settings:
   \- in PM: will send you your settings for all supported modules\.
   \- in a group: will redirect you to pm, with all that chat's settings\.

{allow_excl_info}
And the following:
"""


async def get_formatted_help_string() -> str:
    """
    Асинхронно получает имя бота (если еще не получено)
    и форматирует HELP_STRINGS. Кэширует результат.
    """
    global _HELP_STRINGS_CACHE
    if _HELP_STRINGS_CACHE is None:
        try:
            # Предполагаем, что application.initialize() был вызван при старте,
            # так как bot.get_me() этого требует.
            bot_info = await application.bot.get_me()
            actual_bot_name = escape_markdown(bot_info.first_name, version=2)
        except Exception as e:
            LOGGER.error(f"Could not get bot name for HELP_STRINGS: {e}", exc_info=True)
            actual_bot_name = "[Unknown Bot Name]"  # Заглушка в случае ошибки

        allow_excl_text = "" if not ALLOW_EXCL else "\\nAll commands can either be used with / or \!\.\\n"

        # Формируем основную часть строки помощи, которая может включать ALLOW_EXCL
        _HELP_STRINGS_CACHE = _HELP_STRING_TEMPLATE.format(
            bot_name=actual_bot_name,
            allow_excl_info=allow_excl_text  # Это должно быть частью шаблона _HELP_STRING_TEMPLATE
        )

    return _HELP_STRINGS_CACHE

DONATE_STRING = DONATION_LINK

IMPORTED = {}
MIGRATEABLE = []
HELPABLE = {}
STATS = []
USER_INFO = []
DATA_IMPORT = []
DATA_EXPORT = []

CHAT_SETTINGS = {}
USER_SETTINGS = {}

GDPR = []

for module_name in ALL_MODULES:
    imported_module = importlib.import_module("tg_bot.modules." + module_name)
    if not hasattr(imported_module, "__mod_name__"):
        imported_module.__mod_name__ = imported_module.__name__

    if not imported_module.__mod_name__.lower() in IMPORTED:
        IMPORTED[imported_module.__mod_name__.lower()] = imported_module
    else:
        raise Exception("Can't have two modules with the same name! Please change one")

    if hasattr(imported_module, "__help__") and imported_module.__help__:
        HELPABLE[imported_module.__mod_name__.lower()] = imported_module

    # Chats to migrate on chat_migrated events
    if hasattr(imported_module, "__migrate__"):
        MIGRATEABLE.append(imported_module)

    if hasattr(imported_module, "__stats__"):
        STATS.append(imported_module)

    if hasattr(imported_module, "__gdpr__"):
        GDPR.append(imported_module)

    if hasattr(imported_module, "__user_info__"):
        USER_INFO.append(imported_module)

    if hasattr(imported_module, "__import_data__"):
        DATA_IMPORT.append(imported_module)

    if hasattr(imported_module, "__export_data__"):
        DATA_EXPORT.append(imported_module)

    if hasattr(imported_module, "__chat_settings__"):
        CHAT_SETTINGS[imported_module.__mod_name__.lower()] = imported_module

    if hasattr(imported_module, "__user_settings__"):
        USER_SETTINGS[imported_module.__mod_name__.lower()] = imported_module




async def send_help(chat_id, text, keyboard=None):
    if not keyboard:
        keyboard = InlineKeyboardMarkup(paginate_modules(0, HELPABLE, "help"))
    await application.bot.send_message(chat_id=chat_id,
                                text=text,
                                parse_mode=ParseMode.MARKDOWN_V2,
                                reply_markup=keyboard)


async def test(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    print(update.to_dict())
    await update.effective_message.reply_text(r"Hola tester\! _I_ *have* `markdown`", parse_mode=ParseMode.MARKDOWN_V2)
    # await update.effective_message.reply_text("This person edited a message")
    print(update.effective_message)



async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Получаем аргументы команды (без учёта регистра)
    args = context.args
    chat = update.effective_chat
    message = update.effective_message
    if chat.type == ChatType.PRIVATE:
        user = update.effective_user
        if args:
            arg = args[0].lower()

            # Обработка /start help
            if arg == "help":
                await send_help(chat.id, await get_formatted_help_string())

            # Обработка /start stngs_<chat_id>
            elif arg.startswith("stngs_"):
                if match := re.match(r"stngs_(.*)", arg):
                    chat_to_manage = await context.bot.get_chat(match.group(1))
                    is_admin = await is_user_admin(chat_to_manage, user.id, context)
                    await send_settings(
                            context,
                            chat_id=match.group(1),
                            user_id=user.id,
                            user=not is_admin
                    )

            # Обработка /start <номер> (для правил)
            elif arg.lstrip('-').isdigit() and "rules" in IMPORTED:
                await IMPORTED["rules"].send_rules(update, arg, from_pm=True)

        else:
            first_name = user.first_name
            await message.reply_text(
                PM_START_TEXT.format(escape_markdown(first_name, version=2),
                                     escape_markdown(context.bot.first_name, version=2)),
                parse_mode=ParseMode.MARKDOWN_V2)
    else:
        await message.reply_text("Yo, whadup?")


# for test purposes
async def error_callback(_: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    error = context.error

    try:
        raise error
    except Forbidden:
        print("Forbidden")
        print(f"Детали: {error}")
        # remove update.message.chat_id from conversation list
    except BadRequest:
        print("BadRequest caught")
        print(f"Детали: {error}")
        # handle malformed requests - read more below!
    except TimedOut:
        print("TimedOut")
        # handle slow connection problems
    except NetworkError:
        print("NetworkError")
        # handle other connection problems
    except ChatMigrated as err:
        print(f"ChatMigrated : {err.new_chat_id}")
        print(f"Детали: {err}")
        # the chat_id of a group has changed, use e.new_chat_id instead
    except TelegramError:
        print("TelegramError")
        print(f"Детали: {error}")
        # handle all other telegram related errors



async def help_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    mod_match = re.match(r"help_module\((.+?)\)", query.data)
    prev_match = re.match(r"help_prev\((.+?)\)", query.data)
    next_match = re.match(r"help_next\((.+?)\)", query.data)
    back_match = re.match(r"help_back", query.data)
    
    current_help_text = await get_formatted_help_string()

    try:
        if mod_match:
            module_name_from_callback = mod_match.group(1)
            if module_name_from_callback in HELPABLE:
                module_data = HELPABLE[module_name_from_callback]
                text = f"Вот справка для модуля *{module_data.__mod_name__}*:\n{module_data.__help__}"
                await query.edit_message_text(
                    text=text,
                    parse_mode=ParseMode.MARKDOWN_V2,
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton(text="Назад", callback_data="help_back")]
                    ])
                )
            else:
                LOGGER.warning(f"Module '{module_name_from_callback}' not found in HELPABLE. Callback data: {query.data}")
                await context.bot.answer_callback_query(query.id, text="Информация для этого модуля не найдена.", show_alert=True)
                return
        elif prev_match:
            curr_page = int(prev_match.group(1))
            await query.edit_message_text(
                current_help_text,
                parse_mode=ParseMode.MARKDOWN_V2,
                reply_markup=InlineKeyboardMarkup(paginate_modules(curr_page - 1, HELPABLE, "help"))
            )
        elif next_match:
            next_page = int(next_match.group(1))
            await query.edit_message_text(
                current_help_text,
                parse_mode=ParseMode.MARKDOWN_V2,
                reply_markup=InlineKeyboardMarkup(paginate_modules(next_page + 1, HELPABLE, "help"))
            )

        elif back_match:
            await query.edit_message_text(
                text=current_help_text,
                parse_mode=ParseMode.MARKDOWN_V2,
                reply_markup=InlineKeyboardMarkup(paginate_modules(0, HELPABLE, "help"))
            )

        # ТОЛЬКО подтверждаем callback-запрос (удаление сообщения убрано)
        await context.bot.answer_callback_query(query.id)
    except BadRequest as excp:
        LOGGER.exception("Exception %s in help buttons. %s", excp.message, str(query.data))
        if excp.message == "Message is not modified":
            pass
        elif excp.message == "Query_id_invalid":
            pass
        elif excp.message == "Message can't be deleted":
            pass
        elif "Query is too old" in excp.message:
            await context.bot.send_message(query.message.chat.id, "Menu is expired. Please type '/help' to open new menu")
            pass



async def get_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat  # type: Optional[Chat]
    args = update.effective_message.text.split(None, 1)

    current_help_text = await get_formatted_help_string()

    if chat.type != ChatType.PRIVATE:
        await update.effective_message.reply_text(
            "Contact me in PM to get the list of possible commands.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(text="Help", url=f"t.me/{context.bot.username}?start=help")]
            ])
        )
        return

    elif len(args) >= 2:
        requested_module_name = args[1].lower()
        if requested_module_name in HELPABLE:
            module_data = HELPABLE[requested_module_name]
            text = f"Here is the available help for the *{module_data.__mod_name__}* module:\n{module_data.__help__}"
            await send_help(chat.id, text, InlineKeyboardMarkup([
                [InlineKeyboardButton(text="Назад", callback_data="help_back")]
            ]))
        else:
            await update.effective_message.reply_text(f"Модуль '{args[1]}' не найден. Попробуйте /help.")
    else:
        await send_help(chat.id, current_help_text)


async def send_settings(context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_id: int, user: bool = False) -> None:
    if user:
        if USER_SETTINGS:
            settings = "\n\n".join(
                "*{}*:\n{}".format(escape_markdown(mod.__mod_name__, version=2), mod.__user_settings__(user_id)
            ) for mod in USER_SETTINGS.values())
            await context.bot.send_message(user_id, "These are your current settings:" + "\n\n" + settings,
                                           parse_mode=ParseMode.MARKDOWN_V2)
        else:
            await context.bot.send_message(chat_id=user_id,
                                           text="Seems like there aren\'t any user specific settings available :\(",
                                           parse_mode=ParseMode.MARKDOWN_V2)
    else:
        if CHAT_SETTINGS:
            chat = await context.bot.get_chat(chat_id)
            await context.bot.send_message(
                chat_id=user_id,
                text="Which module would you like to check {}\'s settings for?".format(
                    escape_markdown(chat.title, version=2)),
                reply_markup=InlineKeyboardMarkup(
                    paginate_modules(0, CHAT_SETTINGS, "stngs", chat=chat_id)
            ), parse_mode=ParseMode.MARKDOWN_V2)
        else:
            await context.bot.send_message(chat_id=user_id,
                text="Seems like there aren\'t any chat settings available :\(\n"
                     "Send this in a group chat you\'re admin in to find its current settings\!",
                parse_mode=ParseMode.MARKDOWN_V2)



async def settings_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user = update.effective_user
    mod_match = re.match(r"stngs_module\((.+?),(.+?)\)", query.data)
    prev_match = re.match(r"stngs_prev\((.+?),(.+?)\)", query.data)
    next_match = re.match(r"stngs_next\((.+?),(.+?)\)", query.data)
    back_match = re.match(r"stngs_back\((.+?)\)", query.data)

    await query.answer()  # Подтверждаем нажатие
    try:
        if mod_match:
            chat_id = mod_match.group(1)
            module = mod_match.group(2)
            chat = await context.bot.get_chat(int(chat_id))
            text = "*{}* has the following settings for the *{}* module:\n\n".format(
                escape_markdown(chat.title, version=2),
                escape_markdown(CHAT_SETTINGS[module].__mod_name__, version=2)) + \
                   CHAT_SETTINGS[module].__chat_settings__(chat_id, user.id)
            await query.edit_message_text(text=text,
                                          parse_mode=ParseMode.MARKDOWN_V2,
                                          reply_markup=InlineKeyboardMarkup(
                                         [[InlineKeyboardButton(text="Назад",
                                                                callback_data="stngs_back({})".format(chat_id))]]))

        elif prev_match:
            chat_id = prev_match.group(1)
            curr_page = int(prev_match.group(2))
            chat = await context.bot.get_chat(int(chat_id))
            await query.edit_message_text("Hi there\! There are quite a few settings for {} - go ahead and pick what "
                                     "you\'re interested in\.".format(escape_markdown(chat.title, version=2)),
                                          parse_mode=ParseMode.MARKDOWN_V2,
                                          reply_markup=InlineKeyboardMarkup(
                                              paginate_modules(curr_page - 1, CHAT_SETTINGS, "stngs",
                                                               chat=chat_id)))

        elif next_match:
            chat_id = next_match.group(1)
            next_page = int(next_match.group(2))
            chat = await context.bot.get_chat(int(chat_id))
            await query.edit_message_text("Hi there\! There are quite a few settings for {} - go ahead and pick what "
                                     "you\'re interested in\.".format(escape_markdown(chat.title, version=2)),
                                          parse_mode=ParseMode.MARKDOWN_V2,
                                          reply_markup=InlineKeyboardMarkup(
                                              paginate_modules(next_page + 1, CHAT_SETTINGS, "stngs",
                                                               chat=chat_id)))

        elif back_match:
            chat_id = back_match.group(1)
            chat = await context.bot.get_chat(int(chat_id))
            await query.edit_message_text(text="Hi there\! There are quite a few settings for {} \- go ahead and pick what "
                                          "you\'re interested in\.".format(escape_markdown(chat.title, version=2)),
                                     parse_mode=ParseMode.MARKDOWN_V2,
                                     reply_markup=InlineKeyboardMarkup(
                                         paginate_modules(0, CHAT_SETTINGS, "stngs",
                                                          chat=chat_id)))

        # ensure no spinny white circle
        await query.answer()
    except BadRequest as excp:
        LOGGER.exception("Exception %s in settings buttons. %s", excp.message, str(query.data))


async def get_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    user = update.effective_user
    message = update.effective_message

    # ONLY send settings in PM
    if chat.type != chat.PRIVATE:
        if await is_user_admin(chat, user.id, context):
            text = "Click here to get this chat\'s settings, as well as yours."
        else:
            text = "Click here to check your settings."

        await message.reply_text(
            text=text,
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton(text="Settings",
                        url=f"t.me/{context.bot.username}?start=stngs_{chat.id}")]]))
    else:
        await send_settings(context, chat.id, user.id, user=True)



def donate(bot: Bot, update: Update):
    user = update.effective_message.from_user
    chat = update.effective_chat  # type: Optional[Chat]

    if chat.type == "private":
        update.effective_message.reply_text(DONATE_STRING, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)

        if DONATION_LINK:
            update.effective_message.reply_text("You can also donate to the person currently running me "
                                                "[here]({})".format(DONATION_LINK),
                                                parse_mode=ParseMode.MARKDOWN)

    else:
        try:
            bot.send_message(user.id, DONATE_STRING, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)

            update.effective_message.reply_text("Я скинул вам ссылку с информацией как нам можно присылать донаты.")
        except Forbidden:
            update.effective_message.reply_text("Напишите мне /donate в личном сообщении.")


def migrate_chats(bot: Bot, update: Update):
    msg = update.effective_message  # type: Optional[Message]
    if msg.migrate_to_chat_id:
        old_chat = update.effective_chat.id
        new_chat = msg.migrate_to_chat_id
    elif msg.migrate_from_chat_id:
        old_chat = msg.migrate_from_chat_id
        new_chat = update.effective_chat.id
    else:
        return

    LOGGER.info("Migrating from %s, to %s", str(old_chat), str(new_chat))
    for mod in MIGRATEABLE:
        mod.__migrate__(old_chat, new_chat)

    LOGGER.info("Successfully migrated!")
    return


def main():
    # add antiflood processor. Must be before any application.add_handler
    rate_limiter = RateLimitMiddleware()
    application.add_handler(MessageHandler(filters.ALL, rate_limiter.check), group=-1)

    test_handler = create_handler("test", test)
    start_handler = create_handler("start", start)

    help_handler = create_handler("help", get_help)
    help_callback_handler = CallbackQueryHandler(help_button, pattern=r"help_")

    settings_handler = create_handler("settings", get_settings)
    settings_callback_handler = CallbackQueryHandler(settings_button, pattern=r"stngs_")

    #donate_handler = CommandHandler("donate", donate)
    #migrate_handler = MessageHandler(Filters.status_update.migrate, migrate_chats)

    application.add_handler(test_handler)
    application.add_handler(start_handler)
    application.add_handler(help_handler)
    application.add_handler(settings_handler)
    application.add_handler(help_callback_handler)
    application.add_handler(settings_callback_handler)
    #dispatcher.add_handler(migrate_handler)
    #dispatcher.add_handler(donate_handler)

    #application.add_error_handler(error_callback)


    if WEBHOOK:
        LOGGER.info("Using webhooks.")
        if CERT_PATH:
            application.run_webhook(
                listen="0.0.0.0",
                port=PORT,
                url_path=TOKEN,
                webhook_url=URL + TOKEN,
                cert=CERT_PATH)
        else:
            application.run_webhook(
                listen="0.0.0.0",
                port=PORT,
                url_path=TOKEN,
                webhook_url=URL + TOKEN)
    else:
        LOGGER.info("Using long polling.")
        application.run_polling()

class RateLimitMiddleware:
    def __init__(self):
        self._global_lock = Lock()
        self.locks = {}  # Regular dict
        self.user_limits = {}  # {user_id: (last_time, count)}

    async def check(self, update: Update, context:ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id

        async with self._global_lock:
            if user_id not in self.locks:
                self.locks[user_id] = Lock()

        async with self.locks[user_id]:
            now = datetime.now()
            last_time, cnt = self.user_limits.get(user_id, (now, 0))

            if now - last_time < timedelta(seconds=1):  # Проверяем, прошла ли 1 секунда
                cnt += 1
                if cnt > 10:  # Лимит: 10 запросов в секунду
                    try:
                        LOGGER.info(f"Слишком много запросов! Подождите секунду. user_id={user_id}")

                        await context.bot.delete_message(
                            chat_id=chat_id,
                            message_id=update.effective_message.message_id,
                        )
                    finally:
                        raise ApplicationHandlerStop
            else:
                cnt = 1  # Сброс счётчика, если прошла 1 сек

            self.user_limits[user_id] = (now, cnt)


if __name__ == '__main__':
    LOGGER.info("Successfully loaded modules: " + str(ALL_MODULES))
    main()
