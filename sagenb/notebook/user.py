# -*- coding: utf-8 -*
from __future__ import absolute_import

import hashlib

from ..config import UAT_ADMIN
from ..config import UAT_GUEST
from ..config import UAT_USER
from ..util import generate_salt

from .conf_models import UserConfiguration_from_basic
from .conf_models import UserConfiguration


def User_from_basic(basic):
    """
    Create a user from a basic data structure.
    """
    user = User(basic['username'])
    user.__dict__.update(dict([('_' + x, y) for x, y in basic.iteritems()]))
    user._conf = UserConfiguration_from_basic(user._conf)
    return user


class User(object):
    account_types = (UAT_ADMIN, UAT_USER, UAT_GUEST)

    def __init__(self,
                 username, password='', temporary_password='',
                 email='', email_confirmed=False,
                 account_type='admin', external_auth=None, is_suspended=False,
                 viewable_worksheets=None,
                 conf=None):
        self.__username = username  # Read only -> property
        self.password = password  # property
        self.email = email
        self.email_confirmed = email_confirmed  # Boolean
        self.account_type = account_type  # property
        self._external_auth_ = external_auth
        self._temporary_password = ''
        self._is_suspended = False
        self._viewable_worksheets = set()
        self._conf = UserConfiguration()

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

    def __eq__(self, other):
        return all((
            self.__class__ is other.__class__,
            self.username == other.username,
            self.email == other.email,
            self.conf() == other.conf(),
            self.account_type == other.account_type))

    def __repr__(self):
        return self.username

    def __getitem__(self, *args):
        return self._conf.__getitem__(*args)

    def __setitem__(self, *args):
        self._conf.__setitem__(*args)

    def basic(self):
        """
        Return a basic Python data structure from which self can be
        reconstructed.
        """
        d = dict([(x[1:], y)
                  for x, y in self.__dict__.iteritems() if x[0] == '_'])
        d['conf'] = self._conf.basic()
        return d

    def conf(self):
        """
        EXAMPLES::

            sage: from sagenb.notebook.user import User
            sage: config = User('bob', 'Aisfa!!', 'bob@sagemath.net',
                                'admin').conf(); config
            Configuration: {}
            sage: config['max_history_length']
            1000
            sage: config['default_system']
            'sage'
            sage: config['autosave_interval']
            3600
            sage: config['default_pretty_print']
            False
        """
        return self._conf

    def is_admin(self):
        """
        EXAMPLES::

            sage: from sagenb.notebook.user import User
            sage: User('A', account_type='admin').is_admin()
            True
            sage: User('B', account_type='user').is_admin()
            False
        """
        return self.account_type == UAT_ADMIN

    def grant_admin(self):
        if not self.is_guest():
            self._account_type = UAT_ADMIN

    def revoke_admin(self):
        if not self.is_guest():
            self.account_type = UAT_USER

    def is_guest(self):
        """
        EXAMPLES::

            sage: from sagenb.notebook.user import User
            sage: User('A', account_type='guest').is_guest()
            True
            sage: User('B', account_type='user').is_guest()
            False
        """
        return self.account_type == UAT_GUEST

    def is_external(self):
        return self.external_auth() is not None

    def external_auth(self):
        return self._external_auth

    def is_suspended(self):
        """
        EXAMPLES::

            sage: from sagenb.notebook.user import User
            sage: user = User('bob', 'Aisfa!!', 'bob@sagemath.net', 'admin')
            sage: user.is_suspended()
            False
        """
        try:
            return self._is_suspended
        except AttributeError:
            return False

    def set_suspension(self):
        """
        EXAMPLES::

            sage: from sagenb.notebook.user import User
            sage: user = User('bob', 'Aisfa!!', 'bob@sagemath.net', 'admin')
            sage: user.is_suspended()
            False
            sage: user.set_suspension()
            sage: user.is_suspended()
            True
            sage: user.set_suspension()
            sage: user.is_suspended()
            False
        """
        try:
            self._is_suspended = False if self._is_suspended else True
        except AttributeError:
            self._is_suspended = True

    def viewable_worksheets(self):
        """
        Returns the (mutable) set of viewable worksheets.

        The elements of the set are of the form ('owner',id),
        identifying worksheets the user is able to view.
        """
        return self._viewable_worksheets
