from __future__ import absolute_import

import base64
import bz2
import os
import re
import threading
import time
import urllib2
from cgi import escape
from collections import defaultdict
from functools import wraps
from urlparse import urlparse

from flask import Blueprint
from flask import make_response
from flask import url_for
from flask import request
from flask import redirect
from flask import g
from flask import current_app
from flask.ext.babel import gettext
from flask.helpers import send_file
from flask.helpers import send_from_directory
from jinja2.exceptions import TemplateNotFound
from werkzeug.utils import secure_filename

from ..config import UN_GUEST
from ..config import UN_PUB
from ..config import UN_SAGE
from ..notebook.interact import INTERACT_UPDATE_PREFIX
from ..util import tmp_filename
from ..util import unicode_str
from ..util.docHTMLProcessor import SphinxHTMLProcessor
# New UI
from ..util.newui import extended_wst_basic
# New UI end
from ..util.templates import encode_response
from ..util.templates import message as message_template
from ..util.templates import prettify_time_ago
from ..util.templates import render_template

from ..util.decorators import guest_or_login_required
from ..util.decorators import login_required

_ = gettext

worksheet = Blueprint('worksheet', __name__)
worksheet_locks = defaultdict(threading.Lock)


def worksheet_view(f):
    """
    The `username` in the wrapper function is the username in the URL to the
    worksheet, which normally is the owner of the worksheet.  Don't confuse
    this with `g.username`, the actual username of the user looking at the
    worksheet.
    """
    @login_required
    @wraps(f)
    def wrapper(username, id, **kwds):
        worksheet_filename = username + "/" + id
        try:
            worksheet = kwds['worksheet'] = (
                g.notebook.filename_wst(worksheet_filename))
        except KeyError:
            return message_template(
                _("You do not have permission to access this worksheet"),
                username=g.username)

        with worksheet_locks[worksheet]:
            owner = worksheet.owner

            if owner != UN_SAGE and g.username != owner:
                if not worksheet.is_published:
                    if (g.username not in worksheet.collaborators and
                            not g.notebook.user_manager[g.username].is_admin):
                        return message_template(
                            _("You do not have permission to access this "
                              "worksheet"),
                            username=g.username)

            if not worksheet.is_published:
                worksheet.set_active(g.username)

            # This was in twist.Worksheet.childFactory
            g.notebook.updater.update()

            return f(username, id, **kwds)

    return wrapper


def url_for_worksheet(worksheet):
    """
    Returns the url for a given worksheet.
    """
    return url_for('worksheet.worksheet_v', username=worksheet.owner,
                   id=str(worksheet.id_number))


def get_cell_id():
    """
    Returns the cell ID from the request.

    We cast the incoming cell ID to an integer, if it's possible.
    Otherwise, we treat it as a string.
    """
    try:
        return int(request.values['id'])
    except ValueError:
        return request.values['id']


# notebook html

def render_ws_template(ws=None, username=UN_GUEST, admin=False, do_print=False,
                       publish=False):
    r"""
    Return the HTML evaluated for a worksheet.

    INPUT:

    - ``ws`` - a Worksheet (default: None)

    - ``username`` - a string (default: UN_GUEST)

    - ``admin`` - a bool (default: False)

    - ``do_print`` - a bool (default: False)

    OUTPUT:

    - a string - the worksheet rendered as HTML

    EXAMPLES::

        sage: from sagenb.config import UN_ADMIN
        sage: nb = sagenb.notebook.notebook.Notebook(
            tmp_dir(ext='.sagenb'))
        sage: nb.user_manager.create_default_users('password')
        sage: W = nb.create_wst('Test', UN_ADMIN)
        sage: render_ws_template(W, UN_ADMIN)
        u'...Test...cell_input...if (e.shiftKey)...state_number...'
    """
    if ws is None:
        return message_template(_("The worksheet does not exist"),
                                username=username)

    # New UI
    try:
        return render_template(os.path.join('html', 'worksheet.html'))
    except TemplateNotFound:
        pass
    # New UI end

    nb = g.notebook

    if ws.docbrowser or ws.is_published:
        if ws.is_published or nb.user_manager[username].is_guest:
            template_name = 'guest_worksheet_page.html'
            publish = True
        else:
            template_name = 'doc_page.html'
    elif do_print:
        template_name = 'print_worksheet.html'
    else:
        template_name = 'worksheet_page.html'

    return render_template(os.path.join('html', 'notebook', template_name),
                           worksheet=ws,
                           notebook=nb, do_print=do_print, publish=publish,
                           username=username)


def html_worksheet_revision_list(username, worksheet):
    r"""
    Return HTML for the revision list of a worksheet.

    INPUT:

    - ``username`` - a string

    - ``worksheet`` - an instance of Worksheet

    OUTPUT:

    - a string - the HTML for the revision list

    EXAMPLES::

        sage: from sagenb.config import UN_ADMIN
        sage: nb = sagenb.notebook.notebook.Notebook(
            tmp_dir(ext='.sagenb'))
        sage: nb.user_manager.create_default_users('password')
        sage: W = nb.create_wst('Test', UN_ADMIN)
        sage: W.body
        u'\n\n{{{id=1|\n\n///\n}}}'
        sage: W.save_snapshot(UN_ADMIN)
        sage: nb.html_worksheet_revision_list(UN_ADMIN, W)
        u'...Revision...Last Edited...ago...'
    """
    data = worksheet.snapshot_data()  # pairs ('how long ago', key)

    return render_template(
        os.path.join("html", "notebook", "worksheet_revision_list.html"),
        data=data, worksheet=worksheet,
        notebook=g.notebook,
        username=username)


def html_specific_revision(username, ws, rev):
    r"""
    Return the HTML for a specific revision of a worksheet.

    INPUT:

    - ``username`` - a string

    - ``ws`` - an instance of Worksheet

    - ``rev`` - a string containing the key of the revision

    OUTPUT:

    - a string - the revision rendered as HTML
    """
    nb = g.notebook
    t = time.time() - float(rev[:-4])
    time_ago = prettify_time_ago(t)

    filename = ws.snapshot_filename(rev)
    txt = bz2.decompress(open(filename).read())
    W = nb.scratch_wst
    W.name = 'Revision of ' + ws.name
    W.delete_cells_directory()
    W.edit_save(txt)

    data = ws.snapshot_data()  # pairs ('how long ago', key)
    prev_rev = None
    next_rev = None
    for i in range(len(data)):
        if data[i][1] == rev:
            if i > 0:
                prev_rev = data[i - 1][1]
            if i < len(data) - 1:
                next_rev = data[i + 1][1]
            break

    return render_template(
        os.path.join("html", "notebook", "specific_revision.html"),
        worksheet=W,  # the revision, not the original!
        username=username, rev=rev, prev_rev=prev_rev,
        next_rev=next_rev, time_ago=time_ago,
        do_print=True, publish=True)


