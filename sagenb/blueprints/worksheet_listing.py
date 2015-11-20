"""
"""
from __future__ import absolute_import

import json
import os
import re
import shutil
import urllib
import urlparse
import zipfile
from HTMLParser import HTMLParser
from HTMLParser import HTMLParseError

from flask import current_app
from flask import g
from flask import Blueprint
from flask import redirect
from flask import request
from flask import url_for
from flask.ext.babel import gettext
from jinja2.exceptions import TemplateNotFound
from werkzeug.utils import secure_filename

from ..config import SAGE_VERSION
from ..misc.misc import unicode_str
from ..misc.misc import tmp_filename
from ..misc.misc import walltime
from ..notebook.misc import encode_response
from ..notebook.themes import render_template


from ..util import templates
from ..util.decorators import login_required
from ..util.decorators import guest_or_login_required
from .worksheet import url_for_worksheet

# Globals
_ = gettext
worksheet_listing = Blueprint('worksheet_listing', __name__)


def render_worksheet_list(args, pub, username):
    """
    Returns a rendered worksheet listing.

    INPUT:

    -  ``args`` - ctx.args where ctx is the dict passed
       into a resource's render method

    -  ``pub`` - boolean, True if this is a listing of
       public worksheets

    -  ``username`` - the user whose worksheets we are
       listing

    OUTPUT:

    a string
    """
    typ = args['typ'] if 'typ' in args else 'active'
    search = unicode_str(args['search']) if 'search' in args else None
    sort = args['sort'] if 'sort' in args else 'last_edited'
    reverse = (args['reverse'] == 'True') if 'reverse' in args else False
    readonly = g.notebook.readonly_user(g.username)
    try:
        if not pub:
            worksheets = g.notebook.worksheet_list_for_user(
                username, typ=typ, sort=sort, search=search, reverse=reverse)
        else:
            worksheets = g.notebook.worksheet_list_for_public(
                username, sort=sort, search=search, reverse=reverse)
    except ValueError as E:
        # for example, the sort key was not valid
        print "Error displaying worksheet listing: ", E
        return templates.message(_("Error displaying worksheet listing."))

    worksheet_filenames = [x.filename() for x in worksheets]

    if pub and (not username or username == tuple([])):
        username = 'pub'

    accounts = g.notebook.user_manager().get_accounts()
    sage_version = SAGE_VERSION
    return render_template('html/worksheet_listing.html', **locals())

# New UI


@worksheet_listing.route('/worksheet_list')
@guest_or_login_required
def worksheet_list():
    """
    Returns a worksheet listing.

    INPUT:

    -  ``args`` - ctx.args where ctx is the dict passed
       into a resource's render method

    -  ``pub`` - boolean, True if this is a listing of
       public worksheets

    -  ``username`` - the user whose worksheets we are
       listing

    OUTPUT:

    a string
    """
    r = {}

    pub = 'pub' in request.args
    g.notebook.readonly_user(g.username)
    typ = request.args['type'] if 'type' in request.args else 'active'
    search = unicode_str(
        request.args['search']) if 'search' in request.args else None
    sort = request.args['sort'] if 'sort' in request.args else 'last_edited'
    reverse = (request.args['reverse'] ==
               'True') if 'reverse' in request.args else False

    try:
        if not pub:
            r['worksheets'] = [
                x.basic() for x in g.notebook.worksheet_list_for_user(
                    g.username, typ=typ, sort=sort, search=search,
                    reverse=reverse)]
        else:
            r['worksheets'] = [
                x.basic() for x in g.notebook.worksheet_list_for_public(
                    g.username, sort=sort, search=search, reverse=reverse)]

    except ValueError as E:
        # for example, the sort key was not valid
        print "Error displaying worksheet listing: ", E
        return templates.message(_("Error displaying worksheet listing."))

    # if pub and (not g.username or g.username == tuple([])):
    #    r['username'] = 'pub'

    r['accounts'] = g.notebook.user_manager().get_accounts()
    r['sage_version'] = SAGE_VERSION
    # r['pub'] = pub

    return encode_response(r)
