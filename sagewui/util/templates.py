from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from builtins import range
from builtins import object

import datetime
import time
import re

from collections import defaultdict
from hashlib import sha1

from jsmin import jsmin

from flask import g
from flask_babel import format_datetime
from flask_babel import get_locale
from flask_babel import ngettext
from flask_themes2 import render_theme_template

from . import cached_property
from . import grouper
from . import N_
from . import nN_
from .keymaps_js import get_keyboard

from ..config import mathjax_macros
from ..config import KEYS
from ..config import SAGE_VERSION
from flask import json

css_illegal_re = re.compile(r'[^-A-Za-z_0-9]')


# jinja2 filters

def css_escape(string):
    r"""
    Returns a string with all characters not legal in a css name
    replaced with hyphens (-).

    INPUT:

    - ``string`` -- the string to be escaped.

    EXAMPLES::

        sage: from sagenb.util.templates import css_escape
        sage: css_escape('abcd')
        'abcd'
        sage: css_escape('12abcd')
        '12abcd'
        sage: css_escape(r'\'"abcd\'"')
        '---abcd---'
        sage: css_escape('my-invalid/identifier')
        'my-invalid-identifier'
        sage: css_escape(r'quotes"mustbe!escaped')
        'quotes-mustbe-escaped'
    """
    return css_illegal_re.sub('-', string)


def prettify_time_ago(t):
    """
    Converts seconds to a meaningful string.

    INPUT

    - t -- time in seconds

    """
    if t < 60:
        s = int(t)
        return ngettext('%(num)d second', '%(num)d seconds', s)
    if t < 3600:
        m = int(t / 60)
        return ngettext('%(num)d minute', '%(num)d minutes', m)
    if t < 3600 * 24:
        h = int(t / 3600)
        return ngettext('%(num)d hour', '%(num)d hours', h)
    d = int(t / (3600 * 24))
    return ngettext('%(num)d day', '%(num)d days', d)


def convert_time_to_string(t):
    """
    Converts ``t`` (in Unix time) to a locale-specific string
    describing the time and date.
    """
    try:
        return format_datetime(datetime.datetime.fromtimestamp(float(t)))
    except AttributeError:  # testing as opposed to within the Flask app
        return time.strftime('%B %d, %Y %I:%M %p', time.localtime(float(t)))


def number_of_rows(txt, ncols):
    r"""
    Returns the number of rows needed to display a string, given a
    maximum number of columns per row.

    INPUT:

    - ``txt`` - a string; the text to "wrap"

    - ``ncols`` - an integer; the number of word wrap columns

    OUTPUT:

    - an integer

    EXAMPLES::

        sage: from sagenb.notebook.cell import number_of_rows
        sage: s = "asdfasdf\nasdfasdf\n"
        sage: number_of_rows(s, 8)
        2
        sage: number_of_rows(s, 5)
        4
        sage: number_of_rows(s, 4)
        4
    """
    rows = txt.splitlines()
    nrows = len(rows)
    for i in range(nrows):
        nrows += (len(rows[i]) - 1) // ncols
    return nrows


def join_max(it, maxi=None, sep=', '):
    it = list(it)
    if maxi is not None and len(it) > maxi:
        it = it[:maxi]
        it.append('...')
    return sep.join(it)


# theme template rendering

def render_template(template, **context):
    """
    For themes to work this replacement of flask.render_template must be used.

    INPUT:

    - As in flask.render_template

    OUTPUT:

    - As in flask.render_template, but if the current theme miss the template,
      the application's normal template is served.

    EXAMPLES::

        sage: from sagenb.util.templates import render_template
        sage: type(render_template)
    """
    theme = g.notebook.conf['theme']
    return render_theme_template(theme, template, **context)


# Message template

def message(msg, cont='/', username=None, **kwds):
    """Returns an error message to the user."""
    template_dict = {
        'msg': msg, 'cont': cont,
        'username': username,
        'sage_version': SAGE_VERSION
        }
    template_dict.update(kwds)
    return render_template('html/error_message.html', **template_dict)


# Dynamic javascript

class DynamicJs(object):
    def __init__(self, debug_mode=False):
        self.debug_mode = debug_mode
        self.__localization = {}
        self.__keyboard = {}

    @cached_property()
    def javascript(self):
        """
        Return javascript library for the Sage Notebook.  This is done by
        reading the template ``notebook_lib.js`` where all of the
        javascript code is contained and replacing a few of the values
        specific to the running session.

        Before the code is returned (as a string), it is run through a
        JavascriptCompressor to minimize the amount of data needed to be
        sent to the browser.

        The code and a hash of the code is returned.

        .. note::

           This the output of this function is cached so that it only
           needs to be generated once.

        EXAMPLES::

            sage: from sagenb.notebook.js import javascript
            sage: s = javascript()
            sage: s[0][:30]
            '/* JavaScriptCompressor 0.1 [w'

        """
        keyhandler = JSKeyHandler()
        for k in KEYS:
            keyhandler.add(*k)

        s = render_template('js/notebook_dynamic.js',
                            KEY_CODES=keyhandler.all_tests(),
                            debug_mode=self.debug_mode)
        s = jsmin(s)
        return (s, sha1(s.encode('utf-8')).hexdigest())

    @property
    def localization(self):
        locale = repr(get_locale())
        if self.__localization.get(locale, None) is None:
            data = render_template('js/localization.js', N_=N_, nN_=nN_)
            self.__localization[locale] = (
                data, sha1(repr(data).encode('utf-8')).hexdigest())

        return self.__localization[locale]

    @cached_property()
    def mathjax(self):
        data = render_template('js/mathjax_sage.js',
                               theme_mathjax_macros=mathjax_macros)
        return (
            data, sha1(repr(data).encode('utf-8')).hexdigest())

    def keyboard(self, browser_os):
        if self.__keyboard.get(browser_os, None) is None:
            data = get_keyboard(browser_os)
            self.__keyboard[browser_os] = (
                data, sha1(repr(data).encode('utf-8')).hexdigest())

        return self.__keyboard[browser_os]

    def clear_cache(self):
        del self.javascript
        del self.mathjax
        self.__localization = {}
        self.__keyboard = {}