def html_share(worksheet, username):
    r"""
    Return the HTML for the "share" page of a worksheet.

    INPUT:

    - ``username`` - a string

    - ``worksheet`` - an instance of Worksheet

    OUTPUT:

    - string - the share page's HTML representation

    EXAMPLES::

        sage: from sagenb.config import UN_ADMIN
        sage: nb = sagenb.notebook.notebook.Notebook(
            tmp_dir(ext='.sagenb'))
        sage: nb.user_manager.create_default_users('password')
        sage: W = nb.create_wst('Test', UN_ADMIN)
        sage: nb.html_share(W, UN_ADMIN)
        u'...currently shared...add or remove collaborators...'
    """
    return render_template(
        os.path.join("html", "notebook", "worksheet_share.html"),
        worksheet=worksheet,
        notebook=g.notebook,
        username=username)


def html_download_or_delete_datafile(ws, username, filename):
    r"""
    Return the HTML for the download or delete datafile page.

    INPUT:

    - ``username`` - a string

    - ``ws`` - an instance of Worksheet

    - ``filename`` - a string; the name of the file

    OUTPUT:

    - a string - the page rendered as HTML

    EXAMPLES::

        sage: from sagenb.config import UN_ADMIN
        sage: nb = sagenb.notebook.notebook.Notebook(
            tmp_dir(ext='.sagenb'))
        sage: nb.user_manager.create_default_users('password')
        sage: W = nb.create_wst('Test', UN_ADMIN)
        sage: nb.html_download_or_delete_datafile(W, UN_ADMIN, 'bar')
        u'...Data file: bar...DATA is a special variable...uploaded...'
    """
    ext = os.path.splitext(filename)[1].lower()
    file_is_image, file_is_text = False, False
    text_file_content = ""

    if ext in ['.png', '.jpg', '.gif']:
        file_is_image = True
    if ext in ['.txt', '.tex', '.sage', '.spyx', '.py', '.f', '.f90',
               '.c']:
        file_is_text = True
        text_file_content = open(os.path.join(
            ws.data_directory, filename)).read()

    return render_template(os.path.join("html", "notebook",
                                        "download_or_delete_datafile.html"),
                           worksheet=ws, notebook=g.notebook,
                           username=username,
                           filename_=filename,
                           file_is_image=file_is_image,
                           file_is_text=file_is_text,
                           text_file_content=text_file_content)


def html_edit_window(worksheet, username):
    r"""
    Return HTML for a window for editing ``worksheet``.

    INPUT:

    - ``username`` - a string containing the username

    - ``worksheet`` - a Worksheet instance

    OUTPUT:

    - a string - the editing window's HTML representation

    EXAMPLES::

        sage: from sagenb.config import UN_ADMIN
        sage: nb = sagenb.notebook.notebook.Notebook(
            tmp_dir(ext='.sagenb'))
        sage: nb.user_manager.create_default_users('password')
        sage: W = nb.create_wst('Test', UN_ADMIN)
        sage: nb.html_edit_window(W, UN_ADMIN)
        u'...textarea class="plaintextedit"...{{{id=1|...//...}}}...'
    """

    return render_template(
        os.path.join("html", "notebook", "edit_window.html"),
        worksheet=worksheet,
        notebook=g.notebook,
        username=username)


def html_beforepublish_window(worksheet, username):
    r"""
    Return HTML for the warning and decision page displayed prior
    to publishing the given worksheet.

    INPUT:

    - ``worksheet`` - an instance of Worksheet

    - ``username`` - a string

    OUTPUT:

    - a string - the pre-publication page rendered as HTML

    EXAMPLES::

        sage: from sagenb.config import UN_ADMIN
        sage: nb = sagenb.notebook.notebook.Notebook(
            tmp_dir(ext='.sagenb'))
        sage: nb.user_manager.create_default_users('password')
        sage: W = nb.create_wst('Test', UN_ADMIN)
        sage: nb.html_beforepublish_window(W, UN_ADMIN)
        u'...want to publish this worksheet?...re-publish when changes...'
    """
    return render_template(
        os.path.join("html", "notebook", "beforepublish_window.html"),
        worksheet=worksheet,
        notebook=g.notebook,
        username=username)


def html_afterpublish_window(worksheet, username, url, dtime):
    r"""
    Return HTML for a given worksheet's post-publication page.

    INPUT:

    - ``worksheet`` - an instance of Worksheet

    - ``username`` - a string

    - ``url`` - a string representing the URL of the published
      worksheet

    - ``dtime`` - an instance of time.struct_time representing the
      publishing time

    OUTPUT:

    - a string - the post-publication page rendered as HTML
    """
    time_ = time.strftime("%B %d, %Y %I:%M %p", dtime)

    return render_template(
        os.path.join("html", "notebook", "afterpublish_window.html"),
        worksheet=worksheet,
        notebook=g.notebook,
        username=username, url=url, time=time_)


def html_upload_data_window(ws, username):
    r"""
    Return HTML for the "Upload Data" window.

    INPUT:

    - ``worksheet`` - an instance of Worksheet

    - ``username`` - a string

    OUTPUT:

    - a string - the HTML representation of the data upload window

    EXAMPLES::

        sage: from sagenb.config import UN_ADMIN
        sage: nb = sagenb.notebook.notebook.Notebook(
            tmp_dir(ext='.sagenb'))
        sage: nb.user_manager.create_default_users('password')
        sage: W = nb.create_wst('Test', UN_ADMIN)
        sage: nb.html_upload_data_window(W, UN_ADMIN)
        u'...Upload or Create Data File...Browse...url...name of a new...'
    """
    return render_template(
        os.path.join("html", "notebook", "upload_data_window.html"),
        worksheet=ws, username=username)


