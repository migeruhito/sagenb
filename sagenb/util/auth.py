from __future__ import absolute_import

import hashlib
import os
import random
import re
import urllib
import urllib2

from flask.ext.babel import gettext
from flask.ext.babel import lazy_gettext

from . import get_module
from .templates import render_template

_ = lazy_gettext


def generate_salt():
    """
    Returns a salt for use in hashing.
    """
    return hex(random.getrandbits(256))[2:-1]


def encrypt_password(password, salt=None):
    if salt is None:
        salt = generate_salt()
    return 'sha256${}${}'.format(
        salt, hashlib.sha256(salt + password).hexdigest())


class AuthMethod():
    """
    Abstract class for authmethods that are used by ExtAuthUserManager
    All auth methods must implement the following methods
    """

    def __init__(self, conf):
        self._conf = conf

    def check_user(self, username):
        raise NotImplementedError

    def check_password(self, username, password):
        raise NotImplementedError

    def get_attrib(self, username, attrib):
        raise NotImplementedError


class LdapAuth(AuthMethod):
    """
    Authentication via LDAP

    User authentication basically works like this:
    1.1) bind to LDAP with either
            - generic configured DN and password (simple bind)
            - GSSAPI (e.g. Kerberos)
    1.2) find the ldap object matching username.

    2) if 1 succeeds, try simple bind with the supplied user DN and password
    """

    def _require_ldap(default_return):
        """
        function decorator to
            - disable LDAP auth
            - return a "default" value (decorator argument)
        if importing ldap fails
        """
        def wrap(f):
            def wrapped_f(self, *args, **kwargs):
                if get_module('ldap') is None:
                    print "cannot 'import ldap', disabling LDAP auth"
                    self._conf['auth_ldap'] = False
                    return default_return
                else:
                    return f(self, *args, **kwargs)
            return wrapped_f
        return wrap

    def __init__(self, conf):
        AuthMethod.__init__(self, conf)

    def _ldap_search(self, query, attrlist=None, sizelimit=20):
        """
        runs any ldap query passed as arg
        """
        import ldap
        from ldap.sasl import gssapi
        conn = ldap.initialize(self._conf['ldap_uri'])

        try:
            if self._conf['ldap_gssapi']:
                token = gssapi()
                conn.sasl_interactive_bind_s('', token)
            else:
                conn.simple_bind_s(
                    self._conf['ldap_binddn'], self._conf['ldap_bindpw'])

            result = conn.search_ext_s(
                self._conf['ldap_basedn'],
                ldap.SCOPE_SUBTREE,
                filterstr=query,
                attrlist=attrlist,
                timeout=self._conf['ldap_timeout'],
                sizelimit=sizelimit)
        except ldap.LDAPError, e:
            print 'LDAP Error: %s' % str(e)
            return []
        finally:
            conn.unbind_s()

        return result

    def _get_ldapuser(self, username, attrlist=None):
        """
        Returns a tuple containing the DN and a dict of attributes of the given
        username, or (None, None) if the username is not found
        """
        from ldap.filter import filter_format

        query = filter_format(
            '(%s=%s)', (self._conf['ldap_username_attrib'], username))

        result = self._ldap_search(query, attrlist)

        # only allow one unique result
        # (len(result) will probably always be 0 or 1)
        return result[0] if len(result) == 1 else (None, None)

    @_require_ldap(False)
    def check_user(self, username):
        # LDAP is NOT case sensitive while sage is, so only allow lowercase
        if not username.islower():
            return False
        dn, attribs = self._get_ldapuser(username)
        return dn is not None

    @_require_ldap(False)
    def check_password(self, username, password):
        import ldap

        dn, attribs = self._get_ldapuser(username)
        if not dn:
            return False

        # try to bind with found DN
        conn = ldap.initialize(uri=self._conf['ldap_uri'])
        try:
            conn.simple_bind_s(dn, password)
            return True
        except ldap.INVALID_CREDENTIALS:
            return False
        except ldap.LDAPError, e:
            print 'LDAP Error: %s' % str(e)
            return False
        finally:
            conn.unbind_s()

    @_require_ldap('')
    def get_attrib(self, username, attrib):
        # 'translate' attribute names used in ExtAuthUserManager
        # to their ldap equivalents

        # "email" is "mail"
        if attrib == 'email':
            attrib = 'mail'

        dn, attribs = self._get_ldapuser(username, [attrib])
        if not attribs:
            return ''

        # return the first item or '' if the attribute is missing
        return attribs.get(attrib, [''])[0]


