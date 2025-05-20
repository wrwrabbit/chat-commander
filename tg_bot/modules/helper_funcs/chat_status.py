from functools import wraps
from typing import Optional, Callable, Awaitable, Any

from telegram.constants import ChatType, ChatMemberStatus
from telegram import Chat, ChatMember, Update, ChatMemberAdministrator
from telegram.ext import ContextTypes

from tg_bot import DEL_CMDS, SUDO_USERS, WHITELIST_USERS


async def can_delete(chat: Chat, bot_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    member = await context.bot.get_chat_member(chat.id, bot_id)
    return (member.status == ChatMemberStatus.OWNER or
            (isinstance(member, ChatMemberAdministrator) and member.can_delete_messages))


async def is_user_ban_protected(
    chat: Chat,
    user_id: int,
    context: ContextTypes.DEFAULT_TYPE,
    member: Optional[ChatMember] = None,
) -> bool:
    if chat.type == ChatType.PRIVATE or user_id in SUDO_USERS or user_id in WHITELIST_USERS:
        return True

    if not member:
        member = await context.bot.get_chat_member(chat.id, user_id)
    return member.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER)


async def is_user_admin(
    chat: Chat,
    user_id: int,
    context: ContextTypes.DEFAULT_TYPE,
    member: Optional[ChatMember] = None,
) -> bool:
    if chat.type == ChatType.PRIVATE or user_id in SUDO_USERS:
        return True

    if not member:
        member = await context.bot.get_chat_member(chat.id, user_id)
    return member.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER)


async def is_bot_admin(
    chat: Chat,
    bot_id: int,
    context: ContextTypes.DEFAULT_TYPE,
    bot_member: Optional[ChatMember] = None,
) -> bool:
    if chat.type == ChatType.PRIVATE:
        return True

    if not bot_member:
        bot_member = await context.bot.get_chat_member(chat.id, bot_id)
    return bot_member.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER)


async def is_user_in_chat(chat: Chat, user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    member = await context.bot.get_chat_member(chat.id, user_id)
    return member.status not in (ChatMemberStatus.LEFT, ChatMemberStatus.BANNED)


def bot_can_delete(func: Callable[[Update, ContextTypes.DEFAULT_TYPE], Awaitable[Any]]):
    @wraps(func)
    async def delete_rights(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if await can_delete(update.effective_chat, context.bot.id, context):
            return await func(update, context)
        await update.effective_message.reply_text(
            "I can't delete messages here! Make sure I'm admin and can delete messages."
        )
    return delete_rights


def can_pin(func: Callable[[Update, ContextTypes.DEFAULT_TYPE], Awaitable[Any]]):
    @wraps(func)
    async def pin_rights(update: Update, context: ContextTypes.DEFAULT_TYPE):
        member = await context.bot.get_chat_member(update.effective_chat.id, context.bot.id)
        if isinstance(member, ChatMemberAdministrator) and member.can_pin_messages:
            return await func(update, context)
        await update.effective_message.reply_text("I can't pin messages here!")
    return pin_rights


def can_promote(func: Callable[[Update, ContextTypes.DEFAULT_TYPE], Awaitable[Any]]):
    @wraps(func)
    async def promote_rights(update: Update, context: ContextTypes.DEFAULT_TYPE):
        member = await context.bot.get_chat_member(update.effective_chat.id, context.bot.id)
        if isinstance(member, ChatMemberAdministrator) and member.can_promote_members:
            return await func(update, context)
        await update.effective_message.reply_text("I can't promote members here!")
    return promote_rights


def can_restrict(func: Callable[[Update, ContextTypes.DEFAULT_TYPE], Awaitable[Any]]):
    @wraps(func)
    async def promote_rights(update: Update, context: ContextTypes.DEFAULT_TYPE):
        member = await context.bot.get_chat_member(update.effective_chat.id, context.bot.id)
        if isinstance(member, ChatMemberAdministrator) and member.can_restrict_members:
            return await func(update, context)
        await update.effective_message.reply_text("I can't restrict members here!")
    return promote_rights


def bot_admin(func: Callable[[Update, ContextTypes.DEFAULT_TYPE], Awaitable[Any]]):
    @wraps(func)
    async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if await is_bot_admin(update.effective_chat, context.bot.id, context):
            return await func(update, context)
        await update.effective_message.reply_text("I'm not admin in this chat!")
    return is_admin


def user_admin(func: Callable[[Update, ContextTypes.DEFAULT_TYPE], Awaitable[Any]]):
    @wraps(func)
    async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if user and await is_user_admin(update.effective_chat, user.id, context):
            return await func(update, context)

        if DEL_CMDS and update.effective_message:
            await update.effective_message.delete()
        else:
            await update.effective_message.reply_text("This command is for admins only!")
    return is_admin


def user_admin_no_reply(func: Callable[[Update, ContextTypes.DEFAULT_TYPE], Awaitable[Any]]):
    @wraps(func)
    async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if user and await is_user_admin(update.effective_chat, user.id, context):
            return await func(update, context)

        if DEL_CMDS and update.effective_message:
            await update.effective_message.delete()
    return is_admin


def user_not_admin(func: Callable[[Update, ContextTypes.DEFAULT_TYPE], Awaitable[Any]]):
    @wraps(func)
    async def is_not_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if user and not await is_user_admin(update.effective_chat, user.id, context):
            return await func(update, context)
    return is_not_admin