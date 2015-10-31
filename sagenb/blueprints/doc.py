"""
Documentation functions

URLS to do:

###/doc/live/   - WorksheetFile(os.path.join(DOC, name)
###/doc/static/ - DOC/index.html
"""
from __future__ import absolute_import

import os
from flask import Blueprint
from flask import g
from flask.ext.babel import gettext
from flask.helpers import send_from_directory

from ..misc.misc import SAGE_DOC

from ..flask_version import templates
from ..flask_version.decorators import login_required
from .worksheet import worksheet_file

_ = gettext

doc = Blueprint('doc', __name__)

# TODO: sage dependency
DOC = os.path.join(SAGE_DOC, 'output', 'html', 'en')


@doc.route('/static/', defaults={'filename': 'index.html'})
@doc.route('/static/<path:filename>')
def static(filename):
    return send_from_directory(DOC, filename)


@doc.route('/live/')
@doc.route('/live/<manual>/<path:path_static>/_static/<path:filename>')
@doc.route('/live/<path:filename>')
@login_required
def live(filename=None, manual=None, path_static=None):
    """
    The docs reference a _static URL in the current directory, even if
    the real _static directory only lives in the root of the manual.
    This function strips out the subdirectory part and returns the
    file from the _static directory in the root of the manual.

    This seems like a Sphinx bug: the generated html file should not
    reference a _static in the current directory unless there actually
    is a _static directory there.

    TODO: Determine if the reference to a _static in the current
    directory is a bug in Sphinx, and file a report or see if it has
    already been fixed upstream.
    """
    if filename is None:
        return templates.message(_('nothing to see.'), username=g.username)
    if path_static is not None:
        path_static = os.path.join(DOC, manual, '_static')
        return send_from_directory(path_static, filename)

    if filename.endswith('.html'):
        filename = os.path.join(DOC, filename)
        return worksheet_file(filename)
    else:
        return send_from_directory(DOC, filename)