# Registration

def register_build_msg(key, username, addr, port, secure):
    url_prefix = "https" if secure else "http"
    s = gettext("Hi %(username)s!\n\n", username=username)
    s += gettext(
        'Thank you for registering for the Sage notebook. '
        'To complete your registration, copy and paste'
        ' the following link into your browser:\n\n'
        '%(url_prefix)s://%(addr)s:%(port)s/confirm?key=%(key)s\n\n'
        'You will be taken to a page which will confirm that you have '
        'indeed registered.',
        url_prefix=url_prefix, addr=addr, port=port, key=key)
    return s.encode('utf-8')


def register_build_password_msg(key, username, addr, port, secure):
    url_prefix = "https" if secure else "http"
    s = gettext("Hi %(username)s!\n\n", username=username)
    s += gettext(
        'Your new password is %(key)s\n\n'
        'Sign in at %(url_prefix)s://%(addr)s:%(port)s/\n\n'
        'Make sure to reset your password by going to Settings in the '
        'upper right bar.',
        key=key, url_prefix=url_prefix, addr=addr, port=port)
    return s.encode('utf-8')


def register_make_key():
    key = random.randint(0, 2**128 - 1)
    return key


# Challenge

class ChallengeResponse(object):
    """
    A simple challenge response class that indicates whether a
    response is empty, correct, or incorrect, and, if it's incorrect,
    includes an optional error code.
    """

    def __init__(self, is_valid, error_code=None):
        """
        Instantiates a challenge response.

        INPUT:

        - ``is_valid`` - a boolean or None; whether there response is
          valid

        - ``error_code`` - a string (default: None); an optional error
          code if ``is_valid`` is False

        TESTS::

            sage: from sagenb.notebook.challenge import ChallengeResponse
            sage: resp = ChallengeResponse(False, 'Wrong! Please try again.')
            sage: resp.is_valid
            False
            sage: resp.error_code
            'Wrong! Please try again.'

        """
        self.is_valid = is_valid
        self.error_code = error_code


class AbstractChallenge(object):
    """
    An abstract class with a suggested common interface for specific
    challenge-response schemes.
    """

    def __init__(self, conf, **kwargs):
        """
        Instantiates an abstract challenge.

        INPUT:

        - ``conf`` - a :class:`ServerConfiguration`; a notebook server
          configuration instance

        - ``kwargs`` - a dictionary of keyword arguments

        TESTS::

            sage: from sagenb.notebook.challenge import AbstractChallenge
            sage: tmp = tmp_dir(ext='.sagenb')
            sage: import sagenb.notebook.notebook as n
            sage: nb = n.Notebook(tmp)
            sage: chal = AbstractChallenge(nb.conf())

        """
        pass

    def html(self, **kwargs):
        """
        Returns HTML for the challenge, e.g., to insert into a new
        account registration page.

        INPUT:

        - ``kwargs`` - a dictionary of keywords arguments

        OUTPUT:

        - a string; HTML form representation of the challenge,
          including a field for the response, supporting hidden
          fields, JavaScript code, etc.

        TESTS::

            sage: from sagenb.notebook.challenge import AbstractChallenge
            sage: tmp = tmp_dir(ext='.sagenb')
            sage: import sagenb.notebook.notebook as n
            sage: nb = n.Notebook(tmp)
            sage: chal = AbstractChallenge(nb.conf())
            sage: chal.html()
            Traceback (most recent call last):
            ...
            NotImplementedError
        """
        raise NotImplementedError

    def is_valid_response(self, **kwargs):
        """
        Returns the status of a challenge response.

        INPUT:

        - ``kwargs`` - a dictionary of keyword arguments

        OUTPUT:

        - a :class:`ChallengeResponse` instance

        TESTS::

            sage: from sagenb.notebook.challenge import AbstractChallenge
            sage: tmp = tmp_dir(ext='.sagenb')
            sage: import sagenb.notebook.notebook as n
            sage: nb = n.Notebook(tmp)
            sage: chal = AbstractChallenge(nb.conf())
            sage: chal.is_valid_response()
            Traceback (most recent call last):
            ...
            NotImplementedError
        """
        raise NotImplementedError


