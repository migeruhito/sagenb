from __future__ import absolute_import

import os
import re
from babel import Locale
from babel.core import UnknownLocaleError
from pkg_resources import Requirement
from pkg_resources import resource_filename
from pkg_resources import working_set
from subprocess import check_output

from .util import import_from
from .util import sage_var  # if py3, from shutil import which
from .util import which  # if py3, from shutil import which


# Sage path fallbacks
def _sage_root_fb():
    path = which('sage')  # This works if sage_root is in PATH or if
    if path is not None:  # sage is a symlink of sage_root/sage
        return os.path.split(os.path.realpath(path))[0]


def _sage_version_fb():
    return re.findall(
        r'ersion\s*(.*),', check_output(['sage', '--version']))[0]


def _sage_doc_fb():
    return os.path.join(SAGE_ROOT, 'src', 'doc')


def _sage_share_fb():
    return os.path.join(SAGE_ROOT, 'local', 'share')


def _sage_src_fb():
    return os.path.join(SAGE_ROOT, 'src')


def _dot_sage_fb():
    return os.path.join(
        os.path.realpath(os.environ.get('HOME', '/tmp')), '.sage')


def _sage_browser_fb():
    """
    Set up default programs for opening web pages.

    INPUT:


    EXAMPLES::

        sage: from sagenb.config import _sage_browser_fb
        sage: _sage_browser_fb() # random -- depends on OS, etc.
        'sage-open'

    NOTE:
        Extracted from sage.misc.viewer.default_viewer
    """
    if os.uname()[0] == 'Darwin':
        browser = os.path.join(SAGE_ROOT, 'local', 'bin', 'sage-open')
    elif os.uname()[0][:6] == 'CYGWIN':
        # Bobby Moreti provided the following.
        if 'BROWSER' not in os.environ:
            browser = (
                '/cygdrive/{}/system32/rundll32.exe '
                'url.dll,FileProtocolHandler'.format(
                    os.environ['SYSTEMROOT'].replace(':', '/').replace('\\',
                                                                       '')))
        else:
            browser = os.environ['BROWSER']
    else:
        browser = which('xdg-open')

    if browser is None:
        # If all fails try to get something from the environment.
        try:
            browser = os.environ['BROWSER']
        except KeyError:
            browser = 'less'  # silly default
            for cmd in ['firefox', 'konqueror', 'mozilla', 'mozilla-firefox']:
                brows = which(cmd)
                if brows is not None:
                    browser = brows
                    break
    return browser


# sage paths
SAGE_ROOT = sage_var('SAGE_ROOT', _sage_root_fb)
SAGE_VERSION = sage_var('SAGE_VERSION', _sage_version_fb)
SAGE_DOC = sage_var('SAGE_DOC', _sage_doc_fb)
SAGE_SHARE = sage_var('SAGE_SHARE', _sage_share_fb)
SAGE_URL = 'http://sagemath.org'  # SAGE_URL is broken in sage.env (ver 6.8)
SAGE_SRC = sage_var('SAGE_SRC', _sage_src_fb)
DOT_SAGE = sage_var('DOT_SAGE', _dot_sage_fb)
SAGE_BROWSER = '{} {}'.format(
    os.path.join(SAGE_ROOT, 'local', 'bin', 'sage-native-execute'),
    sage_var('SAGE_BROWSER', _sage_browser_fb))

# sagenb paths
# TODO: This must be in sync with flask app base path. Should be removed from
# here
SAGENB_ROOT = resource_filename(__name__, '')
DOT_SAGENB = os.environ.get('DOT_SAGENB', DOT_SAGE)
try:
    SAGENB_VERSION = working_set.find(Requirement.parse('sagenb')).version
except AttributeError:
    SAGENB_VERSION = ''

# paths for static urls
SRC = os.path.join(SAGE_SRC, 'sage')
JMOL = os.path.join(SAGE_SHARE, 'jmol')
JSMOL = os.path.join(SAGE_SHARE, 'jsmol')
J2S = os.path.join(JSMOL, 'j2s')

