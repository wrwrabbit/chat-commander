import html
from io import BytesIO
from typing import Optional, List

from telegram import Update, ChatMemberAdministrator
from telegram.error import BadRequest, TelegramError
from telegram.ext import ContextTypes, MessageHandler, filters
from telegram.helpers import mention_html
from telegram.constants import ChatType, ChatMemberStatus

import tg_bot.modules.sql.global_bans_sql as sql
from tg_bot import application, OWNER_ID, SUDO_USERS, SUPPORT_USERS, STRICT_GBAN
from tg_bot.modules.helper_funcs.chat_status import user_admin, is_user_admin
from tg_bot.modules.helper_funcs.extraction import extract_user_and_is_channel, extract_user_and_text_and_is_channel
from tg_bot.modules.helper_funcs.filters import CustomFilters
from tg_bot.modules.helper_funcs.misc import send_to_list
from tg_bot.modules.helper_funcs.handlers import create_handler
from tg_bot.modules.sql.users_sql import get_all_chats

GBAN_ENFORCE_GROUP = 6

GBAN_ERRORS = {
    "User is an administrator of the chat",
    "Chat not found",
    "Not enough rights to restrict/unrestrict chat member",
    "User_not_participant",
    "Peer_id_invalid",
    "Group chat was deactivated",
    "Need to be inviter of a user to kick it from a basic group",
    "Chat_admin_required",
    "Only the creator of a basic group can kick group administrators",
    "Channel_private",
    "Not in the chat"
}

UNGBAN_ERRORS = {
    "User is an administrator of the chat",
    "Chat not found",
    "Not enough rights to restrict/unrestrict chat member",
    "User_not_participant",
    "Method is available for supergroup and channel chats only",
    "Not in the chat",
    "Channel_private",
    "Chat_admin_required",
    "Peer_id_invalid",
}


async def gban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if int(update.effective_user.id) not in SUDO_USERS:
        await update.effective_message.reply_text("Only SUDO users can use this command")
        return
    
    message = update.effective_message  # type: Optional[Message]
    chat = update.effective_chat

    user_id, reason, is_channel = await extract_user_and_text_and_is_channel(message, args)

    if not user_id:
        await message.reply_text("You don't seem to be referring to a user.")
        return

    if int(user_id) in SUDO_USERS:
        await message.reply_text("I spy, with my little eye... a sudo user war! Why are you guys turning on each other?")
        return

    if int(user_id) in SUPPORT_USERS:
        await message.reply_text("OOOH someone's trying to gban a support user! *grabs popcorn*")
        return

    if user_id == context.bot.id:
        await message.reply_text("-_- So funny, lets gban myself why don't I? Nice try.")
        return

    try:
        user_chat = await context.bot.get_chat(user_id)
    except BadRequest as excp:
        await message.reply_text(excp.message)
        return

    if sql.is_user_gbanned(user_id, is_channel):
        if not reason:
            await message.reply_text("This user is already gbanned; I'd change the reason, but you haven't given me one...")
            return

        old_reason = sql.update_gban_reason(user_id, is_channel, user_chat.username or user_chat.first_name, reason)
        if old_reason:
            await message.reply_text("This user is already gbanned, for the following reason:\n"
                               "<code>{}</code>\n"
                               "I've gone and updated it with your new reason!".format(html.escape(old_reason)),
                               parse_mode="HTML")
        else:
            await message.reply_text("This user is already gbanned, but had no reason set; I've gone and updated it!")

        return

    await message.reply_text("*Blows dust off of banhammer* 😉")

    banner = update.effective_user  # type: Optional[User]
    await send_to_list(context.bot, SUDO_USERS + SUPPORT_USERS,
                 "{} is gbanning user {} "
                 "because:\n{}".format(mention_html(banner.id, banner.first_name),
                                       mention_html(user_chat.id, user_chat.username or user_chat.first_name),
                                       reason or "No reason given"),
                 html=True)

    sql.gban_user(user_id, is_channel, user_chat.username or user_chat.first_name, reason)

    chats = get_all_chats()
    for chat_obj in chats:
        chat_id = chat_obj.chat_id

        # Check if this group has disabled gbans
        if not sql.does_chat_gban(chat_id):
            continue

        try:
            if not is_channel:
                await context.bot.ban_chat_member(chat_id, user_id)
            else:
                await context.bot.ban_chat_sender_chat(chat_id, user_id)
        except BadRequest as excp:
            if excp.message in GBAN_ERRORS:
                pass
            else:
                await message.reply_text("Could not gban due to: {}".format(excp.message))
                await send_to_list(context.bot, SUDO_USERS + SUPPORT_USERS, "Could not gban due to: {}".format(excp.message))
                sql.ungban_user(user_id, is_channel)
                return
        except TelegramError:
            pass

    await send_to_list(context.bot, SUDO_USERS + SUPPORT_USERS, "gban complete!")
    await message.reply_text("Person has been gbanned.")