class NotConfiguredChallenge(AbstractChallenge):
    """
    A fallback challenge used when an administrator has not configured
    a specific method.
    """

    def html(self, **kwargs):
        """
        Returns a suggestion to inform the Notebook server's
        administrator about the misconfigured challenge.

        INPUT:

        - ``conf`` - a :class:`ServerConfiguration`; an instance of the
          server's configuration

        - ``kwargs`` - a dictionary of keyword arguments

        OUTPUT:

        - a string

        TESTS::

            sage: from sagenb.notebook.challenge import NotConfiguredChallenge
            sage: tmp = tmp_dir(ext='.sagenb')
            sage: import sagenb.notebook.notebook as n
            sage: nb = n.Notebook(tmp)
            sage: chal = NotConfiguredChallenge(nb.conf())
            sage: print chal.html()
            Please ask the server administrator to configure a challenge!

        """
        return _(
            "Please ask the server administrator to configure a challenge!")

    def is_valid_response(self, **kwargs):
        """
        Always reports a failed response, for the sake of security.

        INPUT:

        - ``kwargs`` - a dictionary of keyword arguments

        OUTPUT:

        - a :class:`ChallengeResponse` instance

       TESTS::

            sage: from sagenb.notebook.challenge import NotConfiguredChallenge
            sage: tmp = tmp_dir(ext='.sagenb')
            sage: import sagenb.notebook.notebook as n
            sage: nb = n.Notebook(tmp)
            sage: chal = NotConfiguredChallenge(nb.conf())
            sage: chal.is_valid_response().is_valid
            False
            sage: chal.is_valid_response().error_code
            ''

        """
        return ChallengeResponse(False, '')


# HTML template for :class:`SimpleChallenge`.
SIMPLE_TEMPLATE = (
    u'<p>%(question)s</p>\n'
    u'<input type="text" id="simple_response_field" '
    u'name="simple_response_field" class="entry" tabindex="5" />\n'
    u'<input type="hidden" value="%(untranslated_question)s" '
    u'id="simple_challenge_field" name="simple_challenge_field" '
    u'class="entry" />')

old_tr = _


def _(s):
    return s

# A set of sample questions for :class:`SimpleChallenge`.
QUESTIONS = {
    _('Is pi > e?'): _('y|yes'),
    _('What is 3 times 8?'): _('24|twenty-four'),
    _('What is 2 plus 3?'): _('5|five'),
    _('How many bits are in one byte?'): _('8|eight'),
    _('What is the largest prime factor of 15?'): _('5|five'),
    #    'What is the smallest perfect number?' : r'6|six',
    #    'What is our class registration code?' : r'XYZ123',
    #    ('What is the smallest integer expressible as the sum of two '
    #     'positive cubes in two distinct ways?' : r'1729'),
    #    ('How many permutations of ABCD agree with it in no position? '
    #     'For example, BDCA matches ABCD only in position 3.' : r'9|nine'),
}

# QUESTIONS is now dict of str->str
# let's make answers lazy translated:
for key in QUESTIONS:
    QUESTIONS[key] = old_tr(QUESTIONS[key])

_ = old_tr
del old_tr


def agree(response, answer):
    """
    Returns whether a challenge response agrees with the answer.

    INPUT:

    - ``response`` - a string; the user's response to a posed challenge

    - ``answer`` - a string; the challenge's right answer as a regular
      expression

    OUTPUT:

    - a boolean; whether the response agrees with the answer

    TESTS::

        sage: from sagenb.notebook.challenge import agree
        sage: agree('0', r'0|zero')
        True
        sage: agree('eighty', r'8|eight')
        False

    """
    response = re.sub(r'\s+', ' ', response.strip())
    m = re.search(r'^(' + answer + r')$', response, re.IGNORECASE)
    if m:
        return True
    else:
        return False