# worksheet html

def html_ratings_info(ws, username=None):
    r"""
    Return html that renders to give a summary of how this worksheet
    has been rated.

    OUTPUT:

    - ``string`` -- a string of HTML as a bunch of table rows.

    EXAMPLES::

        sage: from sagenb.config import UN_ADMIN
        sage: nb = sagenb.notebook.notebook.Notebook(
            tmp_dir(ext='.sagenb'))
        sage: nb.user_manager.create_default_users('password')
        sage: W = nb.create_wst('Publish Test', UN_ADMIN)
        sage: W.rate(0, 'this lacks content', 'riemann')
        sage: W.rate(3, 'this is great', 'hilbert')
        sage: W.html_ratings_info()
        u'...hilbert...3...this is great...this lacks content...'
    """
    return render_template(
        os.path.join('html', 'worksheet', 'ratings_info.html'),
        worksheet=ws, username=username)


# Public Worksheets

def html_plain_text_window(worksheet, username):
    r"""
    Return HTML for the window that displays a plain text version
    of the worksheet.

    INPUT:

    -  ``worksheet`` - a Worksheet instance

    -  ``username`` - a string

    OUTPUT:

    - a string - the plain text window rendered as HTML

    EXAMPLES::

        sage: from sagenb.config import UN_ADMIN
        sage: nb = sagenb.notebook.notebook.Notebook(
            tmp_dir(ext='.sagenb'))
        sage: nb.user_manager.create_default_users('password')
        sage: W = nb.create_wst('Test', UN_ADMIN)
        sage: nb.html_plain_text_window(W, UN_ADMIN)
        u'...pre class="plaintext"...cell_intext...textfield...'
    """
    plain_text = worksheet.plain_text(prompts=True, banner=False)
    plain_text = escape(plain_text).strip()

    return render_template(
        os.path.join("html", "notebook", "plain_text_window.html"),
        worksheet=worksheet,
        notebook=g.notebook,
        username=username, plain_text=plain_text)


def pub_worksheet(source):
    # TODO: Independent pub pool and server settings.
    nb = g.notebook
    proxy = doc_worksheet()
    proxy.name = source.name
    proxy.last_change = source.last_change
    proxy.worksheet_that_was_published = nb.came_from_wst(source)
    nb.initialize_wst(source, proxy)
    proxy.set_tags({'_pub_': [True]})
    proxy.save()
    return proxy


##############################
# Views
##############################


@worksheet.route('/new_worksheet')
@login_required
def new_worksheet():
    if g.notebook.readonly_user(g.username):
        return message_template(
            _("Account is in read-only mode"),
            cont=url_for('worksheet_listing.home', username=g.username))

    W = g.notebook.create_wst(gettext("Untitled"), g.username)
    return redirect(url_for_worksheet(W))


@worksheet.route('/home/<username>/<id>/')
@worksheet_view
def worksheet_v(username, id, worksheet=None):
    """
    username is the owner of the worksheet
    id is the id of the worksheet
    """
    if worksheet is not None:
        worksheet.sage()
    return render_ws_template(ws=worksheet, username=g.username)


# Public Worksheets

@worksheet.route('/home/pub/<id>/')
@guest_or_login_required
def public_worksheet(id):
    filename = 'pub/%s' % id
    try:
        original_worksheet = g.notebook.filename_wst(filename)
    except KeyError:
        return message_template(
            _("Requested public worksheet does not exist"))

    if g.notebook.conf['pub_interact']:
        worksheet = pub_worksheet(original_worksheet)
        owner = worksheet.owner
        worksheet.owner = UN_PUB
        s = render_ws_template(ws=worksheet, username=g.username)
        worksheet.owner = owner
    else:
        s = render_ws_template(ws=original_worksheet, username=g.username)
    return s


@worksheet.route('/home/pub/<id>/download/<path:title>')
def public_worksheet_download(id, title):
    worksheet_filename = "pub" + "/" + id
    try:
        worksheet = g.notebook.filename_wst(worksheet_filename)
    except KeyError:
        return message_template(
            _("You do not have permission to access this worksheet"),
            username=g.username)
    return unconditional_download(worksheet, title)


@worksheet.route('/home/pub/<id>/cells/<path:filename>')
def public_worksheet_cells(id, filename):
    worksheet_filename = "pub" + "/" + id
    try:
        worksheet = g.notebook.filename_wst(worksheet_filename)
    except KeyError:
        return message_template(
            _("You do not have permission to access this worksheet"),
            username=g.username)
    return send_from_directory(worksheet.cells_directory, filename)


published_commands_allowed = set([
    'alive', 'cells', 'cell_update', 'data', 'download', 'edit_published_page',
    'eval', 'quit_sage', 'rate', 'rating_info', 'new_cell_before',
    'new_cell_after', 'introspect', 'delete_all_output', 'copy',
    'restart_sage', 'jsmol'])

readonly_commands_allowed = set([
    'alive', 'cells', 'data', 'datafile', 'download', 'quit_sage',
    'rating_info', 'delete_all_output', 'jsmol'])


def worksheet_command(target, **route_kwds):
    if 'methods' not in route_kwds:
        route_kwds['methods'] = ['GET', 'POST']

    def decorator(f):
        @worksheet.route('/home/<username>/<id>/' + target, **route_kwds)
        @worksheet_view
        @wraps(f)
        def wrapper(*args, **kwds):
            # We remove the first two arguments corresponding to the
            # username and the worksheet id
            username_id = args[:2]
            args = args[2:]

            #####################
            # Public worksheets #
            #####################
            # _sage_ is used by live docs and published interacts
            if username_id and username_id[0] in [UN_SAGE]:
                if target.split('/')[0] not in published_commands_allowed:
                    raise NotImplementedError(
                        "User _sage_ can not access URL %s" % target)
            if g.notebook.readonly_user(g.username):
                if target.split('/')[0] not in readonly_commands_allowed:
                    return message_template(
                        _("Account is in read-only mode"),
                        cont=url_for('worksheet_listing.home',
                                     username=g.username))

            # Make worksheet a non-keyword argument appearing before the
            # other non-keyword arguments.
            worksheet = kwds.pop('worksheet', None)
            if worksheet is not None:
                args = (worksheet,) + args

            return f(*args, **kwds)

        # This function shares some functionality with url_for_worksheet.
        # Maybe we can refactor this some?
        def wc_url_for(worksheet, *args, **kwds):
            kwds['username'] = g.username
            kwds['id'] = str(worksheet.id_number)
            return url_for('.{}'.format(f.__name__), *args, **kwds)

        wrapper.url_for = wc_url_for

        return wrapper
    return decorator


