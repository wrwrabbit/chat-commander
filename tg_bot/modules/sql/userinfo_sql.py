import threading

from sqlalchemy import Column, BigInteger, UnicodeText, Boolean

from tg_bot.modules.sql import SESSION, BASE


class UserBio(BASE):
    __tablename__ = "userbio"
    user_id = Column(BigInteger, primary_key=True)
    is_channel = Column(Boolean, primary_key=True)
    bio = Column(UnicodeText)

    def __init__(self, user_id, is_channel, bio):
        self.user_id = user_id
        self.is_channel = is_channel
        self.bio = bio

    def __repr__(self):
        return "<User info %d>" % self.user_id


UserBio.__table__.create(checkfirst=True)

INSERTION_LOCK = threading.RLock()


def get_user_bio(user_id, is_channel):
    userbio = SESSION.query(UserBio).filter(UserBio.user_id == user_id, UserBio.is_channel == is_channel).first()
    SESSION.close()
    if userbio:
        return userbio.bio
    return None


def set_user_bio(user_id, is_channel, bio):
    with INSERTION_LOCK:
        userbio = SESSION.query(UserBio).filter(UserBio.user_id == user_id, UserBio.is_channel == is_channel).first()
        if userbio:
            userbio.bio = bio
        else:
            userbio = UserBio(user_id, is_channel, bio)
        SESSION.add(userbio)
        SESSION.commit()


def clear_user_bio(user_id, is_channel):
    with INSERTION_LOCK:
        curr = SESSION.query(UserBio).filter(UserBio.user_id == user_id, UserBio.is_channel == is_channel).first()
        if curr:
            SESSION.delete(curr)
            SESSION.commit()
            return True
        SESSION.close()
    return False