# themes
system_themes_path = os.path.join(SAGENB_ROOT, 'themes')
user_themes_path = os.path.join(DOT_SAGENB, 'themes')
THEME_PATHS = [p for p in [system_themes_path, user_themes_path]
               if os.path.isdir(p)]
# TODO: Only needed by sagenb.notebook.server_conf
THEMES = []
for path in (tp for tp in THEME_PATHS if os.path.isdir(tp)):
    THEMES.extend([
        theme
        for theme in os.listdir(path)
        if os.path.isdir(os.path.join(path, theme))])
THEMES.sort()
DEFAULT_THEME = 'Default'
# TODO: dangerous. flask.ext.babel translations path is not configurable.
# This must be in sync with the hardcoded babel translation path. This
# should be removed when sagenb.notebook.server_conf, sagenb.notebook.user_conf
# be refactored.

# translations
TRANSLATIONS_PATH = os.path.join(SAGENB_ROOT, 'translations')
# TODO: Only needed by sagenb.notebook.server_conf, sagenb.notebook.user_conf
TRANSLATIONS = []
for name in (l for l in os.listdir(TRANSLATIONS_PATH) if l != 'en_US'):
    try:
        Locale.parse(name)
    except UnknownLocaleError:
        pass
    else:
        TRANSLATIONS.append(name)
TRANSLATIONS.sort()
TRANSLATIONS.insert(0, 'en_US')

# GUI settings
MATHJAX = True
JEDITABLE_TINYMCE = True

# password
min_password_length = 6

# TODO: Get macros from server and user settings.
mathjax_macros = import_from(
    'sage.misc.latex_macros', 'sage_mathjax_macros',
    default=lambda: lambda: [
        "ZZ : '{\\\\Bold{Z}}'",
        "NN : '{\\\\Bold{N}}'",
        "RR : '{\\\\Bold{R}}'",
        "CC : '{\\\\Bold{C}}'",
        "QQ : '{\\\\Bold{Q}}'",
        "QQbar : '{\\\\overline{\\\\QQ}}'",
        "GF : ['{\\\\Bold{F}_{#1}}', 1]",
        "Zp : ['{\\\\ZZ_{#1}}', 1]",
        "Qp : ['{\\\\QQ_{#1}}', 1]",
        "Zmod : ['{\\\\ZZ/#1\\\\ZZ}', 1]",
        "CIF : '{\\\\Bold{C}}'",
        "CLF : '{\\\\Bold{C}}'",
        "RDF : '{\\\\Bold{R}}'",
        "RIF : '{\\\\Bold{I} \\\\Bold{R}}'",
        "RLF : '{\\\\Bold{R}}'",
        "CFF : '{\\\\Bold{CFF}}'",
        "Bold : ['{\\\\mathbf{#1}}', 1]"])()

# Javascript keys
r"""
Notebook Keybindings

This module is responsible for setting the keyboard bindings for the notebook.

These are the standard key and mouse bindings available in the
notebook:

- *Evaluate Input:* Press **shift-enter**. You can start several calculations
  at once. If you press **alt-enter** instead, then a new cell is created after
  the current one. If you press **ctrl-enter** then the cell is split and both
  pieces are evaluated separately.

..

- *Tab Completion:* Press **tab** while the cursor is on an identifier. On some
  web browsers (e.g., Opera) you must use control-space instead of tab.

..

- *Insert New Cell:* Put the mouse between an output and input until the
  horizontal line appears and click. If you press Alt-Enter in a cell, the cell
  is evaluated and a new cell is inserted after it.

..

- *Delete Cell:* Delete all cell contents, then press **backspace**.

..

- *Split and Join Cells:* Press **ctrl-;** in a cell to split it into two
  cells, and **ctrl-backspace** to join them. Press **ctrl-enter** to split a
  cell and evaluate both pieces.

..

- *Insert New HTML Cell:* Shift click between cells to create a new HTML cell.
  Double click on existing HTML to edit it. Use \$...\$ and \$\$...\$\$ to
  include typeset math in the HTML block.

..

- *Hide/Show Output:* Click on the left side of output to toggle between
  hidden, shown with word wrap, and shown without word wrap.

..

- *Indenting Blocks:* Highlight text and press **>** to indent it all and **<**
  to unindent it all (works in Safari and Firefox). In Firefox you can also
  press tab and shift-tab.

..

- *Comment/Uncomment Blocks:* Highlight text and press **ctrl-.** to comment it
  and **ctrl-,** to uncomment it. Alternatively, use **ctrl-3** and **ctrl-4**.

..

- *Parenthesis matching:* To fix unmatched or mis-matched parentheses, braces
  or brackets, press **ctrl-0**.  Parentheses, brackets or braces to the left
  of or above the cursor will be matched, minding strings and comments.  Note,
  only Python comments are recognized, so this won\'t work for c-style
  multiline comments, etc.

"""
mod_ALT = 1
mod_CTRL = 2
mod_SHIFT = 4