@worksheet_command('rename')
def worksheet_rename(worksheet):
    worksheet.name = request.values['name']
    return 'done'


@worksheet_command('alive')
def worksheet_alive(worksheet):
    return str(worksheet.state_number)


@worksheet_command('system/<system>')
def worksheet_system(worksheet, system):
    worksheet.system = system.strip()
    return 'success'


@worksheet_command('pretty_print/<enable>')
def worksheet_pretty_print(worksheet, enable):
    enable = False if enable == 'false' or enable is False else True
    worksheet.pretty_print = enable
    return 'success'


@worksheet_command('live_3D/<enable>')
def worksheet_live_3D(worksheet, enable):
    worksheet.set_live_3D = enable == 'true'
    return 'success'


@worksheet_command('conf')
def worksheet_conf(worksheet):
    return str(worksheet.conf())


########################################################
# Save a worksheet
########################################################

@worksheet_command('save')
def worksheet_save(worksheet):
    """
    Save the contents of a worksheet after editing it in plain-text
    edit mode.
    """
    if 'button_save' in request.form:
        E = request.values['textfield']
        worksheet.edit_save(E)
        worksheet.record_edit(g.username)
    return redirect(url_for_worksheet(worksheet))


@worksheet_command('save_snapshot')
def worksheet_save_snapshot(worksheet):
    """Save a snapshot of a worksheet."""
    worksheet.save_snapshot(g.username)
    return 'saved'


@worksheet_command('save_and_quit')
def worksheet_save_and_quit(worksheet):
    """Save a snapshot of a worksheet then quit it. """
    worksheet.save_snapshot(g.username)
    worksheet.quit()
    return 'saved'

# XXX: Redundant due to the above?


@worksheet_command('save_and_close')
def worksheet_save_and_close(worksheet):
    """Save a snapshot of a worksheet then quit it. """
    worksheet.save_snapshot(g.username)
    worksheet.quit()
    return 'saved'


@worksheet_command('discard_and_quit')
def worksheet_discard_and_quit(worksheet):
    """Quit the worksheet, discarding any changes."""
    worksheet.revert_to_last_saved_state()
    worksheet.quit()
    return 'saved'  # XXX: Should this really be saved?


@worksheet_command('revert_to_last_saved_state')
def worksheet_revert_to_last_saved_state(worksheet):
    worksheet.revert_to_last_saved_state()
    return 'reverted'

# New UI
########################################################
# Worksheet properties
########################################################


@worksheet_command('worksheet_properties')
def worksheet_properties(worksheet):
    """
    Send worksheet properties as a JSON object
    """
    nb = g.notebook
    r = extended_wst_basic(worksheet, nb)

    if worksheet.published_id_number is not None:
        hostname = request.headers.get(
            'host',
            nb.interface + ':' + str(g.notebook.port))

        r['published_url'] = 'http%s://%s/home/%s' % (
            '' if not nb.secure else 's',
            hostname,
            worksheet.published_filename)

    return encode_response(r)

########################################################
# Cell properties
########################################################


@worksheet_command('cell_properties')
def worksheet_cell_properties(worksheet):
    """
    Return the cell with the given id as a JSON object
    """
    id = get_cell_id()
    return encode_response(worksheet.get_cell_with_id(id).basic())
# New UI end

########################################################
# Used in refreshing the cell list
########################################################


@worksheet_command('cell_list')
def worksheet_cell_list(worksheet):
    """
    Return the state number and the HTML for the main body of the
    worksheet, which consists of a list of cells.
    """
    r = {}
    r['state_number'] = worksheet.state_number
    # TODO: Send and actually use the body's HTML.
    r['html_cell_list'] = ''
    # New UI
    r['cell_list'] = [c.basic() for c in worksheet.cells]
    # New UI end

    return encode_response(r)

########################################################
# Set output type of a cell
########################################################


@worksheet_command('set_cell_output_type')
def worksheet_set_cell_output_type(worksheet):
    """
    Set the output type of the cell.

    This enables the type of output cell, such as to allowing wrapping
    for output that is very long.
    """
    id = get_cell_id()
    type = request.values['type']
    worksheet.get_cell_with_id(id).set_cell_output_type(type)
    return ''

########################################################
# Cell creation
########################################################


@worksheet_command('new_cell_before')
def worksheet_new_cell_before(worksheet):
    """Add a new cell before a given cell."""
    r = {}
    r['id'] = id = get_cell_id()
    input = unicode_str(request.values.get('input', ''))
    cell = worksheet.new_cell_before(id, input=input)
    worksheet.increase_state_number()

    r['new_id'] = cell.id
    r['new_html'] = cell.html(div_wrap=False)

    return encode_response(r)


@worksheet_command('new_text_cell_before')
def worksheet_new_text_cell_before(worksheet):
    """Add a new text cell before a given cell."""
    r = {}
    r['id'] = id = get_cell_id()
    input = unicode_str(request.values.get('input', ''))
    cell = worksheet.new_text_cell_before(id, input=input)
    worksheet.increase_state_number()

    r['new_id'] = cell.id
    r['new_html'] = cell.html(editing=True)

    # XXX: Does editing correspond to TinyMCE?  If so, we should try
    # to centralize that code.
    return encode_response(r)


@worksheet_command('new_cell_after')
def worksheet_new_cell_after(worksheet):
    """Add a new cell after a given cell."""
    r = {}
    r['id'] = id = get_cell_id()
    input = unicode_str(request.values.get('input', ''))
    cell = worksheet.new_cell_after(id, input=input)
    worksheet.increase_state_number()

    r['new_id'] = cell.id
    r['new_html'] = cell.html(div_wrap=True)

    return encode_response(r)


