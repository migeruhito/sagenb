from __future__ import absolute_import

from .config import UAT_ADMIN
from .config import UAT_GUEST
from .config import UAT_USER
from .config import UN_SYSTEM


class User(object):
    def __init__(self, user_model):
        self.__user_model = user_model

    # Exposed model attributes

    @property
    def username(self):
        """
        Expose model.username read only
        """
        return self.__user_model.username

    # Utility methods

    @property
    def login_allowed(self):
        return self.usename not in UN_SYSTEM

    @property
    def is_admin(self):
        """
        EXAMPLES::

            sage: from sagenb.notebook.user import User
            sage: User('A', account_type='admin').is_admin
            True
            sage: User('B', account_type='user').is_admin
            False
        """
        return self.__user_model.account_type == UAT_ADMIN

    @property
    def is_guest(self):
        """
        EXAMPLES::

            sage: from sagenb.notebook.user import User
            sage: User('A', account_type='guest').is_guest
            True
            sage: User('B', account_type='user').is_guest
            False
        """
        return self.__user_model.account_type == UAT_GUEST

    def grant_admin(self):
        if not self.is_guest:
            self.__user_model.account_type = UAT_ADMIN

    def revoke_admin(self):
        if not self.is_guest:
            self.__user_model.account_type = UAT_USER
