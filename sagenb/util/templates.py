from __future__ import absolute_import

import datetime
import time
import os
import re

from flask import g
from flask.ext.babel import format_datetime
from flask.ext.babel import ngettext
from flask.ext.themes2 import render_theme_template

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


def clean_name(name):
    """
    Converts a string to a safe/clean name by converting non-alphanumeric
    characters to underscores.

    INPUT:

    - name -- a string

    EXAMPLES::

        sage: from sagenb.util.templates import clean_name
        sage: print clean_name('this!is@bad+string')
        this_is_bad_string
    """
    return ''.join([x if x.isalnum() else '_' for x in name])


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
        nrows += int((len(rows[i]) - 1) / ncols)
    return nrows


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
    theme = g.notebook.conf()['theme']
    return render_theme_template(theme, template, **context)


# Message template

def message(msg, cont='/', username=None, **kwds):
    """Returns an error message to the user."""
    template_dict = {'msg': msg, 'cont': cont, 'username': username}
    template_dict.update(kwds)
    return render_template(os.path.join('html', 'error_message.html'),
                           **template_dict)
