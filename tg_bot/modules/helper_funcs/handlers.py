from telegram.ext import CommandHandler, PrefixHandler, MessageHandler, filters
from typing import Union, List, Callable, Optional
from tg_bot import ALLOW_EXCL


CMD_STARTERS = ('/', '!')

def create_handler(command: str, callback: Callable, **kwargs):
    if ALLOW_EXCL:
        if "admin_ok" in kwargs:
            del kwargs["admin_ok"]

        main_handler = PrefixHandler(CMD_STARTERS, command, callback, **kwargs)
        edited_filter = (
                filters.UpdateType.EDITED_MESSAGE &
                filters.Text([f"{p}{command}" for p in CMD_STARTERS])
        )

        return [
            main_handler,  # Обычные команды
пше            MessageHandler(edited_filter, callback)  # Редактированные
        ]
    else:
        return CommandHandler(command, callback, **kwargs)
