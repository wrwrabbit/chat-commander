from typing import Union, List, Optional, Callable, Awaitable, Any
from functools import wraps

from future.utils import string_types
from telegram import Update, MessageEntity
from telegram.constants import ParseMode
from telegram.ext import CommandHandler, MessageHandler, ContextTypes, filters
from telegram.helpers import escape_markdown

from tg_bot import application
from tg_bot.modules.helper_funcs.handlers import CMD_STARTERS, create_handler
from tg_bot.modules.helper_funcs.misc import is_module_loaded

FILENAME = __name__.rsplit(".", 1)[-1]

# If module is due to be loaded, then setup all the magical handlers
if is_module_loaded(FILENAME):
    from tg_bot.modules.helper_funcs.chat_status import user_admin, is_user_admin

    from tg_bot.modules.sql import disable_sql as sql

    DISABLE_CMDS = []
    DISABLE_OTHER = []
    ADMIN_CMDS = []

    def check_command_enabled(admin_ok: bool = False):
        """
        Decorator to check if a command is enabled before executing the handler.
        If command is disabled and admin_ok=True, allows execution for admins only.
        
        Usage:
            @check_command_enabled(admin_ok=True)
            async def my_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
                ...
        """
        def decorator(func: Callable[[Update, ContextTypes.DEFAULT_TYPE], Awaitable[Any]]):
            @wraps(func)
            async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
                if not update.effective_message or not update.effective_message.text:
                    return await func(update, context)
                
                # Extract command name from message entities
                message = update.effective_message
                if message.entities and message.entities[0].type == MessageEntity.BOT_COMMAND:
                    # Extract command name (without / and @botname)
                    command_text = message.text[message.entities[0].offset:message.entities[0].offset + message.entities[0].length]
                    command = command_text[1:].split('@')[0].lower()  # Remove / and @botname
                else:
                    # Not a command, proceed normally
                    return await func(update, context)
                
                chat = update.effective_chat
                
                # Check if command is disabled
                if sql.is_command_disabled(chat.id, command):
                    if admin_ok:
                        # Check if user is admin
                        user = update.effective_user
                        if user and await is_user_admin(chat, user.id, context):
                            # Admin can use disabled command
                            return await func(update, context)
                        # Not admin, command is disabled
                        return None
                    else:
                        # Command is disabled and not admin_ok
                        return None
                
                # Command is enabled, proceed normally
                return await func(update, context)
            return wrapper
        return decorator

    class DisableAbleCommandHandler:
        """
        Handler that supports command disabling with optional admin override.
        Uses create_handler internally to support ALLOW_EXCL (prefixes / and !).
        """
        def __init__(self, command, callback, admin_ok=False, **kwargs):
            # Register command in DISABLE_CMDS
            if isinstance(command, string_types):
                DISABLE_CMDS.append(command)
                if admin_ok:
                    ADMIN_CMDS.append(command)
            else:
                DISABLE_CMDS.extend(command)
                if admin_ok:
                    ADMIN_CMDS.extend(command)
            
            # Apply decorator to callback
            wrapped_callback = check_command_enabled(admin_ok=admin_ok)(callback)
            
            # Use create_handler to support ALLOW_EXCL
            self.handler = create_handler(command, wrapped_callback, **kwargs)
        
        def __getattr__(self, name):
            # Delegate all attribute access to the underlying handler
            return getattr(self.handler, name)


    class DisableAbleRegexHandler(MessageHandler):
        def __init__(self, pattern, callback, friendly="", **kwargs):
            # Use filters.Regex instead of RegexHandler
            regex_filter = filters.Regex(pattern)
            super().__init__(regex_filter, callback, **kwargs)
            DISABLE_OTHER.append(friendly or pattern)
            self.friendly = friendly or pattern

        def check_update(self, update):
            chat = update.effective_chat
            if super().check_update(update):
                return not sql.is_command_disabled(chat.id, self.friendly)
            return None


    @user_admin
    async def disable(update: Update, context: ContextTypes.DEFAULT_TYPE):
        args = context.args
        chat = update.effective_chat  # type: Optional[Chat]
        if args and len(args) >= 1:
            disable_cmd = args[0]
            if disable_cmd.startswith(CMD_STARTERS):
                disable_cmd = disable_cmd[1:]

            if disable_cmd in set(DISABLE_CMDS + DISABLE_OTHER):
                sql.disable_command(chat.id, disable_cmd)
                await update.effective_message.reply_text("Disabled the use of `{}`".format(disable_cmd),
                                                          parse_mode=ParseMode.MARKDOWN)
            else:
                await update.effective_message.reply_text("That command can't be disabled")

        else:
            await update.effective_message.reply_text("What should I disable?")


    @user_admin
    async def enable(update: Update, context: ContextTypes.DEFAULT_TYPE):
        args = context.args
        chat = update.effective_chat  # type: Optional[Chat]
        if args and len(args) >= 1:
            enable_cmd = args[0]
            if enable_cmd.startswith(CMD_STARTERS):
                enable_cmd = enable_cmd[1:]

            if sql.enable_command(chat.id, enable_cmd):
                await update.effective_message.reply_text("Enabled the use of `{}`".format(enable_cmd),
                                                          parse_mode=ParseMode.MARKDOWN)
            else:
                await update.effective_message.reply_text("Is that even disabled?")

        else:
            await update.effective_message.reply_text("What should I enable?")


    @user_admin
    async def list_cmds(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if DISABLE_CMDS + DISABLE_OTHER:
            result = ""
            for cmd in set(DISABLE_CMDS + DISABLE_OTHER):
                result += " - `{}`\n".format(escape_markdown(cmd))
            await update.effective_message.reply_text("The following commands are toggleable:\n{}".format(result),
                                                      parse_mode=ParseMode.MARKDOWN)
        else:
            await update.effective_message.reply_text("No commands can be disabled.")


    # do not async
    def build_curr_disabled(chat_id: Union[str, int]) -> str:
        disabled = sql.get_all_disabled(chat_id)
        if not disabled:
            return "No commands are disabled!"

        result = ""
        for cmd in disabled:
            result += " - `{}`\n".format(escape_markdown(cmd))
        return "The following commands are currently restricted:\n{}".format(result)


    async def commands(update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat = update.effective_chat
        await update.effective_message.reply_text(build_curr_disabled(chat.id), parse_mode=ParseMode.MARKDOWN)


    def __stats__():
        return "{} disabled items, across {} chats.".format(sql.num_disabled(), sql.num_chats())


    def __migrate__(old_chat_id, new_chat_id):
        sql.migrate_chat(old_chat_id, new_chat_id)


    def __chat_settings__(chat_id, user_id):
        return build_curr_disabled(chat_id)


    __mod_name__ = "Отключение команд"

    __help__ = r"""
 \- /cmds: проверить текущий статус отключенных команд

\*Только администратор:\*
 \- /disable \<имя команды\>: отключить эту команду
 \- /enable \<имя команды\>: отменить отключение команды
 \- /listcmds: перечислить все возможные отключаемые команды
    """

    DISABLE_HANDLER = create_handler("disable", disable, filters=filters.ChatType.GROUPS)
    ENABLE_HANDLER = create_handler("enable", enable, filters=filters.ChatType.GROUPS)
    COMMANDS_HANDLER = create_handler(["cmds", "disabled"], commands, filters=filters.ChatType.GROUPS)
    TOGGLE_HANDLER = create_handler("listcmds", list_cmds, filters=filters.ChatType.GROUPS)

    application.add_handler(DISABLE_HANDLER)
    application.add_handler(ENABLE_HANDLER)
    application.add_handler(COMMANDS_HANDLER)
    application.add_handler(TOGGLE_HANDLER)

else:
    # If module is not loaded, use create_handler directly
    def DisableAbleCommandHandler(command, callback, admin_ok=False, **kwargs):
        return create_handler(command, callback, **kwargs)
    
    DisableAbleRegexHandler = MessageHandler
