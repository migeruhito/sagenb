from __future__ import absolute_import


import copy

from flask.ext.babel import gettext
from flask.ext.babel import lazy_gettext

from .config import CHOICES
from .config import DESC
from .config import GROUP
from .config import POS
from .config import TYPE
from .config import T_BOOL
from .config import T_CHOICE
from .config import T_COLOR
from .config import T_INFO
from .config import T_INTEGER
from .config import T_LIST
from .config import T_REAL
from .config import T_STRING
from .config import G_APPEARANCE
from .config import G_AUTH
from .config import G_LDAP
from .config import G_SERVER
from .config import POS_DEFAULT
from .config import THEMES
from .config import TRANSLATIONS
from .config import UAT_ADMIN
from .config import UAT_GUEST
from .config import UAT_USER
from .util import import_from
from .util import N_

_ = lazy_gettext

app_defaults = {
    'word_wrap_cols': 72,
    'max_history_length': 250,

    'idle_timeout': 0,        # timeout in seconds for worksheets
    'doc_timeout': 600,         # timeout in seconds for live docs
    'idle_check_interval': 360,

    'save_interval': 360,        # seconds

    'doc_pool_size': 128,

    'pub_interact': False,

    'server_pool': [],

    'system': 'sage',

    'pretty_print': False,

    'ulimit': '',

    'notification_recipients': None,

    'email': False,

    'accounts': False,

    'openid': False,

    'challenge': False,
    'challenge_type': 'simple',
    'recaptcha_public_key': '',
    'recaptcha_private_key': '',
    'default_language': 'en_US',
    'theme': 'Default',
    'model_version': 0,

    'auth_ldap': False,
    'ldap_uri': 'ldap://example.net:389/',
    'ldap_basedn': 'ou=users,dc=example,dc=net',
    'ldap_binddn': 'cn=manager,dc=example,dc=net',
    'ldap_bindpw': 'secret',
    'ldap_gssapi': False,
    'ldap_username_attrib': 'cn',
    'ldap_timeout': 5,
    }

app_gui_hints = {
    'max_history_length': {
        DESC: _('Maximum history length'),
        GROUP: G_SERVER,
        TYPE: T_INTEGER,
    },
    'idle_timeout': {
        POS: 1,
        DESC: _('Idle timeout for normal worksheets (seconds)'),
        GROUP: G_SERVER,
        TYPE: T_INTEGER,
    },
    'doc_timeout': {
        POS: 3,
        DESC: _('Idle timeout for live documentation (seconds)'),
        GROUP: G_SERVER,
        TYPE: T_INTEGER,
    },
    'idle_check_interval': {
        DESC: _('Idle check interval (seconds)'),
        GROUP: G_SERVER,
        TYPE: T_INTEGER,
    },
    'save_interval': {
        DESC: _('Save interval (seconds)'),
        GROUP: G_SERVER,
        TYPE: T_INTEGER,
    },
    'doc_pool_size': {
        DESC: _('Doc worksheet pool size'),
        GROUP: G_SERVER,
        TYPE: T_INTEGER,
    },
    'pub_interact': {
        DESC: _(
            'Enable published interacts (EXPERIMENTAL; USE AT YOUR OWN RISK)'),
        GROUP: G_SERVER,
        TYPE: T_BOOL,
    },
    'server_pool': {
        DESC: _('Worksheet process users (comma-separated list)'),
        GROUP: G_SERVER,
        TYPE: T_LIST,
    },
    'system': {
        DESC: _('Default system'),
        GROUP: G_SERVER,
        TYPE: T_STRING,
    },
    'ulimit': {
        DESC: _('Worksheet process limits'),
        GROUP: G_SERVER,
        TYPE: T_STRING,
    },
    'model_version': {
        DESC: _('Model Version'),
        GROUP: G_SERVER,
        TYPE: T_INFO,
    },
    'notification_recipients': {
        DESC: _('Send notification e-mails to (comma-separated list)'),
        GROUP: G_SERVER,
        TYPE: T_LIST,
    },
    'word_wrap_cols': {
        DESC: _('Number of word-wrap columns'),
        GROUP: G_APPEARANCE,
        TYPE: T_INTEGER,
    },
    'pretty_print': {
        DESC: _('Pretty print (typeset) output'),
        GROUP: G_APPEARANCE,
        TYPE: T_BOOL,
    },
    'default_language': {
        DESC: _('Default Language'),
        GROUP: G_APPEARANCE,
        TYPE: T_CHOICE,
        CHOICES: TRANSLATIONS,
    },
    'theme': {
        DESC: _('Theme'),
        GROUP: G_APPEARANCE,
        TYPE: T_CHOICE,
        CHOICES: THEMES,
    },

    'openid': {
        POS: 1,
        DESC: _('Allow OpenID authentication (requires python ssl module)'),
        GROUP: G_AUTH,
        TYPE: T_BOOL,
    },
    'accounts': {
        POS: 2,
        DESC: _('Enable user registration'),
        GROUP: G_AUTH,
        TYPE: T_BOOL,
    },
    'email': {
        POS: 3,
        DESC: _('Require e-mail for account registration'),
        GROUP: G_AUTH,
        TYPE: T_BOOL,
    },
    'challenge': {
        POS: 4,
        DESC: _('Use a challenge for account registration'),
        GROUP: G_AUTH,
        TYPE: T_BOOL,
    },
    'challenge_type': {
        POS: 4,
        DESC: _('Type of challenge'),
        GROUP: G_AUTH,
        TYPE: T_CHOICE,
        CHOICES: [N_('simple'), N_('recaptcha')],
    },
    'recaptcha_public_key': {
        DESC: _('reCAPTCHA public key'),
        GROUP: G_AUTH,
        TYPE: T_STRING,
    },
    'recaptcha_private_key': {
        DESC: _('reCAPTCHA private key'),
        GROUP: G_AUTH,
        TYPE: T_STRING,
    },

    'auth_ldap': {
        POS: 1,
        DESC: _('Enable LDAP Authentication'),
        GROUP: G_LDAP,
        TYPE: T_BOOL,
    },
    'ldap_uri': {
        POS: 2,
        DESC: _('LDAP URI'),
        GROUP: G_LDAP,
        TYPE: T_STRING,
    },
    'ldap_binddn': {
        POS: 3,
        DESC: _('Bind DN'),
        GROUP: G_LDAP,
        TYPE: T_STRING,
    },
    'ldap_bindpw': {
        POS: 4,
        DESC: _('Bind Password'),
        GROUP: G_LDAP,
        TYPE: T_STRING,
    },
    'ldap_gssapi': {
        POS: 5,
        DESC: _('Use GSSAPI instead of Bind DN/Password'),
        GROUP: G_LDAP,
        TYPE: T_BOOL,
    },
    'ldap_basedn': {
        POS: 6,
        DESC: _('Base DN'),
        GROUP: G_LDAP,
        TYPE: T_STRING,
    },
    'ldap_username_attrib': {
        POS: 7,
        DESC: _('Username Attribute (i.e. cn, uid or userPrincipalName)'),
        GROUP: G_LDAP,
        TYPE: T_STRING,
    },
    'ldap_timeout': {
        POS: 8,
        DESC: _('Query timeout (seconds)'),
        GROUP: G_LDAP,
        TYPE: T_INTEGER,
    },
}