async def ungban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if int(update.effective_user.id) not in SUDO_USERS:
        await update.effective_message.reply_text("Only SUDO users can use this command")
        return
    
    message = update.effective_message  # type: Optional[Message]

    user_id, is_channel = await extract_user_and_is_channel(message, args)
    if not user_id:
        await message.reply_text("You don't seem to be referring to a user.")
        return

    user_chat = await context.bot.get_chat(user_id)

    if not sql.is_user_gbanned(user_id, is_channel):
        await message.reply_text("This user is not gbanned!")
        return

    banner = update.effective_user  # type: Optional[User]

    await message.reply_text("I'll give {} a second chance, globally.".format(user_chat.username or user_chat.first_name))

    await send_to_list(context.bot, SUDO_USERS + SUPPORT_USERS,
                 "{} has ungbanned user {}".format(mention_html(banner.id, banner.first_name),
                                                   mention_html(user_chat.id, user_chat.username or user_chat.first_name)),
                 html=True)

    chats = get_all_chats()
    for chat_obj in chats:
        chat_id = chat_obj.chat_id

        # Check if this group has disabled gbans
        if not sql.does_chat_gban(chat_id):
            continue

        try:
            if not is_channel:
                member = await context.bot.get_chat_member(chat_id, user_id)
                if member.status == ChatMemberStatus.BANNED:
                    await context.bot.unban_chat_member(chat_id, user_id)
            else:
                await context.bot.unban_chat_sender_chat(chat_id, user_id)

        except BadRequest as excp:
            if excp.message in UNGBAN_ERRORS:
                pass
            else:
                await message.reply_text("Could not un-gban due to: {}".format(excp.message))
                await context.bot.send_message(OWNER_ID, "Could not un-gban due to: {}".format(excp.message))
                return
        except TelegramError:
            pass

    sql.ungban_user(user_id, is_channel)

    await send_to_list(context.bot, SUDO_USERS + SUPPORT_USERS, "un-gban complete!")

    await message.reply_text("Person has been un-gbanned.")


async def gbanlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    banned_users = sql.get_gban_list()

    if not banned_users:
        await update.effective_message.reply_text("There aren't any gbanned users! You're kinder than I expected...")
        return

    banfile = 'Screw these guys.\n'
    for user in banned_users:
        banfile += "[x] {} - {}\n".format(user["name"], user["user_id"])
        if user["reason"]:
            banfile += "Reason: {}\n".format(user["reason"])

    with BytesIO(str.encode(banfile)) as output:
        output.name = "gbanlist.txt"
        await update.effective_message.reply_document(document=output, filename="gbanlist.txt",
                                                caption="Here is the list of currently gbanned users.")


async def check_and_ban(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id, is_channel, should_message=True):
    if sql.is_user_gbanned(user_id, is_channel):
        if not is_channel:
            await update.effective_chat.ban_member(user_id)
        else:
            await update.effective_chat.ban_sender_chat(user_id)
        if should_message:
            await update.effective_message.reply_text("This is a bad person, they shouldn't be here!")


