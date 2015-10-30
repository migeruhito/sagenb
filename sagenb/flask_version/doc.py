"""
Documentation functions

URLS to do:

###/pdf/       <-FILE->  DOC_PDF
###/doc/live/   - WorksheetFile(os.path.join(DOC, name)
###/doc/static/ - DOC/index.html
###/doc/static/reference/ <-FILE-> DOC/reference/
###/doc/reference/media/  <-FILE-> DOC_REF_MEDIA

/src/             - SourceBrowser
/src/<name>       - Source(os.path.join(SRC,name), self.username)

"""
from __future__ import absolute_import

import os
from flask import Blueprint
from flask import g
from flask import current_app
from flask.ext.babel import gettext
from flask.helpers import send_from_directory

from sagenb.misc.misc import SAGE_DOC

from .decorators import login_required
from .worksheet import worksheet_file

_ = gettext

doc = Blueprint('doc', __name__)

DOC = os.path.join(SAGE_DOC, 'output', 'html', 'en')

################
# Static paths #
################

#The static documentation paths are currently set in base.SageNBFlask.__init__

@doc.route('/doc/static/', defaults={'filename': 'index.html'})
@doc.route('/doc/static/<path:filename>')
def doc_static(filename):
    return send_from_directory(DOC, filename)


@doc.route('/doc/live/')
@doc.route('/doc/live/<manual>/<path:path_static>/_static/<path:filename>')
@doc.route('/doc/live/<path:filename>')
@login_required
def doc_live(filename=None, manual=None, path_static=None):
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
        return current_app.message(_('nothing to see.'), username=g.username)
    if path_static is not None:
        path_static = os.path.join(DOC, manual, '_static')
        return send_from_directory(path_static, filename)

    if filename.endswith('.html'):
        filename = os.path.join(DOC, filename)
        return worksheet_file(filename)
    else:
        return send_from_directory(DOC, filename)