user_defaults = {
    'max_history_length': 1000,
    'default_system': 'sage',
    'autosave_interval': 60 * 60,
    'default_pretty_print': False,
    'next_worksheet_id_number': -1,  # not yet initialized
    'language': 'default',
    }

user_gui_hints = {
    'language': {
        DESC: lazy_gettext('Language'),
        GROUP: lazy_gettext('Appearance'),
        TYPE: T_CHOICE,
        CHOICES: ['default'] + TRANSLATIONS,
        },
    }


class Configuration(object):
    @classmethod
    def from_basic(cls, basic):
        c = cls()
        c.confs = copy.copy(basic)
        return c

    def __init__(self):
        self.confs = {}

    def __repr__(self):
        return 'Configuration: %s' % self.confs

    def __eq__(self, other):
        return self.__class__ is other.__class__ and self.confs == other.confs

    def __ne__(self, other):
        return not self.__eq__(other)

    def basic(self):
        return self.confs

    def defaults(self):
        raise NotImplementedError

    def defaults_descriptions(self):
        raise NotImplementedError

    def __getitem__(self, key):
        try:
            return self.confs[key]
        except KeyError:
            if key in self.defaults():
                A = self.defaults()[key]
                self.confs[key] = A
                return A
            else:
                raise KeyError("No key '%s' and no default for this key" % key)

    def __setitem__(self, key, value):
        self.confs[key] = value

    def html_conf_form(self, action):
        D = self.defaults()
        C = self.confs
        K = list(set(C.keys() + D.keys()))
        K.sort()
        options = ''
        for key in K:
            options += ('<tr><td>%s</td><td><input type="text" name="%s" '
                        'value="%s"></td></tr>\n' % (
                            key, key, self[key]))
        s = """
        <form method="post" action="%s" enctype="multipart/form-data">
        <input type="submit" value="Submit">
        <table border=0 cellpadding=5 cellspacing=2>
            %s
        </table>
        </form>
        """ % (action, options)
        return s

    def update_from_form(self, form):
        D = self.defaults()
        DS = self.defaults_descriptions()
        C = self.confs
        keys = list(set(C.keys() + D.keys()))

        updated = {}
        for key in keys:
            try:
                typ = DS[key][TYPE]
            except KeyError:
                # We skip this setting.  Perhaps defaults_descriptions
                # is not in sync with defaults, someone has tampered
                # with the request arguments, etc.
                continue
            val = form.get(key, '')

            if typ == T_BOOL:
                if val:
                    val = True
                else:
                    val = False

            elif typ == T_INTEGER:
                try:
                    val = int(val)
                except ValueError:
                    val = self[key]

            elif typ == T_REAL:
                try:
                    val = float(val)
                except ValueError:
                    val = self[key]

            elif typ == T_LIST:
                val = val.strip()
                if val == '' or val == 'None':
                    val = None
                else:
                    val = val.split(',')

            if typ != T_INFO and self[key] != val:
                self[key] = val
                updated[key] = ('updated', gettext('Updated'))

        return updated

    def html_table(self, updated={}):

        # check if LDAP can be used
        ldap_version = import_from('ldap', '__version__')

        # For now, we assume there's a description for each setting.
        D = self.defaults()
        DS = self.defaults_descriptions()
        C = self.confs
        K = set(C.keys() + D.keys())

        G = {}
        # Make groups
        for key in K:
            try:
                gp = DS[key][GROUP]
                # don't display LDAP settings if the check above failed
                if gp == G_LDAP and ldap_version is None:
                    continue
                DS[key][DESC]
                DS[key][TYPE]
            except KeyError:
                # We skip this setting.  It's obsolete and/or
                # defaults_descriptions is not up to date.  See
                # *_conf.py for details.
                continue
            try:
                G[gp].append(key)
            except KeyError:
                G[gp] = [key]

        s = u''
        color_picker = 0
        special_init = u''
        for group in G:
            s += (u'<div class="section">\n  <h2>%s</h2>\n  <table>\n' %
                  lazy_gettext(group))

            opts = G[group]

            def sortf(x, y):
                wx = DS[x].get(POS, POS_DEFAULT)
                wy = DS[y].get(POS, POS_DEFAULT)
                if wx == wy:
                    return cmp(x, y)
                else:
                    return cmp(wx, wy)
            opts.sort(sortf)
            for o in opts:
                s += (u'    <tr>\n      <td>%s</td>\n      <td>\n' %
                      lazy_gettext(DS[o][DESC]))
                input_type = 'text'
                input_value = self[o]

                extra = ''
                if DS[o][TYPE] == T_BOOL:
                    input_type = 'checkbox'
                    if input_value:
                        extra = 'checked="checked"'

                if DS[o][TYPE] == T_LIST:
                    if input_value is not None:
                        input_value = ','.join(input_value)

                if DS[o][TYPE] == T_CHOICE:
                    s += u'        <select name="%s" id="%s">\n' % (o, o)
                    for c in DS[o][CHOICES]:
                        selected = ''
                        if c == input_value:
                            selected = u' selected="selected"'
                        s += (u'          <option value="%s"%s>%s</option>\n' %
                              (c, selected, lazy_gettext(c)))
                    s += u'        </select>\n'

                elif DS[o][TYPE] == T_INFO:
                    s += u'        <span>%s</span>' % input_value

                else:
                    s += (u'        <input type="%s" name="%s" id="%s" '
                          u'value="%s" %s>\n' % (
                              input_type, o, o, input_value, extra))

                    if DS[o][TYPE] == T_COLOR:
                        s += (u'        <div id="picker_%s"></div>\n' %
                              color_picker)
                        special_init += (
                            u'    $("#picker_%s").farbtastic("#%s");\n' % (
                                color_picker, o))
                        color_picker += 1

                s += (u'      </td>\n      <td class="%s">%s</td>\n'
                      u'    </tr>\n' % updated.get(o, ('', '')))

            s += u'  </table>\n</div>\n'

        s += (u'<script type="text/javascript">\n'
              u'$(document).ready(function() {\n' + special_init +
              '});\n</script>')

        lines = s.split(u'\n')
        lines = map(lambda x: u'  ' + x, lines)

        return u'\n'.join(lines)


class ServerConfiguration(Configuration):
    def defaults(self):
        return app_defaults

    def defaults_descriptions(self):
        return app_gui_hints


class UserConfiguration(Configuration):
    def defaults(self):
        return user_defaults

    def defaults_descriptions(self):
        return user_gui_hints


class User(object):
    account_types = (UAT_ADMIN, UAT_USER, UAT_GUEST)

    @classmethod
    def from_basic(cls, basic):
        conf = basic.pop('conf')
        conf = UserConfiguration.from_basic(conf)
        new = cls(conf=conf, **basic)
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
        # property
        self.password = password
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
            self.__password = password
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