async def enforce_gban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Not using @restrict handler to avoid spamming - just ignore if cant gban.
    if sql.does_chat_gban(update.effective_chat.id):
        try:
            bot_member = await context.bot.get_chat_member(update.effective_chat.id, context.bot.id)
            if not (isinstance(bot_member, ChatMemberAdministrator) and bot_member.can_restrict_members):
                return
        except BadRequest:
            return

        user = update.effective_user  # type: Optional[User]
        chat = update.effective_chat  # type: Optional[Chat]
        msg = update.effective_message  # type: Optional[Message]

        is_channel = update.effective_message.sender_chat is not None

        if user and not await is_user_admin(chat, user.id, context):
            await check_and_ban(update, context, user.id, is_channel)

        if msg.new_chat_members:
            new_members = update.effective_message.new_chat_members
            for mem in new_members:
                await check_and_ban(update, context, mem.id, is_channel)

        if msg.reply_to_message:
            user = msg.reply_to_message.from_user  # type: Optional[User]
            if user and not await is_user_admin(chat, user.id, context):
                await check_and_ban(update, context, user.id, is_channel, should_message=False)


@user_admin
async def gbanstat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) > 0:
        if args[0].lower() in ["on", "yes"]:
            sql.enable_gbans(update.effective_chat.id)
            await update.effective_message.reply_text("I've enabled gbans in this group. This will help protect you "
                                                "from spammers, unsavoury characters, and the biggest trolls.")
        elif args[0].lower() in ["off", "no"]:
            sql.disable_gbans(update.effective_chat.id)
            await update.effective_message.reply_text("I've disabled gbans in this group. GBans wont affect your users "
                                                "anymore. You'll be less protected from any trolls and spammers "
                                                "though!")
    else:
        await update.effective_message.reply_text("Give me some arguments to choose a setting! on/off, yes/no!\n\n"
                                            "Your current setting is: {}\n"
                                            "When True, any gbans that happen will also happen in your group. "
                                            "When False, they won't, leaving you at the possible mercy of "
                                            "spammers.".format(sql.does_chat_gban(update.effective_chat.id)))


def __stats__():
    return "{} gbanned users.".format(sql.num_gbanned_users())


def __user_info__(user_id, is_channel):
    is_gbanned = sql.is_user_gbanned(user_id, is_channel)

    text = "Globally banned: <b>{}</b>"
    if is_gbanned:
        text = text.format("Yes")
        user = sql.get_gbanned_user(user_id, is_channel)
        if user.reason:
            text += "\nReason: {}".format(html.escape(user.reason))
    else:
        text = text.format("No")
    return text


def __migrate__(old_chat_id, new_chat_id):
    sql.migrate_chat(old_chat_id, new_chat_id)


def __chat_settings__(chat_id, user_id):
    return r"This chat is enforcing *gbans*: `{}`\.".format(sql.does_chat_gban(chat_id))


__help__ = r"""
Gbans, также известные как глобальные баны, используются владельцами ботов для блокировки спамеров во всех группах\. \
Это помогает защитить вас и ваши группы, удаляя спам\-флудеры как можно быстрее\. Их можно отключить для вашей группы \
командой /gbanstat\.

 \- /gbanlist : перечислить глобально забаненных пользователей\.

\*Только администратор:\*
 \- /gbanstat \<on/off/yes/no\>: отключит действие глобальных банов на вашу группу или вернет ваши текущие настройки\.
 
 \*Только SUDO администратор:\*
 \- /gban : забанить пользователя глобально\.
 \- /ungban : разблокировать пользователя глобально\.
"""

__mod_name__ = "Глобальные баны"

GBAN_HANDLER = create_handler("gban", gban, filters=CustomFilters.sudo_filter | CustomFilters.support_filter)
UNGBAN_HANDLER = create_handler("ungban", ungban, filters=CustomFilters.sudo_filter | CustomFilters.support_filter)
GBAN_LIST = create_handler("gbanlist", gbanlist, filters=CustomFilters.sudo_filter | CustomFilters.support_filter)

GBAN_STATUS = create_handler("gbanstat", gbanstat, filters=filters.ChatType.GROUPS)

GBAN_ENFORCER = MessageHandler(filters.ALL & filters.ChatType.GROUPS, enforce_gban)

application.add_handler(GBAN_HANDLER)
application.add_handler(UNGBAN_HANDLER)
application.add_handler(GBAN_LIST)
application.add_handler(GBAN_STATUS)

if STRICT_GBAN:  # enforce GBANS if this is set
    application.add_handler(GBAN_ENFORCER, GBAN_ENFORCE_GROUP)
