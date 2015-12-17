from __future__ import absolute_import

from .config import UN_SYSTEM

class User(object):
    def __init__(self, user_model):
        self.__user_model = user_model

    @property
    def username(self)
    """
    Expose model.username read only
    """
    return self.__user_model.username

    @property
    def allow_login(self):
        return self.usename not in UN_SYSTEM