@worksheet_command('new_text_cell_after')
def worksheet_new_text_cell_after(worksheet):
    """Add a new text cell after a given cell."""
    r = {}
    r['id'] = id = get_cell_id()
    input = unicode_str(request.values.get('input', ''))
    cell = worksheet.new_text_cell_after(id, input=input)
    worksheet.increase_state_number()

    r['new_id'] = cell.id
    r['new_html'] = cell.html(editing=True)

    # XXX: Does editing correspond to TinyMCE?  If so, we should try
    # to centralize that code.
    return encode_response(r)

########################################################
# Cell deletion
########################################################


@worksheet_command('delete_cell')
def worksheet_delete_cell(worksheet):
    """
    Deletes a worksheet cell, unless there's only one compute cell
    left.  This allows functions which evaluate relative to existing
    cells, e.g., inserting a new cell, to continue to work.
    """
    r = {}
    r['id'] = id = get_cell_id()
    if len(worksheet.compute_cells) <= 1:
        r['command'] = 'ignore'
    else:
        r['command'] = 'delete'
        r['prev_id'] = worksheet.delete_cell_with_id(id)
        r['cell_id_list'] = worksheet.cell_id_list

    return encode_response(r)


@worksheet_command('delete_cell_output')
def worksheet_delete_cell_output(worksheet):
    """Delete's a cell's output."""
    r = {}
    r['id'] = id = get_cell_id()
    worksheet.get_cell_with_id(id).delete_output()
    r['command'] = 'delete_output'

    return encode_response(r)

########################################################
# Evaluation and cell update
########################################################


@worksheet_command('eval')
def worksheet_eval(worksheet):
    """
    Evaluate a worksheet cell.

    If the request is not authorized (the requester did not enter the
    correct password for the given worksheet), then the request to
    evaluate or introspect the cell is ignored.

    If the cell contains either 1 or 2 question marks at the end (not
    on a comment line), then this is interpreted as a request for
    either introspection to the documentation of the function, or the
    documentation of the function and the source code of the function
    respectively.
    """

    r = {}

    r['id'] = id = get_cell_id()
    cell = worksheet.get_cell_with_id(id)
    public = worksheet.tags.get('_pub_', [False])[
        0]  # this is set in pub_worksheet

    if public and not cell.is_interactive_cell():
        r['command'] = 'error'
        r['message'] = (
            'Cannot evaluate non-interactive public cell with ID %r.' % id)
        return encode_response(r)

    worksheet.increase_state_number()

    if public:
        # Make public input cells read-only.
        input_text = cell.input_text()
    else:
        input_text = unicode_str(request.values.get(
            'input', '')).replace('\r\n', '\n')  # DOS

    # Handle an updated / recomputed interact.  TODO: JSON encode
    # the update data.
    if 'interact' in request.values:
        r['interact'] = 1
        input_text = INTERACT_UPDATE_PREFIX
        variable = request.values.get('variable', '')
        if variable != '':
            adapt_number = int(request.values.get('adapt_number', -1))
            value = request.values.get('value', '')
            input_text += (
                "\n_interact_.update('%s', '%s', "
                "%s, _support_.base64.standard_b64decode('%s'), globals())" % (
                    id, variable, adapt_number, value))

        if int(request.values.get('recompute', 0)):
            input_text += "\n_interact_.recompute('%s')" % id

    cell.set_input_text(input_text)

    if int(request.values.get('save_only', '0')):
        g.notebook.updater.update()
        return encode_response(r)
    elif int(request.values.get('text_only', '0')):
        g.notebook.updater.update()
        r['cell_html'] = cell.html()
        return encode_response(r)

    cell.evaluate(username=g.username)

    # whether to insert a new cell or not
    new_cell = int(request.values.get('newcell', 0))
    if new_cell:
        new_cell = worksheet.new_cell_after(id)
        r['command'] = 'insert_cell'
        r['new_cell_id'] = new_cell.id
        r['new_cell_html'] = new_cell.html(div_wrap=False)
    else:
        r['next_id'] = worksheet.next_compute_id(cell)

    g.notebook.updater.update()

    return encode_response(r)


@worksheet_command('cell_update')
def worksheet_cell_update(worksheet):

    r = {}
    r['id'] = id = get_cell_id()

    # update the computation one "step".
    worksheet.check_comp()

    # now get latest status on our cell
    r['status'], cell = worksheet.check_cell(id)

    if r['status'] == 'd':
        r['new_input'] = cell.changed_input_text()
        r['output_html'] = cell.output_html()

        # Update the log.
        t = time.strftime('%Y-%m-%d at %H:%M',
                          time.localtime(time.time()))
        H = "Worksheet '%s' (%s)\n" % (worksheet.name, t)
        H += cell.edit_text(ncols=g.notebook.HISTORY_NCOLS, prompts=False,
                            max_out=g.notebook.HISTORY_MAX_OUTPUT)
        g.notebook.add_to_user_history(H, g.username)
    else:
        r['new_input'] = ''
        r['output_html'] = ''

    if cell.interrupted():
        r['interrupted'] = 'true'
    else:
        r['interrupted'] = 'false'

    if 'Unhandled SIGSEGV' in cell.output_text(raw=True).split('\n'):
        r['interrupted'] = 'restart'
        print 'Segmentation fault detected in output!'

    r['output'] = cell.output_text(html=True) + ' '
    r['output_wrapped'] = cell.output_text(g.notebook.conf['word_wrap_cols'],
                                           html=True) + ' '
    r['introspect_html'] = cell.introspect_html()

    # Compute 'em, if we got 'em.
    worksheet.start_next_comp()

    return encode_response(r)


########################################################
# Cell introspection
########################################################
@worksheet_command('introspect')
def worksheet_introspect(worksheet):
    """
    Cell introspection. This is called when the user presses the tab
    key in the browser in order to introspect.
    """
    r = {}
    r['id'] = id = get_cell_id()

    if worksheet.tags.get('_pub_', [False])[0]:  # tags set in pub_worksheet
        r['command'] = 'error'
        r['message'] = 'Cannot evaluate public cell introspection.'
        return encode_response(r)

    before_cursor = request.values.get('before_cursor', '')
    after_cursor = request.values.get('after_cursor', '')
    cell = worksheet.get_cell_with_id(id)
    cell.evaluate(introspect=[before_cursor, after_cursor])

    r['command'] = 'introspect'
    return encode_response(r)

########################################################
# Edit the entire worksheet
########################################################


