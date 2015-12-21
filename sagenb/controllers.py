from __future__ import absolute_import

import crypt

from .models import User as UserModel
from .models import UserConfiguration
from .config import SALT
from .config import UAT_ADMIN
from .config import UAT_GUEST
from .config import UAT_USER
from .config import UN_SYSTEM
from .util.auth import encrypt_password


class User(object):
    @classmethod
    def from_basic(cls, basic):
        conf = basic.pop('conf')
        conf = UserConfiguration.from_basic(conf)
        new = cls(UserModel(conf=conf, **basic))
        return new

    @classmethod
    def new(cls, username, password='', email='', account_type='admin',
            external_auth=None):
        """
        create a new user model with encrypted password and return the
        corresponding user controller.
        """
        user = cls(UserModel(
            username, email=email, account_type=account_type,
            external_auth=external_auth))
        user.password = password
        return user

    def __init__(self, user_model):
        self.__user_model = user_model

    # Expose model attributes

    @property
    def username(self):
        """
        Expose model.username read only
        """
        return self.__user_model.username

    def __set_password(self, passwd):
        """
        Expose model.password write only and encrypt if password, else
        set to ''
        """
        self.__model.password = encrypt_password(passwd) if passwd else ''

    password = property(fset=__set_password)

    @property
    def email(self):
        return self.__model.email

    @email.setter
    def email(self, email):
        self.__model.email = email

    @property
    def email_confirmed(self):
        return self.__model.email_confirmed

    @email_confirmed.setter
    def email_confirmed(self, emailc):
        self.__model.email_confirmed = emailc

    # Utility methods

    def __eq__(self, other):
        return all((
            self.__model.__class__ is other.__model.__class__,
            self.__model.username == other.__model.username,
            self.__model.email == other.__model.email,
            self.__model.conf == other.__model.conf,
            self.__model.account_type == other.__model.account_type))

    def __repr__(self):
        return self.username

    def __getitem__(self, *args):
        return self.__model.conf.__getitem__(*args)

    def __setitem__(self, *args):
        self.__model.conf.__setitem__(*args)

    @property
    def basic(self):
        """
        Return a basic Python data structure from which self can be
        reconstructed.
        """
        return {
            'username': self.__model.username,
            'password': self.__model.password,
            'email': self.__model.email,
            'email_confirmed': self.__model.email_confirmed,
            'account_type': self.__model.account_type,
            'external_auth': self.__model.external_auth,
            'temporary_password': self.__model._temporary_password,
            'is_suspended': self.__model.is_suspended,
            'viewable_worksheets': self.__model.viewable_worksheets,
            'conf': self.__model.conf.basic(),
            }

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

    def check_password(self, password):
        # the empty password is always false
        if self.username == "pub" or password == '':
            return False
        if self.__model.external_auth is not None:
            return None

        my_passwd = self.__model.password
        if not my_passwd:
            return False
        if '$' not in my_passwd:
            check = my_passwd == crypt.crypt(password, SALT)
            if check:
                self.password = password
            return check

        salt = my_passwd.split('$')[1]
        return encrypt_password(password, salt) == my_passwd
