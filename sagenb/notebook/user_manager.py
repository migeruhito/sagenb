from __future__ import absolute_import

import crypt

from ..config import SALT
from ..config import UAT_ADMIN
from ..config import UAT_GUEST
from ..config import UAT_USER
from ..config import UN_ADMIN
from ..config import UN_GUEST
from ..config import UN_PUB
from ..config import UN_SAGE
from ..config import UN_SYSTEM
from ..util.auth import encrypt_password
from ..util.auth import LdapAuth

from ..models import User


class UserManager(dict):
    super_class = dict  # Use super() with python3

    def __init__(self, accounts=True, conf=None):
        """
        EXAMPLES:
            sage: from sagenb.notebook.user_manager import UserManager
            sage: U = UserManager()
            sage: U == loads(dumps(U))
            True

        """
        dict.__init__(self)
        self._users = {}
        self._passwords = {}
        self._conf = {'accounts': accounts} if conf is None else conf

    def __eq__(self, other):
        """
        EXAMPLES:
            sage: from sagenb.notebook.user_manager import SimpleUserManager
            sage: U1 = SimpleUserManager()
            sage: U2 = SimpleUserManager(accounts=False)
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
            sage: from sagenb.notebook.user_manager import SimpleUserManager
            sage: U = SimpleUserManager()
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
            sage: from sagenb.notebook.user_manager import SimpleUserManager
            sage: U = SimpleUserManager()
            sage: U.add_user(
            'william', 'password', 'email@address.com', account_type='admin')
            sage: U.add_user(
            'william', 'password', 'email@address.com', account_type='admin')
           WARNING: User 'william' already exists -- and is now being replaced.
            sage: U['william']
            william
        """
        self[username] = User(username, password, email, account_type,
                              external_auth)
        self.set_password(username, password)

    def copy_password(self, username, other_username):
        """
        Sets the password of user to be the password of other_user.

        EXAMPLES:
            sage: from sagenb.notebook.user_manager import SimpleUserManager
            sage: UM = SimpleUserManager(accounts=True)
            sage: UM.create_default_users('passpass')
            sage: UM.add_user('william', 'password', 'email@address.com')
            sage: UM.check_password('admin','passpass')
            True
            sage: UM.check_password('william','password')
            True
            sage: UM.copy_password('william', 'admin')
            sage: UM.check_password('william','passpass')
            True

        """
        O = self[other_username]
        passwd = O.password
        self.set_password(username, passwd, encrypt=False)

    def set_password(self, username, new_password, encrypt=True):
        """
        EXAMPLES:
            sage: from sagenb.notebook.user_manager import SimpleUserManager
            sage: U = SimpleUserManager()
            sage: U.create_default_users('passpass')
            sage: U.check_password('admin','passpass')
            True
            sage: U.set_password('admin', 'password')
            sage: U.check_password('admin','password')
            True
            sage: U.set_password(
                'admin', 'test'); U.check_password('admin','test')
            True
            sage: U.set_password(
                'admin', 'test', encrypt=False); U.password('admin')
            'test'
        """
        self[username].password = (
            encrypt_password(new_password) if encrypt else new_password)
        self._passwords[username] = self[username].password

    def password(self, username):
        """
        Return the stored password for username. Might be encrypted.
        EXAMPLES:
            sage: from sagenb.notebook.user_manager import SimpleUserManager
            sage: U = SimpleUserManager()
            sage: U.create_default_users('passpass')
            sage: U.check_password('admin','passpass')
            True
        """
        return self._passwords.get(username, None)

    def check_password(self, username, password):
        # the empty password is always false
        if username == "pub" or password == '':
            return False
        user_password = self.password(username)
        if user_password is None and self[username].external_auth is None:
            print "User %s has None password" % username
            return False
        if user_password.find('$') == -1:
            if user_password == crypt.crypt(password, SALT):
                self.set_password(username, password)
                return True
            else:
                return False
        else:
            salt = user_password.split('$')[1]
            if encrypt_password(password, salt) == user_password:
                return True
        try:
            return self._check_password(username, password)
        except AttributeError:
            return False


class ExtAuthUserManager(UserManager):
    """
    For testing if the user \emph{username} has signed in before, you cant use
    username in self, as with the super class.

    Note that this should not be used to check to see if a username is valid
    since in this UserManager backend we could have many valid usernames, but
    not all of them will have actually logged into the notebook.
    """
    super_class = UserManager  # Use super() with python3

    def __init__(self, accounts=None, conf=None):
        self.super_class.__init__(self, accounts=accounts, conf=conf)

        # keys must match to a T_BOOL option in server_config.py
        # so we can turn this auth method on/off
        self._auth_methods = {
            'auth_ldap': LdapAuth(self._conf),
        }

    def __missing__(self, username):
        print('hello')
        """
        Check all auth methods that are enabled in the notebook's config.
        If a valid username is found, a new User object will be created.
        """
        for a, method in self._auth_methods.iteritems():
            if self._conf[a] and method.check_user(username):
                try:
                    email = method.get_attrib(username, 'email')
                except KeyError:
                    email = None

                self.add_user(username, password='', email=email,
                              account_type=UAT_USER, external_auth=a)
                return self[username]

        raise KeyError('no user {!r}'.format(username))

    def _check_password(self, username, password):
        """
        Find auth method for user 'username' and
        use that auth method to check username/password combination.
        """
        a = self[username].external_auth
        if a is not None and self._conf[a]:
            return self._auth_methods[a].check_password(username, password)
        return False


class OpenIDUserManager(ExtAuthUserManager):

    def __init__(self, accounts=True, conf=None):
        """
        Creates an user_manager that supports OpenID identities
        EXAMPLES:
            sage: from sagenb.notebook.user_manager import OpenIDUserManager
            sage: UM = OpenIDUserManager()
            sage: UM.create_default_users('passpass')
            sage: UM.check_password('admin','passpass')
            True
        """
        ExtAuthUserManager.__init__(self, accounts=accounts, conf=conf)
        self._openid = {}

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
