from __future__ import absolute_import

import crypt

from .models import User as UserModel
from .models import UserConfiguration
from .config import SALT
from .config import UAT_ADMIN
from .config import UAT_GUEST
from .config import UAT_USER
from .config import UN_ADMIN
from .config import UN_GUEST
from .config import UN_PUB
from .config import UN_SAGE
from .config import UN_SYSTEM
from .util.auth import encrypt_password
from .util.auth import LdapAuth


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
        self.__user_model.password = encrypt_password(passwd) if passwd else ''

    password = property(fset=__set_password)

    @property
    def email(self):
        return self.__user_model.email

    @email.setter
    def email(self, email):
        self.__user_model.email = email

    @property
    def email_confirmed(self):
        return self.__user_model.email_confirmed

    @email_confirmed.setter
    def email_confirmed(self, value):
        self.__user_model.email_confirmed = value

    @property
    def is_suspended(self):
        return self.__user_model.is_suspended

    @is_suspended.setter
    def is_suspended(self, value):
        self.__user_model.is_suspended = value

    @property
    def viewable_worksheets(self):
        return self.__user_model.viewable_worksheets



    # Utility methods

    def __eq__(self, other):
        return all((
            self.__user_model.__class__ is other.__user_model.__class__,
            self.__user_model.username == other.__user_model.username,
            self.__user_model.email == other.__user_model.email,
            self.__user_model.conf == other.__user_model.conf,
            self.__user_model.account_type == other.__user_model.account_type))

    def __repr__(self):
        return self.username

    def __getitem__(self, *args):
        return self.__user_model.conf.__getitem__(*args)

    def __setitem__(self, *args):
        self.__user_model.conf.__setitem__(*args)

    @property
    def basic(self):
        """
        Return a basic Python data structure from which self can be
        reconstructed.
        """
        return {
            'username': self.__user_model.username,
            'password': self.__user_model.password,
            'email': self.__user_model.email,
            'email_confirmed': self.__user_model.email_confirmed,
            'account_type': self.__user_model.account_type,
            'external_auth': self.__user_model.external_auth,
            'temporary_password': self.__user_model._temporary_password,
            'is_suspended': self.__user_model.is_suspended,
            'viewable_worksheets': self.__user_model.viewable_worksheets,
            'conf': self.__user_model.conf.basic(),
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
        if self.__user_model.external_auth is not None:
            return None

        my_passwd = self.__user_model.password
        if not my_passwd:
            return False
        if '$' not in my_passwd:
            check = my_passwd == crypt.crypt(password, SALT)
            if check:
                self.password = password
            return check

        salt = my_passwd.split('$')[1]
        return encrypt_password(password, salt) == my_passwd


class UserManager(dict):
    """
    EXAMPLES:
        sage: from sagenb.notebook.user_manager import UserManager
        sage: U = UserManager()
        sage: U == loads(dumps(U))
        True

    """
    def __init__(self,
                 auth_ldap=False,
                 ldap_uri='ldap://example.net:389/',
                 ldap_basedn='ou=users,dc=example,dc=net',
                 ldap_binddn='cn=manager,dc=example,dc=net',
                 ldap_bindpw='secret',
                 ldap_gssapi=False,
                 ldap_username_attrib='cn',
                 ldap_timeout=5,
                 ):
        dict.__init__(self)  # Use super() with python3

        self._auth_methods = {
            'auth_ldap': LdapAuth(
                auth_ldap=auth_ldap,
                ldap_uri=ldap_uri,
                ldap_basedn=ldap_basedn,
                ldap_binddn=ldap_binddn,
                ldap_bindpw=ldap_bindpw,
                ldap_gssapi=ldap_gssapi,
                ldap_username_attrib=ldap_username_attrib,
                ldap_timeout=ldap_timeout,
                ),
        }

        self._openid = {}

    def __missing__(self, username):
        """
        Check all auth methods that are enabled in the notebook's config.
        If a valid username is found, a new User object will be created.
        """
        for a, method in self._auth_methods.iteritems():
            if method.enabled and method.check_user(username):
                try:
                    email = method.get_attrib(username, 'email')
                except KeyError:
                    email = None

                self.add_user(username, password='', email=email,
                              account_type=UAT_USER, external_auth=a)
                return self[username]

        raise KeyError('no user {!r}'.format(username))

    def __eq__(self, other):
        """
        EXAMPLES:
            sage: from sagenb.notebook.user_manager import UserManager
            sage: U1 = UserManager()
            sage: U2 = UserManager(accounts=False)
            sage: U1 == U2
            False
            sage: U1 == U2
            True
            sage: U1.create_default_users('password')
            sage: U1 == U2
            False
            sage: U2.create_default_users('password')
            sage: U1 == U2
            True
        """
        return all((
            other.__class__ is self.__class__,
            self == other,
            ))

    @property
    def login_allowed_usernames(self):
        """
        Return a list of users that can log in.
        """
        return [x for x in self if x not in UN_SYSTEM]

    def create_default_users(self, passwd):
        """
        Creates the default users (pub, _sage_, guest, and admin) in the
        current notebook.

        EXAMPLES:
            sage: from sagenb.notebook.user_manager import UserManager
            sage: U = UserManager()
            sage: U.create_default_users('password')
            sage: U
            {'sage': _sage_, 'admin': admin, 'guest': guest, 'pub': pub}

        """
        self.add_user(UN_PUB, '', '', account_type=UAT_USER)
        self.add_user(UN_SAGE, '', '', account_type=UAT_USER)
        self.add_user(UN_GUEST, '', '', account_type=UAT_GUEST)
        self.add_user(UN_ADMIN, passwd, '', account_type=UAT_ADMIN)

    def add_user(self, username, password, email, account_type="user",
                 external_auth=None):
        """
        Adds a new user to the user dictionary.

        INPUT:
            username -- the username
            password -- the password
            email -- the email address
            account_type -- one of 'user', 'admin', or 'guest'

        EXAMPLES:
            sage: from sagenb.notebook.user_manager import UserManager
            sage: U = UserManager()
            sage: U.add_user(
            'william', 'password', 'email@address.com', account_type='admin')
            sage: U.add_user(
            'william', 'password', 'email@address.com', account_type='admin')
           WARNING: User 'william' already exists -- and is now being replaced.
            sage: U['william']
            william
        """
        self[username] = User.new(username, password, email, account_type,
                                  external_auth)

    def check_password(self, username, password):
        check = self[username].check_password(password)
        if check is not None:
            return check

        a = self[username].external_auth
        if a is not None and self._auth_methods[a].enabled:
            return self._auth_methods[a].check_password(username, password)
        return False

    #openID

    def load(self, datastore):
        """
        Loads required data from a given datastore.
        """
        self._openid = datastore.load_openid()

    def save(self, datastore):
        """
        Saves persistent data to a given datastore.
        """
        datastore.save_openid(self._openid)

    def get_username_from_openid(self, identity_url):
        """
        Return the username corresponding ot a given identity_url
        EXAMPLES:
            sage: from sagenb.notebook.user_manager import OpenIDUserManager
            sage: UM = OpenIDUserManager()
            sage: UM.create_default_users('passpass')
            sage: UM.create_new_openid(
                'https://www.google.com/accounts/o8/id?'
                'id=AItdaWgzjV1HJTa552549o1csTDdfeH6_bPxF14', 'thedude')
            sage: UM.get_username_from_openid(
                'https://www.google.com/accounts/o8/id?'
                'id=AItdaWgzjV1HJTa552549o1csTDdfeH6_bPxF14')
            'thedude'
        """
        try:
            return self._openid[identity_url]
        except KeyError:
            raise KeyError("no openID identity '{}'".format(identity_url))

    def create_new_openid(self, identity_url, username):
        """
        Create a new identity_url -- username pairing
        EXAMPLES:
            sage: from sagenb.notebook.user_manager import OpenIDUserManager
            sage: UM = OpenIDUserManager()
            sage: UM.create_default_users('passpass')
            sage: UM.create_new_openid('https://www.google.com/accounts/o8/id?'
            'id=AItdaWgzjV1HJTa552549o1csTDdfeH6_bPxF14', 'thedude')
            sage: UM.get_username_from_openid(
                'https://www.google.com/accounts/o8/id?'
                'id=AItdaWgzjV1HJTa552549o1csTDdfeH6_bPxF14')
            'thedude'
        """
        self._openid[identity_url] = username

    def get_user_from_openid(self, identity_url):
        """
        Return the user object corresponding ot a given identity_url
        """
        return self[self.get_username_from_openid(identity_url)]