@worksheet_command('edit')
def worksheet_edit(worksheet):
    """
    Return a window that allows the user to edit the text of the
    worksheet with the given filename.
    """
    return html_edit_window(worksheet, g.username)


########################################################
# Plain text log view of worksheet
########################################################
@worksheet_command('text')
def worksheet_text(worksheet):
    """
    Return a window that allows the user to edit the text of the
    worksheet with the given filename.
    """
    return html_plain_text_window(worksheet, g.username)

########################################################
# Copy a worksheet
########################################################


@worksheet_command('copy')
def worksheet_copy(worksheet):
    copy = g.notebook.copy_wst(worksheet, g.username)
    if 'no_load' in request.values:
        return ''
    else:
        return redirect(url_for_worksheet(copy))

########################################################
# Get a copy of a published worksheet and start editing it
########################################################


@worksheet_command('edit_published_page')
def worksheet_edit_published_page(worksheet):
    # if user_type(self.username) == UAT_GUEST:
    # return message_template('You must <a href="/">login first</a> in order
    # to edit this worksheet.')

    ws = g.notebook.came_from_wst(worksheet)
    if ws.owner == g.username:
        W = ws
    else:
        W = g.notebook.copy_wst(worksheet, g.username)
        W.name = worksheet.name

    return redirect(url_for_worksheet(W))


########################################################
# Collaborate with others
########################################################
@worksheet_command('share')
def worksheet_share(worksheet):
    return html_share(worksheet, g.username)


@worksheet_command('invite_collab')
def worksheet_invite_collab(worksheet):
    user_manager = g.notebook.user_manager
    owner = worksheet.owner
    id_number = worksheet.id_number
    old_collaborators = set(worksheet.collaborators)
    collaborators = (u.strip() for u in request.values.get(
        'collaborators', '').split(','))
    collaborators = set(u for u in collaborators
                        if u in user_manager and u != owner)

    if len(collaborators - old_collaborators) > 500:
        # to prevent abuse, you can't add more than 500 collaborators at a time
        return message_template(
            _("Error: can't add more than 500 collaborators at a time"),
            cont=url_for_worksheet(worksheet),
            username=g.username)
    worksheet.collaborators = collaborators
    # add worksheet to new collaborators
    for u in collaborators - old_collaborators:
        try:
            user_manager[u].viewable_worksheets.add((owner, id_number))
        except KeyError:
            # user doesn't exist
            pass
    # remove worksheet from ex-collaborators
    for u in old_collaborators - collaborators:
        try:
            user_manager[u].viewable_worksheets.discard(
                (owner, id_number))
        except KeyError:
            # user doesn't exist
            pass

    return redirect(url_for_worksheet(worksheet))

########################################################
# Revisions
########################################################


@worksheet_command('revisions')
def worksheet_revisions(worksheet):
    """
    Show a list of revisions of this worksheet.
    """
    if 'action' not in request.values:
        if 'rev' in request.values:
            return html_specific_revision(g.username, worksheet,
                                          request.values['rev'])
        else:
            return html_worksheet_revision_list(g.username, worksheet)
    else:
        rev = request.values['rev']
        action = request.values['action']
        if action == 'revert':
            worksheet.save_snapshot(g.username)
            # XXX: Requires access to filesystem
            txt = bz2.decompress(
                open(worksheet.snapshot_filename(rev)).read())
            worksheet.delete_cells_directory()
            worksheet.edit_save(txt)
            return redirect(url_for_worksheet(worksheet))
        elif action == 'publish':
            W = g.notebook.publish_wst(worksheet, g.username)
            txt = bz2.decompress(
                open(worksheet.snapshot_filename(rev)).read())
            W.delete_cells_directory()
            W.edit_save(txt)
            return redirect(url_for_worksheet(W))
        else:
            return message_template(_('Error'), username=g.username)


########################################################
# Cell directories
########################################################
@worksheet_command('cells/<path:filename>')
def worksheet_cells(worksheet, filename):
    # XXX: This requires that the worker filesystem be accessible from
    # the server.
    return send_from_directory(worksheet.cells_directory, filename)


########################################################
# Jmol/JSmol callback to read data files
########################################################
@worksheet_command('jsmol')
def worksheet_jsmol_data(worksheet):
    """
    Jmol/JSmol callback

    The jmol applet does not take the data inline, but calls back at
    this URI to get one or more base64-encoded data files.
    """
    # Defaults taken from upstream jsmol.php
    query = request.values.get(
        'query',
        "http://cactus.nci.nih.gov/chemical/structure/ethanol/"
        "file?format=sdf&get3d=True")
    call = request.values.get('call', u'getRawDataFromDatabase')
    encoding = request.values.get('encoding', None)

    current_app.logger.debug('JSmol call:  %s', call)
    current_app.logger.debug('JSmol query: %s', query)
    if encoding is None:
        def encoder(x):
            return x
    elif encoding == u'base64':
        def encoder(x):
            # JSmol expects the magic ';base64,' in front of output
            return ';base64,' + base64.encodestring(x)
    else:
        current_app.logger.error('Invalid JSmol encoding %s', encoding)
        return message_template(_('Invalid JSmol encoding: ' + str(encoding)),
                                username=g.username)

    if call == u'getRawDataFromDatabase':
        # Annoyingly, JMol prepends the worksheet url (not: the
        # request url) to the query. Strip off:
        worksheet_url = request.base_url[:-len('/jsmol')]
        pattern = worksheet_url + '/cells/(?P<cell_id>[0-9]*)/(?P<filename>.*)'
        match = re.match(pattern, query)
        if match is None:
            current_app.logger.error(
                'Invalid JSmol query %s, does not match %s', query, pattern)
            return message_template(_('Invalid JSmol query: ' + query),
                                    username=g.username)
        cell_id = match.group('cell_id')
        filename = match.group('filename')
        # appended query is only for cache busting
        filename = filename.rsplit('?', 1)[0]
        filename = secure_filename(filename)   # never trust input
        filename = os.path.join(worksheet.cells_directory, cell_id, filename)
        with open(filename, 'r') as f:
            data = f.read()
            response = make_response(encoder(data))
    else:
        current_app.logger.error('Invalid JSmol request %s', call)
        return message_template(_('Invalid JSmol request: ' + str(call)),
                                username=g.username)

    # Taken from upstream jsmol.php
    is_binary = '.gz' in query
    # Non-standard Content-Type taken from upstream jsmol.php
    if is_binary:
        response.headers['Content-Type'] = (
            'Content-Type: text/plain; charset=x-user-defined')
    else:
        response.headers['Content-Type'] = 'Content-Type: application/json'
    return response


