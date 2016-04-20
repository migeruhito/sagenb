from __future__ import absolute_import

import re
import string
from flask.ext.babel import gettext

from ..config import TRACEBACK

valid_username_chars = r'a-zA-Z0-9_.@'
valid_username_re = re.compile(r'^[{}]{{3,64}}$'.format(
    valid_username_chars))
invalid_username_re = re.compile('[^{}]'.format(valid_username_chars))
valid_email_re = re.compile(r"""
    ^%(unquoted)s+(\.%(unquoted)s+)*    # unquoted local-part
    @                                   # at
    ([a-z0-9]([a-z0-9-]*[a-z0-9])?\.)+  # subdomains can't start or end with -
    [a-z]+$                             # top-level domain is at least 1 char
""" % {'unquoted': r"[a-z0-9!#$%&'*+\-/=?^_`{|}~]"},
    re.IGNORECASE | re.VERBOSE)
extract_title_re = re.compile(
    r'\<title\>(.*?)\<\/title\>', re.IGNORECASE | re.DOTALL)
whitespace_re = re.compile('\s')
non_whitespace_re = re.compile('\S')
extract_cells_re0 = re.compile(  # No \n needed after open delimiter. Only comp
    r'(?:\n+|^)\{\{\{'
    r'(?:(?:([^\n]*)\|)?\n+)?'
    r'(.*?)'
    r'(?:\n+///\n+(.*?))?\n*'
    r'(?<=\n)\}\}\}(?=\n|$)',
    flags=re.DOTALL)
extract_cells_re = re.compile(  # \n needed after open delimiter
    r'\s*(.*?)\s*'
    r'(?:(?<=\n)|^)\{\{\{'
    r'(?:([^\n]*)\|)?\n+'
    r'(.*?)\n*'
    r'(?:(?<=\n)///\n+(.*?))?\n*'
    r'(?<=\n)\}\}\}(?:\n+|$)',
    flags=re.DOTALL)
split_last_text_re = re.compile(r'(.*\n+}}})(?:\n+|$)\s*(.*)\s*',
                                flags=re.DOTALL)
meta_re = re.compile(r'\s*(.*?)\s*=\s*(.*?)\s*(?:,|$)')
search_keywords_re = re.compile(
    r'(?: +|^)'
    r'(?:(?P<sep>["\'])(.*?)(?P=sep)|(\S+))'
    r'(?:(?= )|$)')


def trunc_invalid_username_chars(name):
    return invalid_username_re.sub('_', name)


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
    return valid_username_re.match(username) is not None


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


def format_exception(s0, ncols):
    r"""
    Formats exceptions so they do not appear expanded by default.

    INPUT:

    - ``s0`` - a string

    - ``ncols`` - an integer; number of word wrap columns

    OUTPUT:

    - a string

    If ``s0`` contains "notracebacks," this function simply returns
    ``s0``.

    EXAMPLES::

        sage: sagenb.notebook.cell.format_exception(
            sagenb.notebook.cell.TRACEBACK,80)
        '\nTraceback (click to the left of this block for traceback)\n...\n
        Traceback (most recent call last):'
        sage: sagenb.notebook.cell.format_exception(
            sagenb.notebook.cell.TRACEBACK + "notracebacks",80)
        'Traceback (most recent call last):notracebacks'
    """
    s = s0.lstrip()
    # Add a notracebacks option -- if it is in the string then
    # tracebacks aren't shrunk.  This is currently used by the
    # functions sagenb.misc.support.help and sage.server.support.help.
    if TRACEBACK not in s or 'notracebacks' in s:
        return s0
    if ncols > 0:
        s = s.strip()
        w = s.splitlines()
        for k in range(len(w)):
            if TRACEBACK in w[k]:
                break
        s = ('\n'.join(w[:k]) +
             '\nTraceback (click to the left of this block for traceback)' +
             '\n...\n' + w[-1])
    else:
        s = s.replace("exec compile(ur'", "")
        s = s.replace("' + '\\n', '', 'single')", "")
    return s


def ignore_prompts_and_output(aString):
    r"""
    Given a string s that defines an input block of code, if the first
    line begins in ``sage:`` (or ``>>>``), strip out all lines that
    don't begin in either ``sage:`` (or ``>>>``) or ``...``, and
    remove all ``sage:`` (or ``>>>``) and ``...`` from the beginning
    of the remaining lines.

    TESTS::

        sage: test1 = sagenb.notebook.worksheet.__internal_test1
        sage: test1 == sagenb.notebook.worksheet.ignore_prompts_and_output(
            test1)
        True
        sage: test2 = sagenb.notebook.worksheet.__internal_test2
        sage: sagenb.notebook.worksheet.ignore_prompts_and_output(test2)
        '2 + 2\n'
    """
    s = aString.lstrip()
    is_example = s.startswith('sage:') or s.startswith('>>>')
    if not is_example:
        return aString  # return original, not stripped copy
    new = ''
    lines = s.split('\n')
    for line in lines:
        line = line.lstrip()
        if line.startswith('sage:'):
            new += after_first_word(line).lstrip() + '\n'
        elif line.startswith('>>>'):
            new += after_first_word(line).lstrip() + '\n'
        elif line.startswith('...'):
            new += after_first_word(line) + '\n'
    return new


def after_first_word(s):
    r"""
    Return everything after the first whitespace_re in the string s.
    Returns the empty string if there is nothing after the first
    whitespace_re.

    INPUT:

    -  ``s`` - string

    OUTPUT: a string

    EXAMPLES::

        sage: from sagenb.notebook.worksheet import after_first_word
        sage: after_first_word("\%gap\n2+2\n")
        '2+2\n'
        sage: after_first_word("2+2")
        ''
    """
    i = whitespace_re.search(s)
    if i is None:
        return ''
    return s[i.start() + 1:]


def extract_cells(text):
    split_last = split_last_text_re.findall(text)
    text, last_text_cell = split_last[0] if split_last else ('', text.strip())
    cells = []
    for txt, meta, inp, outp in extract_cells_re.findall(text):
        if txt:
            cells.append(('plain', txt))
        meta = dict(meta_re.findall(meta))
        idx = None if 'id' not in meta else int(meta['id'])
        cells.append(('compute', (idx, inp, outp)))
    if last_text_cell:
        cells.append(('plain', last_text_cell))
    return cells


def extract_text(text, start='', default=gettext('Untitled')):
    # If the first line is "system: ..." , then it is the system.  Otherwise
    # the system is Sage.
    text = text.lstrip().splitlines()
    if not (text and text[0].startswith(start)):
        name = default
    else:
        name = text.pop(0)[len(start):].strip()
    return name, '\n'.join(text)


def search_keywords(s):
    r"""
    The point of this function is to allow for searches like this::

                  "ws 7" foo bar  Modular  '"the" end'

    i.e., where search terms can be in quotes and the different quote
    types can be mixed.

    INPUT:

    -  ``s`` - a string

    OUTPUT:

    -  ``list`` - a list of strings
    """
    return [k[1] if k[0] else k[2] for k in search_keywords_re.findall(s)]


def best_completion(s, word):
    completions = s.split()
    try:
        chars = completions.pop()[len(word):]
    except IndexError:
        return ''

    best = []
    for new_char in chars:
        test_word = word + new_char
        for w in completions:
            if not w.startswith(test_word):
                return ''.join(best)
        word = test_word
        best.append(new_char)
    return ''.join(best)