# New UI end


@worksheet_listing.route('/home/<username>/')
@login_required
def home(username):
    if not g.notebook.user_manager().user_is_admin(
            g.username) and username != g.username:
        return templates.message(_("User '%(user)s' does not have permission "
                                   "to view the home page of '%(name)s'.",
                                   user=g.username, name=username))
    else:
        try:
            # New UI
            return render_template('html/worksheet_list.html')
        except TemplateNotFound:
            # New UI end
            return render_worksheet_list(
                request.args, pub=False, username=username)


@worksheet_listing.route('/home/')
@login_required
def bare_home():
    return redirect(url_for('home', username=g.username))

###########
# Folders #
###########


def get_worksheets_from_request():
    # TODO: Is this neccessary?
    g.notebook.user_manager().user(g.username)

    if 'filename' in request.form:
        filenames = [request.form['filename']]
    elif 'filenames' in request.form:
        filenames = json.loads(request.form['filenames'])
    else:
        filenames = []
    worksheets = []
    for filename in filenames:
        W = g.notebook.get_worksheet_with_filename(filename)
        if W.owner() != g.username:
            # TODO BUG: if trying to stop a shared worksheet, this check means
            # that only the owner can stop from the worksheet listing (using
            # /send_to_stop), but any shared person can stop the worksheet by
            # quitting it.
            continue
        worksheets.append(W)

    return worksheets


@worksheet_listing.route('/send_to_trash', methods=['POST'])
@login_required
def send_worksheet_to_trash():
    for W in get_worksheets_from_request():
        W.move_to_trash(g.username)
    return ''


@worksheet_listing.route('/send_to_archive', methods=['POST'])
@login_required
def send_worksheet_to_archive():
    for W in get_worksheets_from_request():
        W.move_to_archive(g.username)
    return ''


@worksheet_listing.route('/send_to_active', methods=['POST'])
@login_required
def send_worksheet_to_active():
    for W in get_worksheets_from_request():
        W.set_active(g.username)
    return ''


@worksheet_listing.route('/send_to_stop', methods=['POST'])
@login_required
def send_worksheet_to_stop():
    for W in get_worksheets_from_request():
        W.quit()
    return ''


@worksheet_listing.route('/emptytrash', methods=['POST'])
@login_required
def empty_trash():
    g.notebook.empty_trash(g.username)
    if 'referer' in request.headers:
        return redirect(request.headers['referer'])
    else:
        return redirect(url_for('home', typ='trash'))


#####################
# Public Worksheets #
#####################
@worksheet_listing.route('/pub/')
@guest_or_login_required
def pub():
    return render_worksheet_list(request.args, pub=True, username=g.username)

#######################
# Download Worksheets #
#######################


@worksheet_listing.route('/download_worksheets.zip')
@login_required
def download_worksheets():
    t = walltime()
    print "Starting zipping a group of worksheets in a separate thread..."
    zip_filename = tmp_filename() + ".zip"

    # child
    worksheet_names = set()
    if 'filenames' in request.values:
        filenames = json.loads(request.values['filenames'])
        worksheets = [g.notebook.get_worksheet_with_filename(x.strip())
                      for x in filenames if len(x.strip()) > 0]
    else:
        worksheets = g.notebook.worksheet_list_for_user(g.username)

    zip = zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_STORED)
    for worksheet in worksheets:
        sws_filename = tmp_filename() + '.sws'
        g.notebook.export_worksheet(worksheet.filename(), sws_filename)
        entry_name = worksheet.name()
        if entry_name in worksheet_names:
            i = 2
            while ("%s_%s" % (entry_name, i)) in worksheet_names:
                i += 1
            entry_name = "%s_%s" % (entry_name, i)
        zip.write(sws_filename, entry_name + ".sws")
        os.unlink(sws_filename)
    zip.close()
    r = open(zip_filename, 'rb').read()
    os.unlink(zip_filename)
    print "Finished zipping %s worksheets (%s seconds)" % (
        len(worksheets), walltime(t))

    response = current_app.make_response(r)
    response.headers['Content-Type'] = 'application/zip'
    return response


