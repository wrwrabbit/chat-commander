import threading

from sqlalchemy import Column, BigInteger, UnicodeText, String, ForeignKey, func, Boolean, ForeignKeyConstraint

from tg_bot import dispatcher
from tg_bot.modules.sql import BASE, SESSION


class Users(BASE):
    __tablename__ = "users"
    user_id = Column(BigInteger, primary_key=True)
    is_channel = Column(Boolean, primary_key=True)
    username = Column(UnicodeText)

    def __init__(self, user_id, is_channel, username=None):
        self.user_id = user_id
        self.is_channel = is_channel
        self.username = username

    def __repr__(self):
        return "<User {} ({} is channel: )>".format(self.username, self.user_id, self.is_channel)


class Chats(BASE):
    __tablename__ = "chats"
    chat_id = Column(String(14), primary_key=True)
    chat_name = Column(UnicodeText, nullable=False)

    def __init__(self, chat_id, chat_name):
        self.chat_id = str(chat_id)
        self.chat_name = chat_name

    def __repr__(self):
        return "<Chat {} ({})>".format(self.chat_name, self.chat_id)


class ChatMembers(BASE):
    __tablename__ = "chat_members"
    priv_chat_id = Column(BigInteger, primary_key=True)
    # NOTE: Use dual primary key instead of private primary key?
    chat = Column(String(14),
                  ForeignKey("chats.chat_id",
                             onupdate="CASCADE",
                             ondelete="CASCADE"),
                  nullable=False)
    user_id = Column(BigInteger, nullable=False)
    is_channel = Column(Boolean, nullable=False)
    __table_args__ = (ForeignKeyConstraint([user_id, is_channel], [Users.user_id, Users.is_channel]), {})

    def __init__(self, chat, user_id, is_channel):
        self.chat = chat
        self.user_id = user_id
        self.is_channel = is_channel

    def __repr__(self):
        return "<Chat user {} ({}) in chat {} ({})>".format(self.user.user_id, self.user.is_channel,
                                                            self.chat.chat_name, self.chat.chat_id)


Users.__table__.create(checkfirst=True)
Chats.__table__.create(checkfirst=True)
ChatMembers.__table__.create(checkfirst=True)

INSERTION_LOCK = threading.RLock()


def ensure_bot_in_db():
    with INSERTION_LOCK:
        bot = Users(dispatcher.bot.id, False, dispatcher.bot.username)
        SESSION.merge(bot)
        SESSION.commit()


def update_user(user_id, is_channel, username, chat_id=None, chat_name=None):
    with INSERTION_LOCK:
        user = SESSION.query(Users).filter(Users.user_id == user_id, Users.is_channel == is_channel).first()
        if not user:
            user = Users(user_id, is_channel, username)
            SESSION.add(user)
            SESSION.flush()
        else:
            user.username = username

        if not chat_id or not chat_name:
            SESSION.commit()
            return

        chat = SESSION.query(Chats).get(str(chat_id))
        if not chat:
            chat = Chats(str(chat_id), chat_name)
            SESSION.add(chat)
            SESSION.flush()

        else:
            chat.chat_name = chat_name

        member = SESSION.query(ChatMembers).filter(ChatMembers.chat == chat.chat_id,
                                                   ChatMembers.user_id == user.user_id,
                                                   ChatMembers.is_channel == user.is_channel).first()
        if not member:
            chat_member = ChatMembers(chat.chat_id, user.user_id, is_channel)
            SESSION.add(chat_member)

        SESSION.commit()


def get_userid_by_name(username):
    try:
        return SESSION.query(Users).filter(func.lower(Users.username) == username.lower()).all()
    finally:
        SESSION.close()


def get_chat_members(chat_id):
    try:
        return SESSION.query(ChatMembers).filter(ChatMembers.chat == str(chat_id)).all()
    finally:
        SESSION.close()


def get_all_chats():
    try:
        return SESSION.query(Chats).all()
    finally:
        SESSION.close()


def get_user_num_chats(user_id, is_channel):
    try:
        return SESSION.query(ChatMembers).filter(ChatMembers.user_id == int(user_id),
                                                 ChatMembers.is_channel == is_channel).count()
    finally:
        SESSION.close()


def num_chats():
    try:
        return SESSION.query(Chats).count()
    finally:
        SESSION.close()


def num_users():
    try:
        return SESSION.query(Users).count()
    finally:
        SESSION.close()


def migrate_chat(old_chat_id, new_chat_id):
    with INSERTION_LOCK:
        chat = SESSION.query(Chats).get(str(old_chat_id))
        if chat:
            chat.chat_id = str(new_chat_id)
            SESSION.add(chat)

        SESSION.flush()

        chat_members = SESSION.query(ChatMembers).filter(ChatMembers.chat == str(old_chat_id)).all()
        for member in chat_members:
            member.chat = str(new_chat_id)
            SESSION.add(member)

        SESSION.commit()


ensure_bot_in_db()


def del_user(user_id, is_channel):
    with INSERTION_LOCK:
        curr = SESSION.query(Users).filter(Users.user_id == int(user_id), Users.is_channel == is_channel).first()
        if curr:
            SESSION.delete(curr)
            SESSION.commit()
            return True

        ChatMembers.query.filter(ChatMembers.user_id == int(user_id), ChatMembers.is_channel == is_channel).delete()
        SESSION.commit()
        SESSION.close()
    return False