KEYS = (
    ('request_introspections', 'KEY_SPC', 0 | mod_CTRL),
    ('request_introspections', 'KEY_TAB', 0),
    ('indent', 'KEY_TAB', 0),
    ('indent', 'KEY_GT', 0),
    ('unindent', 'KEY_TAB', 0 | mod_SHIFT),
    ('unindent', 'KEY_LT', 0),
    ('request_history', 'KEY_Q', 0 | mod_CTRL),
    ('request_history', 'KEY_QQ', 0 | mod_CTRL),
    ('request_log', 'KEY_P', 0 | mod_CTRL),
    ('request_log', 'KEY_PP', 0 | mod_CTRL),
    ('close_helper', 'KEY_ESC', 0),
    ('interrupt', 'KEY_ESC', 0),
    ('send_input', 'KEY_RETURN', 0 | mod_SHIFT),
    ('send_input', 'KEY_ENTER', 0 | mod_SHIFT),
    ('send_input_newcell', 'KEY_RETURN', 0 | mod_ALT),
    ('send_input_newcell', 'KEY_ENTER', 0 | mod_ALT),
    ('prev_cell', 'KEY_UP', 0 | mod_CTRL),
    ('next_cell', 'KEY_DOWN', 0 | mod_CTRL),
    ('page_up', 'KEY_PGUP', 0),
    ('page_down', 'KEY_PGDN', 0),
    ('delete_cell', 'KEY_BKSPC', 0),
    ('generic_submit', 'KEY_ENTER', 0),
    ('up_arrow', 'KEY_UP', 0),
    ('down_arrow', 'KEY_DOWN', 0),
    ('comment', 'KEY_DOT', 0 | mod_CTRL),
    ('comment', 'KEY_3', 0 | mod_CTRL),
    ('uncomment', 'KEY_COMMA', 0 | mod_CTRL),
    ('uncomment', 'KEY_4', 0 | mod_CTRL),
    ('fix_paren', 'KEY_0', 0 | mod_CTRL),

    ('control', 'KEY_CTRL', 0),
    ('backspace', 'KEY_BKSPC', 0),
    ('enter', 'KEY_ENTER', 0),
    ('enter', 'KEY_RETURN', 0),
    ('enter_shift', 'KEY_ENTER', 0 | mod_SHIFT),
    ('enter_shift', 'KEY_RETURN', 0 | mod_SHIFT),
    ('spliteval_cell', 'KEY_ENTER', 0 | mod_CTRL),
    ('spliteval_cell', 'KEY_RETURN', 0 | mod_CTRL),
    # needed on OS X Firefox
    ('spliteval_cell', 'KEY_CTRLENTER', 0 | mod_CTRL),
    ('join_cell', 'KEY_BKSPC', 0 | mod_CTRL),
    ('split_cell', 'KEY_SEMI', 0 | mod_CTRL),
    ('split_cell_noctrl', 'KEY_SEMI', 0),

    ('menu_left', 'KEY_LEFT', 0),
    ('menu_up', 'KEY_UP', 0),
    ('menu_right', 'KEY_RIGHT', 0),
    ('menu_down', 'KEY_DOWN', 0),
    ('menu_pick', 'KEY_ENTER', 0),
    ('menu_pick', 'KEY_RETURN', 0),
)

# 8  -- backspace
# 9  -- tab
# 13 -- return
# 27 -- esc
# 32 -- space
# 37 -- left
# 38 -- up
# 39 -- right
# 40 -- down
