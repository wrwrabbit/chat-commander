from telegram import Update
from telegram.ext import CommandHandler, filters, MessageHandler
from typing import cast
from tg_bot import ALLOW_EXCL

CMD_STARTERS = ('/', '!')

def create_handler(command, callback, **kwargs):
    if ALLOW_EXCL:
        return CommandHandler(command, callback, **kwargs)
    else:
        return CustomCommandHandler(command, callback, **kwargs)

class CustomCommandHandler(CommandHandler):
    def __init__(self, command, callback, **kwargs):
        if "admin_ok" in kwargs:
            del kwargs["admin_ok"]
        super().__init__(command, callback, **kwargs)

    def check_update(self, update: object) -> bool:
        if isinstance(update, Update) and (update.message or update.edited_message):
            return False
        update = cast(Update, update)
        message = update.message or update.edited_message

        if not message or not message.text or len(message.text) <= 1:
            return False

        text = getattr(message, 'html_text', message.text)
        fst_word = text.split(None, 1)[0]
        if not (len(fst_word) > 1 and any(fst_word.startswith(start) for start in CMD_STARTERS)):
            return False

        command = fst_word[1:].split('@')
        command.append(update.get_bot().username)  # in case the command was sent without a username
        if self.filters is None:
            res = True
        elif isinstance(self.filters, list):
            res = any(func(message) for func in self.filters)
        else:
            res = self.filters.check_update(update)

        return res and (command[0].lower() in self.commands
                                    and command[1].lower() == update.get_bot().username.lower())

class CustomRegexHandler(MessageHandler):
    def __init__(self, pattern, callback, _="", **kwargs):
        super().__init__(filters.Regex(pattern), callback, **kwargs)

# make sure the regex handler can take extra kwargs
# need to update any code that uses these handlers to accommodate other API changes in version 20+
#tg.RegexHandler = CustomRegexHandler

