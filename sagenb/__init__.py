# -*- coding: utf-8 -*
from __future__ import absolute_import

import os

from cgi import escape
from json import dumps

from flask import Flask
from flask import g
from flask import url_for
# Make flask use the old session foo from <=flask-0.9
from flask.ext.oldsessions import OldSecureCookieSessionInterface
from flask.ext.autoindex import AutoIndex
from flask.ext.babel import Babel
from flask.ext.babel import gettext
from flask.ext.themes2 import Themes
from flask.ext.themes2 import theme_paths_loader

from .util import templates
from .util.decorators import guest_or_login_required
from .misc.misc import import_from
from .misc.misc import default_theme
from .misc.misc import theme_paths
from .misc.misc import unicode_str
from .notebook.template import css_escape
from .notebook.template import clean_name
from .notebook.template import prettify_time_ago
from .notebook.template import TEMPLATE_PATH
from .notebook.template import number_of_rows
from .notebook.themes import render_template

from .blueprints.base import oid

from .blueprints.admin import admin
from .blueprints.authentication import authentication
from .blueprints.base import base
from .blueprints.doc import doc
from .blueprints.settings import settings
from .blueprints.static_paths import static_paths
from .blueprints.worksheet_listing import worksheet_listing
from .blueprints.worksheet import worksheet


# TODO: sage dependency
SAGE_SRC = import_from('sage.env', 'SAGE_SRC', default=os.environ.get(
    'SAGE_SRC', os.path.join(os.environ['SAGE_ROOT'], 'devel', 'sage')))
SRC = os.path.join(SAGE_SRC, 'sage')

# CLEAN THIS UP!


def create_app(notebook, startup_token=None, debug=False):
    """
    This is the main method to create a running notebook. This is
    called from the process spawned in run.py
    """
    # Create app
    app = Flask('sagenb',
                static_folder='data', static_url_path='/static',
                template_folder=TEMPLATE_PATH)
    app.startup_token = startup_token
    app.session_interface = OldSecureCookieSessionInterface()

    app.config['SESSION_COOKIE_HTTPONLY'] = False
    app.config['PROPAGATE_EXCEPTIONS'] = debug
    app.config['DEBUG'] = debug

    # Template globals
    app.add_template_global(url_for)
    # Template filters
    app.add_template_filter(css_escape)
    app.add_template_filter(number_of_rows)
    app.add_template_filter(clean_name)
    app.add_template_filter(prettify_time_ago)
    app.add_template_filter(max)
    app.add_template_filter(lambda x: repr(unicode_str(x))[1:],
                            name='repr_str')
    app.add_template_filter(dumps, 'tojson')

    app.secret_key = os.urandom(24)
    oid.init_app(app)

    @app.before_request
    def set_notebook_object():
        g.notebook = notebook

    ####################################
    # create Babel translation manager #
    ####################################
    babel = Babel(app, default_locale='en_US')

    # Check if saved default language exists. If not fallback to default
    @app.before_first_request
    def check_default_lang():
        def_lang = notebook.conf()['default_language']
        trans_ids = [str(trans) for trans in babel.list_translations()]
        if def_lang not in trans_ids:
            notebook.conf()['default_language'] = None

    # register callback function for locale selection
    # this function must be modified to add per user language support
    @babel.localeselector
    def get_locale():
        return g.notebook.conf()['default_language']

    #################
    # Set up themes #
    #################
    # A new conf entry, 'themes', was added to notebook
    app.config['THEME_PATHS'] = theme_paths()
    app.config['DEFAULT_THEME'] = default_theme()
    Themes(app, loaders=[theme_paths_loader], app_identifier='sagenb')
    name = notebook.conf()['theme']
    if name not in app.theme_manager.themes:
        notebook.conf()['theme'] = app.config['DEFAULT_THEME']
    # app.theme_manager.refresh()

    ########################
    # Register the modules #
    ########################
    app.register_blueprint(doc, url_prefix='/doc')
    app.register_blueprint(static_paths)

    app.register_blueprint(base)
    app.register_blueprint(worksheet_listing)
    app.register_blueprint(admin)
    app.register_blueprint(authentication)
    app.register_blueprint(worksheet)
    app.register_blueprint(settings)

    # Handles all uncaught exceptions by sending an e-mail to the
    # administrator(s) and displaying an error page.
    @app.errorhandler(500)
    def log_exception(error):
        return templates.message(
            gettext('''500: Internal server error.'''),
            username=getattr(g, 'username', 'guest')), 500

    # autoindex v0.3 doesnt seem to work with modules
    # routing with app directly does the trick
    # TODO: Check to see if autoindex 0.4 works with modules
    idx = AutoIndex(app, browse_root=SRC, add_url_rules=False)

    @app.route('/src/')
    @app.route('/src/<path:path>')
    @guest_or_login_required
    def autoindex(path='.'):
        filename = os.path.join(SRC, path)
        if os.path.isfile(filename):
            src = escape(open(filename).read().decode('utf-8', 'ignore'))
            if (os.path.splitext(filename)[1] in
                    ['.py', '.c', '.cc', '.h', '.hh', '.pyx', '.pxd']):
                return render_template(os.path.join('html',
                                                    'source_code.html'),
                                       src_filename=path,
                                       src=src, username=g.username)
            return src
        return idx.render_autoindex(path)

    return app
