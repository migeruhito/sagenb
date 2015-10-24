# -*- coding: utf-8 -*-
"""
HTML Templating for the Notebook

AUTHORS:

- Bobby Moretti (2007-07-18): initial version

- Timothy Clemans and Mike Hansen (2008-10-27): major update
"""
#############################################################################
#       Copyright (C) 2007 William Stein <wstein@gmail.com>
#  Distributed under the terms of the GNU General Public License (GPL)
#  The full text of the GPL is available at:
#                  http://www.gnu.org/licenses/
#############################################################################

import jinja2

import os
import re

from flask import current_app as app
from flask.ext.babel import gettext
from flask.ext.babel import ngettext

from sagenb.misc.misc import SAGE_VERSION
from sagenb.misc.misc import DATA

if os.environ.has_key('SAGENB_TEMPLATE_PATH'):
    if not os.path.isdir(os.environ['SAGENB_TEMPLATE_PATH']):
        raise ValueError("Enviromental variable SAGENB_TEMPLATE_PATH points to\
                         a non-existant directory")
    TEMPLATE_PATH = os.environ['SAGENB_TEMPLATE_PATH']
else:
    TEMPLATE_PATH = os.path.join(DATA, 'sage')

css_illegal_re = re.compile(r'[^-A-Za-z_0-9]')

def css_escape(string):
    r"""
    Returns a string with all characters not legal in a css name
    replaced with hyphens (-).

    INPUT:

    - ``string`` -- the string to be escaped.

    EXAMPLES::

        sage: from sagenb.notebook.template import css_escape
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
        m = int(t/60)
        return ngettext('%(num)d minute', '%(num)d minutes', m)
    if t < 3600*24:
        h = int(t/3600)
        return ngettext('%(num)d hour', '%(num)d hours', h)
    d = int(t/(3600*24))
    return ngettext('%(num)d day', '%(num)d days', d)

def clean_name(name):
    """
    Converts a string to a safe/clean name by converting non-alphanumeric characters to underscores.

    INPUT:

    - name -- a string

    EXAMPLES::

        sage: from sagenb.notebook.template import clean_name
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


def template(filename, **user_context):
    """
    Returns HTML, CSS, etc., for a template file rendered in the given
    context.

    INPUT:

    - ``filename`` - a string; the filename of the template relative
      to ``sagenb/data/templates``

    - ``user_context`` - a dictionary; the context in which to evaluate
      the file's template variables

    OUTPUT:

    - a string - the rendered HTML, CSS, etc.

    EXAMPLES::

        sage: from sagenb.notebook.template import template
        sage: s = template(os.path.join('html', 'yes_no.html')); type(s)
        <type 'unicode'>
        sage: 'Yes' in s
        True
        sage: u = unicode('Are Gröbner bases awesome?','utf-8')
        sage: s = template(os.path.join('html', 'yes_no.html'), message=u)
        sage: 'Gr\xc3\xb6bner' in s.encode('utf-8')
        True
    """
    from sagenb.notebook.notebook import MATHJAX, JEDITABLE_TINYMCE
    from misc import notebook
    #A dictionary containing the default context
    default_context = {'sitename': gettext('Sage Notebook'),
                       'sage_version': SAGE_VERSION,
                       'MATHJAX': MATHJAX,
                       'gettext': gettext,
                       'JEDITABLE_TINYMCE': JEDITABLE_TINYMCE,
                       'conf': notebook.conf() if notebook else None}
    try:
        tmpl = app.jinja_env.get_template(filename)
    except jinja2.exceptions.TemplateNotFound:
        return "Notebook Bug -- missing template %s"%filename

    context = dict(default_context)
    context.update(user_context)
    r = tmpl.render(**context)
    return r
