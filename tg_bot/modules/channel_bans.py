import html
from typing import Optional

from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters
from telegram import MessageOriginChannel
from telegram.helpers import mention_html

from tg_bot import application, SUDO_USERS
from tg_bot.modules.helper_funcs.chat_status import user_admin, bot_can_delete
from tg_bot.modules.log_channel import loggable
from tg_bot.modules.helper_funcs.handlers import create_handler
from tg_bot.modules.sql import channel_bans_sql as sql


@user_admin
@bot_can_delete
@loggable
async def ban_channel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    args = context.args
    if not args:
        await update.effective_message.reply_text("Please provide a channel name")
        return ""
    channel_name = args[0]
    chat = update.effective_chat
    user = update.effective_user
    chat_id = chat.id
    sql.add_channel_bans(chat_id, channel_name)
    await update.effective_message.reply_text("Channel was added to ban list")
    
    log = "<b>{}:</b>" \
          "\n#CHANNEL_BANNED" \
          "\n<b>Admin:</b> {}" \
          "\n<b>Channel:</b> <code>{}</code>".format(html.escape(chat.title),
                                                     mention_html(user.id, user.first_name),
                                                     html.escape(channel_name))
    return log


@user_admin
@loggable
async def unban_channel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    args = context.args
    if not args:
        await update.effective_message.reply_text("Please provide a channel name")
        return ""
    channel_name = args[0]
    chat = update.effective_chat
    user = update.effective_user
    chat_id = chat.id
    sql.delete_channel_ban(chat_id, channel_name)
    await update.effective_message.reply_text("Channel was removed from ban list")
    
    log = "<b>{}:</b>" \
          "\n#CHANNEL_UNBANNED" \
          "\n<b>Admin:</b> {}" \
          "\n<b>Channel:</b> <code>{}</code>".format(html.escape(chat.title),
                                                     mention_html(user.id, user.first_name),
                                                     html.escape(channel_name))
    return log


@user_admin
async def banned_channels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    res = sql.get_channel_bans(chat.id)
    if res is not None:
        res = list(map(lambda x: x.channel_to_ban, res))
        await update.effective_message.reply_text("Channels banned in this chat: " + ','.join(res))
    else:
        await update.effective_message.reply_text("There are no channels in ban")


@user_admin
@bot_can_delete
@loggable
async def global_ban_channel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    args = context.args
    if not args:
        await update.effective_message.reply_text("Please provide a channel name")
        return ""
    if int(update.effective_user.id) not in SUDO_USERS:
        await update.effective_message.reply_text("Only SUDO users can use this command")
        return ""
    channel_name = args[0]
    chat = update.effective_chat
    user = update.effective_user
    sql.add_channel_global_bans(channel_name)
    await update.effective_message.reply_text("Channel " + channel_name + " was added to global ban list")
    
    log = "<b>{}:</b>" \
          "\n#GLOBAL_CHANNEL_BANNED" \
          "\n<b>Admin:</b> {}" \
          "\n<b>Channel:</b> <code>{}</code>".format(html.escape(chat.title),
                                                     mention_html(user.id, user.first_name),
                                                     html.escape(channel_name))
    return log


@user_admin
@loggable
async def global_unban_channel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    args = context.args
    if not args:
        await update.effective_message.reply_text("Please provide a channel name")
        return ""
    if int(update.effective_user.id) not in SUDO_USERS:
        await update.effective_message.reply_text("Only SUDO users can use this command")
        return ""
    channel_name = args[0]
    chat = update.effective_chat
    user = update.effective_user
    sql.delete_channel_global_ban(channel_name)
    await update.effective_message.reply_text("Channel " + channel_name + " was removed from global ban list")
    
    log = "<b>{}:</b>" \
          "\n#GLOBAL_CHANNEL_UNBANNED" \
          "\n<b>Admin:</b> {}" \
          "\n<b>Channel:</b> <code>{}</code>".format(html.escape(chat.title),
                                                    mention_html(user.id, user.first_name),
                                                    html.escape(channel_name))
    return log