class SimpleChallenge(AbstractChallenge):
    """
    A simple question and answer challenge.
    """

    def html(self, **kwargs):
        """
        Returns a HTML form posing a randomly chosen question.

        INPUT:

        - ``kwargs`` - a dictionary of keyword arguments

        OUTPUT:

        - a string; the HTML form

        TESTS::

            sage: from sagenb.notebook.challenge import SimpleChallenge
            sage: tmp = tmp_dir(ext='.sagenb')
            sage: import sagenb.notebook.notebook as n
            sage: nb = n.Notebook(tmp)
            sage: chal = SimpleChallenge(nb.conf())
            sage: chal.html() # random
            '...What is the largest prime factor of 1001?...'

        """
        question = random.choice([q for q in QUESTIONS])
        return SIMPLE_TEMPLATE % {'question': gettext(question),
                                  'untranslated_question': question}

    def is_valid_response(self, req_args={}, **kwargs):
        """
        Returns the status of a user's answer to the challenge
        question.

        INPUT:

        - ``req_args`` - a string:list dictionary; the arguments of
          the remote client's HTTP POST request

        - ``kwargs`` - a dictionary of extra keyword arguments

        OUTPUT:

        - a :class:`ChallengeResponse` instance

        TESTS::

            sage: from sagenb.notebook.challenge import SimpleChallenge
            sage: tmp = tmp_dir(ext='.sagenb')
            sage: import sagenb.notebook.notebook as n
            sage: nb = n.Notebook(tmp)
            sage: chal = SimpleChallenge(nb.conf())
            sage: req = {}
            sage: chal.is_valid_response(req).is_valid
            sage: chal.is_valid_response(req).error_code
            ''
            sage: from sagenb.notebook.challenge import QUESTIONS
            sage: ques, ans = sorted(QUESTIONS.items())[0]
            sage: ans = ans.split('|')[0]
            sage: print ques
            How many bits are in one byte?
            sage: print ans
            8
            sage: req['simple_response_field'] = ans
            sage: chal.is_valid_response(req).is_valid
            False
            sage: chal.is_valid_response(req).error_code
            ''
            sage: req['simple_challenge_field'] = ques
            sage: chal.is_valid_response(req).is_valid
            True
            sage: chal.is_valid_response(req).error_code
            ''

        """
        response_field = req_args.get('simple_response_field', None)
        if not (response_field and len(response_field)):
            return ChallengeResponse(None, '')

        challenge_field = req_args.get('simple_challenge_field', None)
        if not (challenge_field and len(challenge_field)):
            return ChallengeResponse(False, '')
        if agree(response_field, gettext(QUESTIONS[challenge_field])):
            return ChallengeResponse(True, '')
        else:
            return ChallengeResponse(False, '')


RECAPTCHA_SERVER = "http://api.recaptcha.net"
RECAPTCHA_SSL_SERVER = "https://api-secure.recaptcha.net"
RECAPTCHA_VERIFY_SERVER = "api-verify.recaptcha.net"