class JSKeyHandler(object):
    """
    This class is used to make javascript functions to check
    for specific keyevents.
    """
    def __init__(self):
        self.key_codes = defaultdict(list)

    def set(self, name, key='', mod=0):
        """
        Add a named keycode to the handler.  When built by
        ``all_tests()``, it can be called in javascript by
        ``key_<key_name>(event_object)``.  The function returns
        true if the keycode numbered by the ``key`` parameter was
        pressed with the appropriate modifier keys, false otherwise.
        """
        self.key_codes[name] = [JSKeyCode(key, mod)]

    def add(self, name, key='', mod=0):
        """
        Similar to ``set_key(...)``, but this instead checks if
        there is an existing keycode by the specified name, and
        associates the specified key combination to that name in
        addition.  This way, if different browsers don't catch one
        keycode, multiple keycodes can be assigned to the same test.
        """
        self.key_codes[name].append(JSKeyCode(key, mod))

    def all_tests(self):
        """
        Builds all tests currently in the handler.  Returns a string
        of javascript code which defines all functions.
        """
        tests = ''
        for name, keys in self.key_codes.items():
            value = "\n||".join([k.js_test() for k in keys])
            tests += " function key_%s(e) {\n  return %s;\n}" % (name, value)
        return tests


class JSKeyCode(object):
    def __init__(self, key, mod):
        global key_codes
        self.key = key
        self.mod = mod

    def js_test(self):
        return "((e.m=={})&&(e.v=={}))".format(self.key, self.mod)


# json responses

def encode_response(obj, separators=(',', ':'), **kwargs):
    """
    Encodes response data to send to a client.  The current
    implementation uses JSON.  See :mod:`json` for details.

    INPUT:

    - ``obj`` - an object comprised of basic Python types

    - ``separators`` - a string 2-tuple (default: (',', ':'));
      dictionary separators to use

    - ``kwargs`` - additional keyword arguments to pass to the
      encoding function

    OUTPUT:

    - a string

    EXAMPLES::

        sage: from sagenb.notebook.misc import encode_response
        sage: o = [int(3), float(2), {'foo': 'bar'}, None]
        sage: encode_response(o)
        '[3,2.0,{"foo":"bar"},null]'
        sage: d = {'AR': 'MA', int(11): 'foo', 'bar': float(1.0), None: 'blah'}
        sage: encode_response(d, sort_keys = True)
        '{"null":"blah","11":"foo","AR":"MA","bar":1.0}'
        sage: d['archies'] = ['an', 'mon', 'hier']
        sage: d['sub'] = {'shape': 'triangle', 'color': 'blue',
                          'sides': [int(3), int(4), int(5)]}
        sage: encode_response(d, sort_keys = True)
        '{"null":"blah","11":"foo","AR":"MA","archies":["an","mon","hier"],
        "bar":1.0,"sub":{"color":"blue","shape":"triangle","sides":[3,4,5]}}'
        sage: print(encode_response(d, separators = (', ', ': '), indent = 4))
        {
            "...": ...
        }
    """
    # TODO: Serialize class attributes, so we can do, e.g., r_dict.foo
    # = 'bar' instead of r_dict['foo'] = 'bar' below.

    # TODO: Use cjson, simplejson instead?  Serialize Sage types,
    # e.g., Integer, RealLiteral?
    return json.dumps(obj, separators=separators, **kwargs)


# completions


def completions_html(cell_id, s, cols=3):
    """
    Returns tabular HTML code for a list of introspection completions.

    INPUT:

    - ``cell_id`` - an integer or a string; the ID of the ambient cell

    - ``s`` - a string with space separated completions

    - ``cols`` max number of columns


    OUTPUT:

    - html code
    """
    if 'no completions of' in s:
        return ''

    s = s.split()
    if len(s) <= 1:
        return ''  # don't show a window, just replace it

    completions = enumerate(grouper(s, (len(s) + cols - 1) // cols, ''))
    return render_template(
        'html/worksheet/completions.html',
        cell_id=cell_id,
        # Transpose and enumerate completions to column-major
        completions_enumerated=completions)