#############
# Uploading #
#############
@worksheet_listing.route('/upload')
@login_required
def upload():
    if g.notebook.readonly_user(g.username):
        return templates.message(
            _("Account is in read-only mode"),
            cont=url_for('home', username=g.username))
    return render_template(os.path.join('html', 'upload.html'),
                           username=g.username, sage_version=SAGE_VERSION)


class RetrieveError(Exception):
    """
    Use this in my_urlretrieve below, and when calling that function, do:

    try:
        my_urlretrive(...)
    except RetrieveError as err:
        return templates.message(str(err))

    This allows us to factor out all the error message handling into
    my_urlretrieve.
    """
    pass


def my_urlretrieve(url, *args, **kwargs):
    """
    Call urllib.urlretrieve and give friendly error messages depending
    on the result. If successful, return exactly what urllib.urlretrieve
    would. Arguments are exactly the same as urlretrieve, except that
    you can also specify a ``backlinks`` keyword used in the error
    message.

    Raises RetrieveError when an error occurs for which we can figure
    out a sensible error message.
    """
    try:
        backlinks = kwargs.pop('backlinks')
    except KeyError:
        backlinks = ''
    try:
        return urllib.urlretrieve(url, *args, **kwargs)
    except IOError as err:
        if err.strerror == 'unknown url type' and err.filename == 'https':
            raise RetrieveError(
                _("This Sage notebook is not configured to load worksheets "
                  "from 'https' URLs. Try a different URL or download the "
                  "worksheet and upload it directly from your "
                  "computer.\n%(backlinks)s", backlinks=backlinks))
        else:
            raise


def parse_link_rel(url, fn):
    """
    Read through html file ``fn`` downloaded from ``url``, looking for a
    link tag of the form:

    <link rel="alternate"
          type="application/sage"
          title="currently ignored"
          href=".../example.sws" />

    This function reads ``fn`` looking for such tags and returns a list
    of dictionaries of the form

    {'title': from title field in link, 'url': absolute URL to .sws file}

    for the corresponding ``.sws`` files. Naturally if there are no
    appropriate link tags found, the returned list is empty. If the HTML
    parser raises an HTMLParseError, we simply return an empty list.
    """
    class GetLinkRelWorksheets(HTMLParser):

        def __init__(self):
            HTMLParser.__init__(self)
            self.worksheets = []

        def handle_starttag(self, tag, attrs):
            if (tag == 'link' and
                    ('rel', 'alternate') in attrs and
                    ('type', 'application/sage') in attrs):
                self.worksheets.append(
                    {'title': [_ for _ in attrs if _[0] == 'title'][0][1],
                     'url': [_ for _ in attrs if _[0] == 'href'][0][1]})

    parser = GetLinkRelWorksheets()
    with open(fn) as f:
        try:
            parser.feed(f.read())
        except HTMLParseError:
            return []

    ret = []
    for d in parser.worksheets:
        sws = d['url']
        # is that link a relative URL?
        if not urlparse.urlparse(sws).netloc:
            # unquote-then-quote to avoid turning %20 into %2520, etc
            ret.append(
                {'url': urlparse.urljoin(
                    url, urllib.quote(urllib.unquote(sws))),
                 'title': d['title']})
        else:
            ret.append({'url': sws, 'title': d['title']})
    return ret