class reCAPTCHAChallenge(AbstractChallenge):
    """
    A reCAPTCHA_ challenge adapted from `this Python API`_, also
    hosted here_, written by Ben Maurer and maintained by Josh
    Bronson.

    .. _reCAPTCHA: http://recaptcha.net/
    .. _this Python API: http://pypi.python.org/pypi/recaptcha-client
    .. _here: http://code.google.com/p/recaptcha
    """

    def __init__(self, conf, remote_ip='', is_secure=False, lang='en',
                 **kwargs):
        """
        Instantiates a reCAPTCHA challenge.

        INPUT:

        - ``conf`` - a :class:`ServerConfiguration`; an instance of the
          notebook server's configuration

        - ``remote_ip`` - a string (default: ''); the user's IP
          address, **required** by reCAPTCHA

        - ``is_secure`` - a boolean (default: False); whether the
          user's connection is secure, e.g., over SSL

        - ``lang`` - a string (default 'en'); the language used for
          the reCAPTCHA interface.  As of October 2009, the
          pre-defined choices are 'en', 'nl', 'fr', 'de', 'pt', 'ru',
          'es', and 'tr'

        - ``kwargs`` - a dictionary of extra keyword arguments

        ATTRIBUTES:

        - ``public_key`` - a string; a **site-specific** public
          key obtained at the `reCAPTCHA site`_.

        - ``private_key`` - a string; a **site-specific** private
          key obtained at the `reCAPTCHA site`_.

        .. _reCAPTCHA site: http://recaptcha.net/whyrecaptcha.html

        Currently, the keys are read from ``conf``'s
        ``recaptcha_public_key`` and ``recaptcha_private_key``
        settings.

        TESTS::

            sage: from sagenb.notebook.challenge import reCAPTCHAChallenge
            sage: tmp = tmp_dir(ext='.sagenb')
            sage: import sagenb.notebook.notebook as n
            sage: nb = n.Notebook(tmp)
            sage: chal = reCAPTCHAChallenge(nb.conf(), remote_ip = 'localhost')

        """
        self.remote_ip = remote_ip
        if is_secure:
            self.api_server = RECAPTCHA_SSL_SERVER
        else:
            self.api_server = RECAPTCHA_SERVER

        self.lang = lang
        self.public_key = conf['recaptcha_public_key']
        self.private_key = conf['recaptcha_private_key']

    def html(self, error_code=None, **kwargs):
        """
        Returns HTML and JavaScript for a reCAPTCHA challenge and
        response field.

        INPUT:

        - ``error_code`` - a string (default: None); an optional error
          code to embed in the HTML, giving feedback about the user's
          *previous* response

        - ``kwargs`` - a dictionary of extra keyword arguments

        OUTPUT:

        - a string; HTML and JavaScript to render the reCAPTCHA
          challenge

        TESTS::

            sage: from sagenb.notebook.challenge import reCAPTCHAChallenge
            sage: tmp = tmp_dir(ext='.sagenb')
            sage: import sagenb.notebook.notebook as n
            sage: nb = n.Notebook(tmp)
            sage: chal = reCAPTCHAChallenge(nb.conf(), remote_ip = 'localhost')
            sage: chal.html()
            u'...recaptcha...'
            sage: chal.html('incorrect-captcha-sol')
            u'...incorrect-captcha-sol...'

        """
        error_param = ''
        if error_code:
            error_param = '&error=%s' % error_code

        template_dict = {'api_server': self.api_server,
                         'public_key': self.public_key,
                         'error_param': error_param,
                         'lang': self.lang}

        return render_template(os.path.join('html', 'recaptcha.html'),
                               **template_dict)

    def is_valid_response(self, req_args={}, **kwargs):
        """
        Submits a reCAPTCHA request for verification and returns its
        status.

        INPUT:

        - ``req_args`` - a dictionary; the arguments of the responding
          user's HTTP POST request

        - ``kwargs`` - a dictionary of extra keyword arguments

        OUTPUT:

        - a :class:`ChallengeResponse` instance; whether the user's
          response is empty, accepted, or rejected, with an optional
          error string

        TESTS::

            sage: from sagenb.notebook.challenge import reCAPTCHAChallenge
            sage: tmp = tmp_dir(ext='.sagenb')
            sage: import sagenb.notebook.notebook as n
            sage: nb = n.Notebook(tmp)
            sage: chal = reCAPTCHAChallenge(nb.conf(), remote_ip = 'localhost')
            sage: req = {}
            sage: chal.is_valid_response(req).is_valid
            sage: chal.is_valid_response(req).error_code
            ''
            sage: req['recaptcha_response_field'] = ['subplotTimes']
            sage: chal.is_valid_response(req).is_valid
            False
            sage: chal.is_valid_response(req).error_code
            'incorrect-captcha-sol'
            sage: req['simple_challenge_field'] = ['VBORw0KGgoANSUhEUgAAAB']
            sage: chal.is_valid_response(req).is_valid # random
            False
            sage: chal.is_valid_response(req).error_code # random
            'incorrect-captcha-sol'

        """
        response_field = req_args.get('recaptcha_response_field', [None])[0]
        if not (response_field and len(response_field)):
            return ChallengeResponse(None, '')

        challenge_field = req_args.get('recaptcha_challenge_field', [None])[0]
        if not (challenge_field and len(challenge_field)):
            return ChallengeResponse(False, 'incorrect-captcha-sol')

        def encode_if_necessary(s):
            if isinstance(s, unicode):
                return s.encode('utf-8')
            return s

        params = urllib.urlencode({
            'privatekey': encode_if_necessary(self.private_key),
            'remoteip':  encode_if_necessary(self.remote_ip),
            'challenge':  encode_if_necessary(challenge_field),
            'response':  encode_if_necessary(response_field)
        })

        request = urllib2.Request(
            url="http://%s/verify" % RECAPTCHA_VERIFY_SERVER,
            data=params,
            headers={
                "Content-type": "application/x-www-form-urlencoded",
                "User-agent": "reCAPTCHA Python"
            }
        )

        httpresp = urllib2.urlopen(request)
        return_values = httpresp.read().splitlines()
        httpresp.close()
        return_code = return_values[0]

        if (return_code == "true"):
            return ChallengeResponse(True)
        else:
            return ChallengeResponse(False, return_values[1])


