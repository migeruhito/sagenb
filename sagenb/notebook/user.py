# -*- coding: utf-8 -*
from __future__ import absolute_import

import hashlib

from ..config import UAT_ADMIN
from ..config import UAT_GUEST
from ..config import UAT_USER
from ..util import generate_salt

from .conf_models import UserConfiguration


class User(object):
    account_types = (UAT_ADMIN, UAT_USER, UAT_GUEST)

    @classmethod
    def from_basic(cls, basic):
        password = basic.pop('password')
        conf = basic.pop('conf')
        conf = UserConfiguration.from_basic(conf)
        new = cls(conf=conf, **basic)
        new.set_hashed_password(password)
        return new

    def __init__(self,
                 username, password='', email='',
                 account_type='admin', external_auth=None,

                 email_confirmed=False,
                 is_suspended=False,
                 viewable_worksheets=None,
                 conf=None,
                 temporary_password='',  # TODO: Remove. Useless.
                 # TODO: There are a spurious User__username field in the
                 # cpickled users this **kwargs get rid of this and other
                 # spurious fields. This must be removed when the pickled
                 # users integrity be checked by a more apropriate way.
                 **kwargs
                 ):
        self.__username = username  # Read only -> property
        self.password = password  # property
        self.email = email
        self.email_confirmed = email_confirmed  # Boolean
        self.account_type = account_type  # property
        self.__external_auth = external_auth  # Read only -> property
        self._temporary_password = temporary_password
        self.is_suspended = is_suspended
        self.viewable_worksheets = (
            set() if viewable_worksheets is None else viewable_worksheets)
        self.conf = UserConfiguration() if conf is None else conf

    @property
    def username(self):
        """
        EXAMPLES::

            sage: from sagenb.notebook.user import User
            sage: User('andrew', 'tEir&tiwk!', 'andrew@matrixstuff.com',
                       'user').username
            'andrew'
            sage: User('sarah', 'Miaasc!', 'sarah@ellipticcurves.org',
                       'user').username
            'sarah'
            sage: User('bob', 'Aisfa!!', 'bob@sagemath.net',
                       'admin').username
            'bob'
        """
        return self.__username

    @property
    def password(self):
        """
        Deprecated. Use user_manager object instead.
        EXAMPLES::

            sage: from sagenb.notebook.user import User
            sage: User('andrew', 'tEir&tiwk!', 'andrew@matrixstuff.com',
                       'user').password #random
        """
        return self.__password

    @password.setter
    def password(self, password):
        """
        EXAMPLES::

            sage: from sagenb.notebook.user import User
            sage: user = User('bob', 'Aisfa!!', 'bob@sagemath.net', 'admin')
            sage: old = user.password
            sage: user.password = 'Crrc!'
            sage: old != user.password
            True
        """
        if password == '':
            # won't get as a password -- i.e., this account is closed.
            self.__password = 'x'
        else:
            salt = generate_salt()
            self.__password = 'sha256${0}${1}'.format(
                salt, hashlib.sha256(salt + password).hexdigest())
            self._temporary_password = ''

    @property
    def account_type(self):
        """
        EXAMPLES::

            sage: from sagenb.notebook.user import User
            sage: User('A', account_type='admin').account_type
            'admin'
            sage: User('B', account_type='user').account_type
            'user'
            sage: User('C', account_type='guest').account_type
            'guest'
        """
        return self.__account_type

    @account_type.setter
    def account_type(self, account_type):
        if self.username == 'admin':
            account_type = UAT_ADMIN
        elif account_type not in self.account_types:
            raise ValueError(
                'account type must be one{}}, {}, or {}'.format(
                    *self.account_types))
        self.__account_type = account_type

    def basic(self):
        """
        Return a basic Python data structure from which self can be
        reconstructed.
        """
        return {
            'username': self.username,
            'password': self.password,
            'email': self.email,
            'email_confirmed': self.email_confirmed,
            'account_type': self.account_type,
            'external_auth': self.external_auth,
            'temporary_password': self._temporary_password,
            'is_suspended': self.is_suspended,
            'viewable_worksheets': self.viewable_worksheets,
            'conf': self.conf.basic(),
            }

    @property
    def external_auth(self):
        return self.__external_auth

    def __eq__(self, other):
        return all((
            self.__class__ is other.__class__,
            self.username == other.username,
            self.email == other.email,
            self.conf == other.conf,
            self.account_type == other.account_type))

    def __repr__(self):
        return self.username

    def __getitem__(self, *args):
        return self.conf.__getitem__(*args)

    def __setitem__(self, *args):
        self.conf.__setitem__(*args)

    def set_hashed_password(self, password):
        """
        EXAMPLES::

            sage: from sagenb.notebook.user import User
            sage: user = User('bob', 'Aisfa!!', 'bob@sagemath.net', 'admin')
            sage: user.set_hashed_password('Crrc!')
            sage: user.password
            'Crrc!'
        """
        self._password = password
        self._temporary_password = ''

    # Auxiliary methods and properties for account_type flags encapsulation

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
        return self.account_type == UAT_ADMIN

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
        return self.account_type == UAT_GUEST

    def grant_admin(self):
        if not self.is_guest:
            self._account_type = UAT_ADMIN

    def revoke_admin(self):
        if not self.is_guest:
            self.account_type = UAT_USER