@user_admin
async def global_banned_channels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if int(update.effective_user.id) not in SUDO_USERS:
        await update.effective_message.reply_text("Only SUDO users can use this command")
        return
    res = sql.get_channel_global_bans()
    if res is not None:
        res = list(map(lambda x: x.channel_to_ban, res))
        await update.effective_message.reply_text("Channels banned globally: " + ','.join(res))
    else:
        await update.effective_message.reply_text("There are no channels in global ban")


async def remove_banned_forwardings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_message.forward_origin is not None:
        forward_origin = update.effective_message.forward_origin
        
        if isinstance(forward_origin, MessageOriginChannel):
            origin_chat = forward_origin.chat
            if origin_chat:
                chat_info = await context.bot.get_chat(origin_chat.id)
                forwarder_from_channel_name = chat_info.username or chat_info.title
                
                if forwarder_from_channel_name:
                    is_exists = sql.is_channel_ban_exists(update.effective_chat.id, forwarder_from_channel_name)
                    if is_exists:
                        if update.effective_message.caption is not None:
                            await update.effective_message.reply_text(
                                "Channel " + forwarder_from_channel_name + " banned in this channel")
                        await update.effective_message.delete()
                        return
                    
                    is_exists_in_global = sql.is_global_channel_ban_exists(forwarder_from_channel_name)
                    if is_exists_in_global:
                        if update.effective_message.caption is not None:
                            await update.effective_message.reply_text("Channel " + forwarder_from_channel_name + " banned in global ban list")
                        await update.effective_message.delete()
                        return


def __migrate__(old_chat_id, new_chat_id):
    sql.migrate_chat(old_chat_id, new_chat_id)


__help__ = r"""
Имя канала, например \- channel\_name \(без @\)
*Администратор:*
 \- /banchannel \<имя канала\>: добавить канал в список запрещенных каналов в этой группе
 \- /unbanchannel \<имя канала\>: удалить канал из списка запрещенных каналов в этой группе
 \- /bannedchannels: показать список всех запрещенных каналов
 \- /gbanchannel \<имя канала\>: добавить канал в глобальный список запрещенных каналов
 \- /gunbanchannel \<имя канала\>: удалить канал из глобального списка запрещенных каналов
 \- /gbannedchannels: показать список всех глобальных запрещенных каналов
"""

__mod_name__ = "Бан Каналов"

BAN_CHANNEL_HANDLER = create_handler("banchannel", ban_channel, filters=filters.ChatType.GROUPS)
UNBAN_CHANNEL_HANDLER = create_handler("unbanchannel", unban_channel, filters=filters.ChatType.GROUPS)
BANNED_CHANNELS_HANDLER = create_handler("bannedchannels", banned_channels, filters=filters.ChatType.GROUPS)
GLOBAL_BAN_CHANNEL_HANDLER = create_handler("gbanchannel", global_ban_channel, filters=filters.ChatType.GROUPS)
GLOBAL_UNBAN_CHANNEL_HANDLER = create_handler("gunbanchannel", global_unban_channel, filters=filters.ChatType.GROUPS)
GLOBAL_BANNED_CHANNELS_HANDLER = create_handler("gbannedchannels", global_banned_channels, filters=filters.ChatType.GROUPS)

application.add_handler(BAN_CHANNEL_HANDLER)
application.add_handler(UNBAN_CHANNEL_HANDLER)
application.add_handler(BANNED_CHANNELS_HANDLER)
application.add_handler(GLOBAL_BAN_CHANNEL_HANDLER)
application.add_handler(GLOBAL_UNBAN_CHANNEL_HANDLER)
application.add_handler(GLOBAL_BANNED_CHANNELS_HANDLER)

PERM_GROUP = 5

application.add_handler(MessageHandler(filters.FORWARDED & filters.ChatType.GROUPS, remove_banned_forwardings),
                       PERM_GROUP)