##############################################
# Data
##############################################
@worksheet_command('<path:filename>')
def worksheet_data_legacy(worksheet, filename):
    # adhering to old behavior, should be removed eventually
    return worksheet_data(worksheet, filename)


@worksheet_command('data/<path:filename>')
def worksheed_data_folder(worksheet, filename):
    # preferred way of accessing data
    return worksheet_data(worksheet, filename)


def worksheet_data(worksheet, filename):
    dir = os.path.abspath(worksheet.data_directory)
    if not os.path.exists(dir):
        return message_template(_('No data files'), username=g.username)
    else:
        return send_from_directory(worksheet.data_directory, filename)


@worksheet_command('datafile')
def worksheet_datafile(worksheet):
    # XXX: This requires that the worker filesystem be accessible from
    # the server.
    dir = os.path.abspath(worksheet.data_directory)
    filename = request.values['name']
    if request.values.get('action', '') == 'delete':
        path = os.path.join(dir, filename)
        os.unlink(path)
        return message_template(
            _("Successfully deleted '%(filename)s'", filename=filename),
            cont=url_for_worksheet(worksheet), username=g.username)
    else:
        return html_download_or_delete_datafile(
            worksheet, g.username, filename)


@worksheet_command('savedatafile')
def worksheet_savedatafile(worksheet):
    filename = request.values['filename']
    if 'button_save' in request.values:
        # XXX: Should this be text_field
        text_field = request.values['textfield']
        # XXX: Requires access to filesystem
        dest = os.path.join(worksheet.data_directory, filename)
        if os.path.exists(dest):
            os.unlink(dest)
        open(dest, 'w').write(text_field)
    return html_download_or_delete_datafile(
        worksheet, g.username, filename)


@worksheet_command('link_datafile')
def worksheet_link_datafile(worksheet):
    target_worksheet_filename = request.values['target']
    data_filename = request.values['filename']
    src = os.path.abspath(os.path.join(
        worksheet.data_directory, data_filename))
    target_ws = g.notebook.filename_wst(
        target_worksheet_filename)
    target = os.path.abspath(os.path.join(
        target_ws.data_directory, data_filename))
    if (target_ws.owner != g.username and
            g.username not in target_ws.collaborators):
        return message_template(
            _("illegal link attempt!"),
            worksheet_datafile.url_for(worksheet, name=data_filename),
            username=g.username)
    if os.path.exists(target):
        return message_template(
            _("The data filename already exists in other worksheet\nDelete "
              "the file in the other worksheet before creating a link."),
            worksheet_datafile.url_for(worksheet, name=data_filename),
            username=g.username)
    os.link(src, target)
    return redirect(worksheet_datafile.url_for(worksheet, name=data_filename))
    # return redirect(url_for_worksheet(target_ws) +
    # '/datafile?name=%s'%data_filename) #XXX: Can we not hardcode this?


@worksheet_command('upload_data')
def worksheet_upload_data(worksheet):
    return html_upload_data_window(worksheet, g.username)


@worksheet_command('do_upload_data')
def worksheet_do_upload_data(worksheet):
    worksheet_url = url_for_worksheet(worksheet)
    upload_url = worksheet_upload_data.url_for(worksheet)

    backlinks = _(
        ' Return to <a href="%(upload_url)s" title="Upload or create a data '
        'file in a wide range of formats"><strong>Upload or Create Data '
        'File</strong></a> or <a href="%(worksheet_url)s" '
        'title="Interactively use the '
        'worksheet"><strong>%(worksheet_name)s</strong></a>.',
        upload_url=upload_url,
        worksheet_url=worksheet_url,
        worksheet_name=worksheet.name)

    if 'file' not in request.files:
        return message_template(
            _('Error uploading file (missing field "file"). %(backlinks)s',
                backlinks=backlinks), worksheet_url, username=g.username)
    else:
        file = request.files['file']

    text_fields = ['url', 'new', 'name']
    for field in text_fields:
        if field not in request.values:
            return message_template(
                _('Error uploading file (missing %(field)s arg).%(backlinks)s',
                    field=field, backlinks=backlinks),
                worksheet_url, username=g.username)

    name = request.values.get('name', '').strip()
    new_field = request.values.get('new', '').strip()
    url = request.values.get('url', '').strip()

    name = name or file.filename or new_field
    if url and not name:
        name = url.split('/')[-1]
    name = secure_filename(name)

    if not name:
        return message_template(
            _('Error uploading file (missing filename).%(backlinks)s',
                backlinks=backlinks), worksheet_url)

    if url != '':
        # we normalize the url by parsing it first
        parsedurl = urlparse(url)
        if not parsedurl[0] in ('http', 'https', 'ftp'):
            return message_template(
                _('URL must start with http, https, or ftp.%(backlinks)s',
                    backlinks=backlinks), worksheet_url, username=g.username)
        download = urllib2.urlopen(parsedurl.geturl())

    # XXX: disk access
    dest = os.path.join(worksheet.data_directory, name)
    if os.path.exists(dest):
        if not os.path.isfile(dest):
            return message_template(
                _('Suspicious filename "%(filename)s" encountered uploading '
                  'file.%(backlinks)s',
                  filename=name, backlinks=backlinks),
                worksheet_url,
                username=g.username)
        os.unlink(dest)

    response = redirect(worksheet_datafile.url_for(worksheet, name=name))

    matches = re.match("file://(?:localhost)?(/.+)", url)
    if matches:
        f = file(dest, 'wb')
        f.write(open(matches.group(1)).read())
        f.close()
        return response

    elif url != '':
        with open(dest, 'w') as f:
            f.write(download.read())
        return response
    elif new_field:
        open(dest, 'w').close()
        return response
    else:
        file.save(dest)
        return response

################################
# Publishing
################################