class ChallengeDispatcher(object):
    """
    A simple dispatcher class that provides access to a specific
    challenge.
    """

    def __init__(self, conf, **kwargs):
        """
        Uses the server's configuration to select and set up a
        challenge.

        INPUT:

        - ``conf`` - a :class:`ServerConfiguration`; a server
          configuration instance

        - ``kwargs`` - a dictionary of keyword arguments

        ATTRIBUTES:

        - ``type`` - a string; the type of challenge to set up

        Currently, ``type`` is read from ``conf``'s ``challenge_type``
        setting.

        TESTS::

            sage: from sagenb.notebook.challenge import ChallengeDispatcher
            sage: tmp = tmp_dir(ext='.sagenb')
            sage: import sagenb.notebook.notebook as n
            sage: nb = n.Notebook(tmp)
            sage: disp = ChallengeDispatcher(nb.conf())
            sage: disp.type # random
            'recaptcha'

        """
        self.type = conf['challenge_type']

        if self.type == 'recaptcha':
            # Very simple test for public and private reCAPTCHA keys.
            if conf['recaptcha_public_key'] and conf['recaptcha_private_key']:
                self.challenge = reCAPTCHAChallenge(conf, **kwargs)
            else:
                self.challenge = NotConfiguredChallenge(conf, **kwargs)

        elif self.type == 'simple':
            self.challenge = SimpleChallenge(conf, **kwargs)

        else:
            self.challenge = NotConfiguredChallenge(conf, **kwargs)

    def __call__(self):
        """
        Returns a previously set up challenge.

        OUTPUT:

        - an instantiated subclass of :class:`AbstractChallenge`.

        TESTS::

            sage: from sagenb.notebook.challenge import ChallengeDispatcher
            sage: tmp = tmp_dir(ext='.sagenb')
            sage: import sagenb.notebook.notebook as n
            sage: nb = n.Notebook(tmp)
            sage: nb.conf()['challenge_type'] = 'simple'
            sage: disp = ChallengeDispatcher(nb.conf())
            sage: disp().html() # random
            '<p>...'
            sage: nb.conf()['challenge_type'] = 'mistake'
            sage: disp = ChallengeDispatcher(nb.conf())
            sage: print disp().html()
            Please ask the server administrator to configure a challenge!

        """
        return self.challenge


def challenge(conf, **kwargs):
    """
    Wraps an instance of :class:`ChallengeDispatcher` and returns an
    instance of a specific challenge.

    INPUT:

    - ``conf`` - a :class:`ServerConfiguration`; a server configuration
      instance

    - ``kwargs`` - a dictionary of keyword arguments

    OUTPUT:

    - an instantiated subclass of :class:`AbstractChallenge`

    TESTS::

        sage: from sagenb.notebook.challenge import challenge
        sage: tmp = tmp_dir(ext='.sagenb')
        sage: import sagenb.notebook.notebook as n
        sage: nb = n.Notebook(tmp)
        sage: nb.conf()['challenge_type'] = 'simple'
        sage: chal = challenge(nb.conf())
        sage: chal.html() # random
        '<p>...'

    """
    return ChallengeDispatcher(conf, **kwargs)()
