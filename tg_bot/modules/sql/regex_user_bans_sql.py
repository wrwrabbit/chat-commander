import threading

from sqlalchemy import Column, BigInteger, UnicodeText

from tg_bot.modules.sql import SESSION, BASE, ENGINE


class RegexUserBan(BASE):
    __tablename__ = "user_regex_ban"
    id = Column(BigInteger, primary_key=True)
    chat_id = Column(BigInteger)
    regex_to_ban = Column(UnicodeText)

    def __init__(self, chat_id, regex_to_ban):
        self.chat_id = chat_id
        self.regex_to_ban = regex_to_ban

    def __repr__(self):
        return "<Ban regex %s> " % self.regex_to_ban,


class RegexUserGlobalBan(BASE):
    __tablename__ = "global_user_regex_ban"
    id = Column(BigInteger, primary_key=True)
    regex_to_ban = Column(UnicodeText)

    def __init__(self, regex_to_ban):
        self.regex_to_ban = regex_to_ban

    def __repr__(self):
        return "<User global regex ban regex_to_ban %s>" % self.regex_to_ban


class UserBanExclusion(BASE):
    __tablename__ = "user_ban_exclusion"
    id = Column(BigInteger, primary_key=True)
    username_to_exclude = Column(UnicodeText)

    def __init__(self, username_to_exclude):
        self.username_to_exclude = username_to_exclude

    def __repr__(self):
        return "<User ban exclusion %s>" % self.username_to_exclude


RegexUserBan.__table__.create(checkfirst=True, bind=ENGINE)
RegexUserGlobalBan.__table__.create(checkfirst=True, bind=ENGINE)
UserBanExclusion.__table__.create(checkfirst=True, bind=ENGINE)

REGEX_BAN_INSERTION_LOCK = threading.RLock()
REGEX_GLOBAL_BAN_INSERTION_LOCK = threading.RLock()
USER_BAN_EXCLUSION_LOCK = threading.RLock()


def add_ban_exclusion(username_to_exclude):
    with USER_BAN_EXCLUSION_LOCK:
        user_ban_exclusion = UserBanExclusion(username_to_exclude)
        SESSION.merge(user_ban_exclusion)
        SESSION.commit()


def add_regex_bans(chat_id, regex_to_ban):
    with REGEX_BAN_INSERTION_LOCK:
        regex_bans = RegexUserBan(chat_id, regex_to_ban)
        SESSION.merge(regex_bans)
        SESSION.commit()


def get_regex_bans(chat_id):
    regex_bans = SESSION.query(RegexUserBan).filter(RegexUserBan.chat_id == chat_id).all()
    SESSION.close()
    if regex_bans:
        return regex_bans
    return []


def get_ban_exclusions():
    result = SESSION.query(UserBanExclusion).all()
    SESSION.close()
    if result:
        return result
    return []


def is_regex_ban_exists(chat_id, regex_to_ban):
    is_exists = SESSION.query(RegexUserBan).filter(RegexUserBan.chat_id == chat_id,
                                                   RegexUserBan.regex_to_ban == regex_to_ban).first() is not None
    SESSION.close()
    return is_exists


def is_ban_exclusion_exists(username):
    is_exists = SESSION.query(RegexUserBan).filter(UserBanExclusion.username_to_exclude == username).first() is not None
    SESSION.close()
    return is_exists


def delete_regex_ban(chat_id, regex_to_ban):
    with REGEX_BAN_INSERTION_LOCK:
        regex_ban = SESSION.query(RegexUserBan).filter(RegexUserBan.chat_id == chat_id,
                                                       RegexUserBan.regex_to_ban == regex_to_ban).first()
        if regex_ban:
            SESSION.delete(regex_ban)
            SESSION.commit()
            return True
        SESSION.close()
    return False


def delete_ban_exclusion(username_to_exclude):
    with USER_BAN_EXCLUSION_LOCK:
        user_ban_exclusion = SESSION.query(UserBanExclusion).filter(
            UserBanExclusion.username_to_exclude == username_to_exclude
        ).first()
        if user_ban_exclusion:
            SESSION.delete(user_ban_exclusion)
            SESSION.commit()
            return True
        SESSION.close()
    return False


def add_regex_global_bans(regex_to_ban):
    with REGEX_GLOBAL_BAN_INSERTION_LOCK:
        regex_bans = RegexUserGlobalBan(regex_to_ban)
        SESSION.merge(regex_bans)
        SESSION.commit()


def get_regex_global_bans():
    regex_global_bans = SESSION.query(RegexUserGlobalBan).all()
    SESSION.close()
    if regex_global_bans:
        return regex_global_bans
    return []


# def is_global_regex_ban_exists(regex_global_ban):
#     is_exists = SESSION.query(RegexUserGlobalBan).filter(RegexUserGlobalBan.regex_to_ban == regex_global_ban).first() is not None
#     SESSION.close()
#     return is_exists


def delete_regex_global_ban(regex_global_ban):
    with REGEX_GLOBAL_BAN_INSERTION_LOCK:
        regex_global_ban = SESSION.query(RegexUserGlobalBan).filter(
            RegexUserGlobalBan.regex_to_ban == regex_global_ban).first()
        if regex_global_ban:
            SESSION.delete(regex_global_ban)
            SESSION.commit()
            return True
        SESSION.close()
    return False


def migrate_chat(old_chat_id, new_chat_id):
    with REGEX_BAN_INSERTION_LOCK:
        regex_bans = SESSION.query(RegexUserBan).filter(RegexUserBan.chat_id == old_chat_id)
        for regex_ban in regex_bans:
            regex_ban.chat_id = str(new_chat_id)
        SESSION.commit()