@worksheet_command('publish')
def worksheet_publish(worksheet):
    """
    This provides a frontend to the management of worksheet
    publication. This management functionality includes
    initializational of publication, re-publication, automated
    publication when a worksheet saved, and ending of publication.
    """
    # Publishes worksheet and also sets worksheet to be published
    # automatically when saved
    nb = g.notebook
    if 'yes' in request.values and 'auto' in request.values:
        nb.publish_wst(worksheet, g.username)
        worksheet.auto_publish = True
        return redirect(worksheet_publish.url_for(worksheet))
    # Just publishes worksheet
    elif 'yes' in request.values:
        nb.publish_wst(worksheet, g.username)
        return redirect(worksheet_publish.url_for(worksheet))
    # Stops publication of worksheet
    elif 'stop' in request.values:
        nb.unpublish_wst(worksheet)
        return redirect(worksheet_publish.url_for(worksheet))
    # Re-publishes worksheet
    elif 're' in request.values:
        nb.publish_wst(worksheet, g.username)
        return redirect(worksheet_publish.url_for(worksheet))
    # Sets worksheet to be published automatically when saved
    elif 'auto' in request.values:
        worksheet.auto_publish = not worksheet.auto_publish
        return redirect(worksheet_publish.url_for(worksheet))
    # Returns boolean of "Is this worksheet set to be published automatically
    # when saved?"
    elif 'is_auto' in request.values:
        return str(worksheet.auto_publish)
    # Returns the publication page
    else:
        # Page for when worksheet already published
        if worksheet.published_id_number is not None:
            hostname = request.headers.get(
                'host', nb.interface + ':' + str(nb.port))

            # XXX: We shouldn't hardcode this.
            addr = 'http%s://%s/home/%s' % (
                '' if not nb.secure else 's',
                hostname,
                worksheet.published_filename)
            dtime = nb.filename_wst(worksheet.published_filename).date_edited
            return html_afterpublish_window(
                worksheet, g.username, addr, dtime)
        # Page for when worksheet is not already published
        else:
            return html_beforepublish_window(worksheet, g.username)

############################################
# Ratings
############################################


@worksheet_command('rating_info')
def worksheet_rating_info(worksheet):
    return html_ratings_info(worksheet)


@worksheet_command('rate')
def worksheet_rate(worksheet):
    # if user_type(self.username) == "guest":
    # return HTMLResponse(stream = message(
    # 'You must <a href="/">login first</a> in order to rate this worksheet.',
    # ret))

    rating = int(request.values['rating'])
    if rating < 0 or rating >= 5:
        return message_template(
            _("Gees -- You can't fool the rating system that easily!"),
            url_for_worksheet(worksheet), username=g.username)

    comment = request.values['comment']
    worksheet.rate(rating, comment, g.username)
    s = _("""
    Thank you for rating the worksheet <b><i>%(worksheet_name)s</i></b>!
    You can <a href="rating_info">see all ratings of this worksheet.</a>
    """, worksheet_name=worksheet.name)
    # XXX: Hardcoded url
    return message_template(s.strip(), '/pub/', title=_('Rating Accepted'),
                            username=g.username)


########################################################
# Downloading, moving around, renaming, etc.
########################################################
@worksheet_command('download/<path:title>')
def worksheet_download(worksheet, title):
    return unconditional_download(worksheet, title)


def unconditional_download(worksheet, title):
    filename = tmp_filename() + '.sws'

    if title.endswith('.sws'):
        title = title[:-4]

    try:
        # XXX: Accessing the hard disk.
        g.notebook.export_wst(worksheet.filename, filename, title)
    except KeyError:
        return message_template(_('No such worksheet.'))

    return send_file(filename, mimetype='application/sage')


@worksheet_command('restart_sage')
def worksheet_restart_sage(worksheet):
    # XXX: TODO -- this must not block long (!)
    worksheet.restart_sage()
    return 'done'


@worksheet_command('quit_sage')
def worksheet_quit_sage(worksheet):
    # XXX: TODO -- this must not block long (!)
    worksheet.quit()
    return 'done'


@worksheet_command('interrupt')
def worksheet_interrupt(worksheet):
    # XXX: TODO -- this must not block long (!)
    worksheet.sage().interrupt()
    return 'failed' if worksheet.sage().is_computing() else 'success'


@worksheet_command('hide_all')
def worksheet_hide_all(worksheet):
    worksheet.hide_all()
    return 'success'


@worksheet_command('show_all')
def worksheet_show_all(worksheet):
    worksheet.show_all()
    return 'success'


@worksheet_command('delete_all_output')
def worksheet_delete_all_output(worksheet):
    try:
        worksheet.delete_all_output(g.username)
    except ValueError:
        return 'fail'
    else:
        return 'success'


@worksheet_command('print')
def worksheet_print(worksheet):
    # XXX: We might want to separate the printing template from the
    # regular html template.
    return render_ws_template(ws=worksheet, do_print=True)


#######################################################
# Live "docbrowser" worksheets from HTML documentation
#######################################################
doc_worksheet_number = -1


def doc_worksheet():
    global doc_worksheet_number
    doc_worksheet_number = doc_worksheet_number % g.notebook.conf[
        'doc_pool_size']
    W = None
    for X in g.notebook.user_wsts(UN_SAGE):
        if X.compute_process_has_been_started():
            continue
        if X.id_number == doc_worksheet_number:
            W = X
            W.clear()
            break

    if W is None:
        # The first argument here is the worksheet's title, which the
        # caller should set with W.set_name.
        W = g.notebook.create_wst('', UN_SAGE)
    return W


def extract_title(html_page):
    # XXX: This might be better as a regex
    h = html_page.lower()
    i = h.find('<title>')
    if i == -1:
        return gettext("Untitled")
    j = h.find('</title>')
    return html_page[i + len('<title>'): j]


@login_required
def worksheet_file(path):
    # Create a live Sage worksheet from the given path.
    if not os.path.exists(path):
        return message_template(_('Document does not exist.'),
                                username=g.username)

    doc_page_html = open(path).read()
    doc_page = SphinxHTMLProcessor().process_doc_html(doc_page_html)

    title = (extract_title(doc_page_html).replace('&mdash;', '--') or
             'Live Sage Documentation')

    W = doc_worksheet()
    W.edit_save(doc_page)
    W.system = 'sage'
    W.name = title
    W.save()
    W.quit()

    # FIXME: For some reason, an extra cell gets added so we
    # remove it here.
    W.cells.pop()

    return render_ws_template(ws=W, username=g.username)
