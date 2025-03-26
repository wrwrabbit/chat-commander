from telegram.ext import CommandHandler, PrefixHandler
from typing import Callable
from tg_bot import ALLOW_EXCL


CMD_STARTERS = ('/', '!')

def create_handler(command: str, callback: Callable, **kwargs):
    if ALLOW_EXCL:
        if "admin_ok" in kwargs:
            del kwargs["admin_ok"]

        main_handler = PrefixHandler(CMD_STARTERS, command, callback, **kwargs)

        return main_handler,  # Обычные команды
    else:
        return CommandHandler(command, callback, **kwargs)
