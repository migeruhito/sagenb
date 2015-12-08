from __future__ import absolute_import

import re
import string
from flask.ext.babel import gettext

valid_username_re = re.compile(r'[a-zA-Z_][a-zA-Z0-9_.@]*')
valid_email_re = re.compile(r"""
    ^%(unquoted)s+(\.%(unquoted)s+)*    # unquoted local-part
    @                                   # at
    ([a-z0-9]([a-z0-9-]*[a-z0-9])?\.)+  # subdomains can't start or end with -
    [a-z]+$                             # top-level domain is at least 1 char
""" % {'unquoted': r"[a-z0-9!#$%&'*+\-/=?^_`{|}~]"},
    re.IGNORECASE | re.VERBOSE)
extract_title_re = re.compile(
    r'\<title\>(.*?)\<\/title\>', re.IGNORECASE | re.DOTALL)


def is_valid_username(username):
    """
    Returns whether a candidate username is valid.  It must contain
    between 3 and 65 of these characters: letters, numbers,
    underscores, @, and/or dots ('.').

    INPUT:

    - ``username`` - a string; the candidate username

    OUTPUT:

    - a boolean

    EXAMPLES::

        sage: from sagenb.notebook.misc import is_valid_username
        sage: is_valid_username('mark10')
        True
        sage: is_valid_username('10mark')
        False
        sage: is_valid_username('me')
        False
        sage: is_valid_username('abcde' * 13)
        False
        sage: is_valid_username('David Andrews')
        False
        sage: is_valid_username('David M. Andrews')
        False
        sage: is_valid_username('sarah_andrews')
        True
        sage: is_valid_username('TA-1')
        False
        sage: is_valid_username('math125-TA')
        False
        sage: is_valid_username('dandrews@sagemath.org')
        True
    """

    if not (len(username) > 2 and len(username) < 65):
        return False
    if not username[0] in string.letters:
        return False
    m = valid_username_re.match(username)
    return m.start() == 0 and m.end() == len(username)


def is_valid_password(password, username):
    """
    Return True if and only if ``password`` is valid, i.e.,
    is between 4 and 32 characters long, doesn't contain space(s), and
    doesn't contain ``username``.

    EXAMPLES::

        sage: from sagenb.notebook.misc import is_valid_password
        sage: is_valid_password('uip@un7!', None)
        True
        sage: is_valid_password('markusup89', None)
        True
        sage: is_valid_password('8u7', None)
        False
        sage: is_valid_password(
            'fUmDagaz8LmtonAowjSe0Pvu9C5Gvr6eKcC6wsAT', None)
        True
        sage: is_valid_password('rrcF !u78!', None)
        False
        sage: is_valid_password('markusup89', 'markus')
        False
    """
    if len(password) < 4 or ' ' in password:
        return False
    if username:
        if string.lower(username) in string.lower(password):
            return False
    return True


def do_passwords_match(pass1, pass2):
    """
    EXAMPLES::

        sage: from sagenb.notebook.misc import do_passwords_match
        sage: do_passwords_match('momcat', 'mothercat')
        False
        sage: do_passwords_match('mothercat', 'mothercat')
        True
    """
    return pass1 == pass2


def is_valid_email(email):
    """
    Validates an email address.  The implemention here is short, but
    it should cover the more common forms.  In particular, it
    allows "plus addresses," e.g.,

        first.last+label@gmail.com

    But it rejects several other classes, including those with
    comments, quoted local-parts, and/or IP address domains.  For more
    information, please see `RFC 3696`_, `RFC 5322`_, and their
    errata.

    .. _RFC 3696:   http://tools.ietf.org/html/rfc3696#section-3
    .. _RFC 5322: http://tools.ietf.org/html/rfc5322#section-3.4.1

    INPUT:

    - ``email`` - string; the address to validate

    OUTPUT:

    - a boolean; whether the address is valid, according to simplistic
      but widely used criteria

    EXAMPLES::

        sage: from sagenb.notebook.misc import is_valid_email
        sage: is_valid_email('joe@washinton.gov')
        True
        sage: is_valid_email('joe.washington.gov')  # missing @
        False
        sage: is_valid_email('foo+plus@gmail.com')
        True
        sage: is_valid_email('foo++@gmail.com')
        True
        sage: is_valid_email('foo+bar+baz@gmail.com')
        True
        sage: is_valid_email('+plus@something.org')
        True
        sage: is_valid_email('hyphens-are-okay@example.ab.cd')
        True
        sage: is_valid_email('onlytld@com')         # missing subdomain
        False
        sage: is_valid_email(
            "we..are@the.borg")    # consecutive dots not allowed
        False
        sage: is_valid_email("abcd@[12.34.56.78]")  # legal, really
        False
        sage: is_valid_email("x@y.z")               # legal but too short
        False
        sage: is_valid_email('"i c@nt"@do.it')      # legal, really
        False
        sage: is_valid_email(65 * 'a' + '@lim.sup') # username too long
        False
        sage: is_valid_email(32 * '@..@.][.' + '!') # too long, ...
        False
    """
    if 7 < len(email) < 257:
        if valid_email_re.match(email) is None:
            return False
        # TODO: If/when we permit *quoted* local-parts, account for
        # legal additional @'s, e.g., "foo@bar"@bar.foo
        if len(email.split('@')[0]) > 64:
            return False
        return True
    return False


def extract_title(html_page):
    title = extract_title_re.search(html_page)
    if title is None:
        return gettext("Untitled")

    return title.groups()[0]