@worksheet_listing.route('/upload_worksheet', methods=['GET', 'POST'])
@login_required
def upload_worksheet():
    # TODO: sage dependency
    from sage.misc.all import tmp_filename
    from sage.misc.all import tmp_dir

    if g.notebook.readonly_user(g.username):
        return templates.message(
            _("Account is in read-only mode"),
            cont=url_for('home', username=g.username))

    backlinks = _(
        'Return to <a href="/upload" title="Upload a worksheet">'
        '<strong>Upload File</strong></a>.')

    url = request.values['url'].strip()
    dir = ''
    if url != '':
        # Downloading a file from the internet
        # The file will be downloaded from the internet and saved
        # to a temporary file with the same extension
        path = urlparse.urlparse(url).path
        extension = os.path.splitext(path)[1].lower()
        if extension not in ["", ".txt", ".sws", ".zip", ".html", ".rst"]:
            # Or shall we try to import the document as an sws when in doubt?
            return templates.message(
                _("Unknown worksheet extension: %(ext)s. %(links)s",
                    ext=extension, links=backlinks))
        filename = tmp_filename() + extension
        try:
            matches = re.match("file://(?:localhost)?(/.+)", url)
            if matches:
                if g.notebook.interface != 'localhost':
                    return templates.message(
                        _("Unable to load file URL's when not running on "
                          "localhost.\n%(backlinks)s", backlinks=backlinks))

                shutil.copy(matches.group(1), filename)
            else:
                my_urlretrieve(url, filename, backlinks=backlinks)

        except RetrieveError as err:
            return templates.message(str(err))

    else:
        # Uploading a file from the user's computer
        dir = tmp_dir()
        file = request.files['file']
        if file.filename is None:
            return templates.message(
                _("Please specify a worksheet to load.\n%(backlinks)s",
                    backlinks=backlinks))

        filename = secure_filename(file.filename)
        if len(filename) == 0:
            return templates.message(
                _("Invalid filename.\n%(backlinks)s",
                    backlinks=backlinks))

        filename = os.path.join(dir, filename)
        file.save(filename)

    new_name = request.values.get('name', None)

    try:
        try:
            if filename.endswith('.zip'):
                # Extract all the .sws files from a zip file.
                zip_file = zipfile.ZipFile(filename)
                for subfilename in zip_file.namelist():
                    prefix, extension = os.path.splitext(subfilename)
                    # Mac zip files contain files like __MACOSX/._worksheet.sws
                    # which are metadata files, so we skip those as
                    # well as any other files we won't understand
                    if extension in [
                            '.sws',
                            '.html',
                            '.txt',
                            '.rst'] and not prefix.startswith('__MACOSX/'):
                        tmpfilename = os.path.join(dir, "tmp" + extension)
                        try:
                            tmpfilename = zip_file.extract(
                                subfilename, tmpfilename)
                        except AttributeError:
                            open(tmpfilename, 'w').write(
                                zip_file.read(subfilename))
                        W = g.notebook.import_worksheet(
                            tmpfilename, g.username)
                        if new_name:
                            W.set_name("%s - %s" % (new_name, W.name()))
                    else:
                        print("Unknown extension, file %s is "
                              "ignored" % subfilename)
                return redirect(url_for('home', username=g.username))

            else:
                if url and extension in ['', '.html']:
                    linked_sws = parse_link_rel(url, filename)
                    if linked_sws:
                        # just grab 1st URL; perhaps later add interface for
                        # downloading multiple linked .sws
                        try:
                            filename = my_urlretrieve(
                                linked_sws[0]['url'], backlinks=backlinks)[0]
                            print 'Importing {0}, linked to from {1}'.format(
                                linked_sws[0]['url'], url)
                        except RetrieveError as err:
                            return templates.message(str(err))
                W = g.notebook.import_worksheet(filename, g.username)
        except Exception, msg:
            print 'error uploading worksheet', msg
            s = _('There was an error uploading the worksheet.  It could be '
                  'an old unsupported format or worse.  If you desperately '
                  'need its contents contact the '
                  '<a href="http://groups.google.com/group/sage-support">'
                  'sage-support group</a> and post a link to your worksheet.  '
                  'Alternatively, an sws file is just a bzip2 tarball; take a '
                  'look inside!\n%(backlinks)s', backlinks=backlinks)
            return templates.message(s, url_for('home', username=g.username))
        finally:
            # Clean up the temporarily uploaded filename.
            os.unlink(filename)
            # if a temp directory was created, we delete it now.
            if dir:
                shutil.rmtree(dir)

    except ValueError, msg:
        s = _("Error uploading worksheet '%(msg)s'.%(backlinks)s",
              msg=msg, backlinks=backlinks)
        return templates.message(s, url_for('home', username=g.username))

    if new_name:
        W.set_name(new_name)

    return redirect(url_for_worksheet(W))
