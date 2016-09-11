from __future__ import absolute_import
from __future__ import print_function
from __future__ import division
from __future__ import unicode_literals

import os
from babel import Locale
from babel.core import UnknownLocaleError
from pkg_resources import Requirement
from pkg_resources import resource_filename
from pkg_resources import working_set

from pexpect.exceptions import ExceptionPexpect
from flask_babel import lazy_gettext

from .sage_server.workers import sage
from .util import sage_browser

# Global variables across the application
# TODO: remove this. Previously in notebook.misc
notebook = None

try:
    sage_conf = sage()
except ExceptionPexpect:
    raise OSError('Install sage and ensure that "sage" is in system PATH')

sage_conf.execute('\n'.join((
    'from sage.env import SAGE_ENV',
    'from sage.misc.latex_macros import sage_mathjax_macros',
    '[',
    '    SAGE_ENV,',
    '    sage_mathjax_macros(),',
    '    {',
    '         "UPDATE_PREFIX": _interact_.INTERACT_UPDATE_PREFIX,',
    '         "RESTART": _interact_.INTERACT_RESTART,',
    '         "START": _interact_.INTERACT_START,',
    '         "TEXT": _interact_.INTERACT_TEXT,',
    '         "HTML": _interact_.INTERACT_HTML,',
    '         "END": _interact_.INTERACT_END,',
    '         },',
    ' ]',
    )))
while True:
    sconf = sage_conf.output_status()
    if sconf.done:
        break
sage_conf.quit()

exec('sage_conf = ' + sconf.output.strip())
SAGE_ENV, mathjax_macros, INTERACT_CONF = sage_conf


# sage paths
SAGE_ROOT = SAGE_ENV['SAGE_ROOT']
SAGE_DOC = SAGE_ENV['SAGE_DOC']
SAGE_SHARE = SAGE_ENV['SAGE_SHARE']
SAGE_SRC = SAGE_ENV['SAGE_SRC']
DOT_SAGE = SAGE_ENV['DOT_SAGE']
SAGE_VERSION = SAGE_ENV['SAGE_VERSION']

SAGE_URL = 'http://sagemath.org'  # SAGE_URL is broken in sage.env (ver <= 7.2)
SAGE_BROWSER = '{} {}'.format(
    os.path.join(SAGE_ROOT, 'local', 'bin', 'sage-native-execute'),
    sage_browser(SAGE_ROOT))

# Interact markers
INTERACT_UPDATE_PREFIX = INTERACT_CONF['UPDATE_PREFIX']
INTERACT_RESTART = INTERACT_CONF['RESTART']
INTERACT_START = INTERACT_CONF['START']
INTERACT_TEXT = INTERACT_CONF['TEXT']
INTERACT_HTML = INTERACT_CONF['HTML']
INTERACT_END = INTERACT_CONF['END']


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

# Gui config
CHOICES = 'choices'
DESC = 'desc'
GROUP = 'group'
POS = 'pos'
TYPE = 'type'

T_BOOL = 0
T_CHOICE = 2
T_COLOR = 4
T_INFO = 7
T_INTEGER = 1
T_LIST = 6
T_REAL = 3
T_STRING = 5

G_APPEARANCE = lazy_gettext('Appearance')
G_AUTH = lazy_gettext('Authentication')
G_LDAP = lazy_gettext('LDAP')
G_SERVER = lazy_gettext('Server')

POS_DEFAULT = 100

# Users Globals
SALT = 'aa'
# User Account Types
UAT_ADMIN = 'admin'
UAT_USER = 'user'
UAT_GUEST = 'guest'
# User Names
UN_ADMIN = 'admin'  # User name for default admin user
UN_GUEST = 'guest'
UN_PUB = 'pub'  # User name for published worksheets
UN_SAGE = '_sage_'  # User name for doc browser worksheets
UN_SYSTEM = (UN_GUEST, UN_SAGE, UN_PUB)

# Default worksheet tags
# Integers that define which folder this worksheet is in relative to a given
# user.
WS_ARCHIVED = 0
WS_ACTIVE = 1
WS_TRASH = 2

# Notebook globals
# [(string: name, bool: optional)]
SYSTEMS = (('sage', False),
           ('gap', False),
           ('gp', False),
           ('html', False),
           ('latex', False),
           ('maxima', False),
           ('python', False),
           ('r', False),
           ('sh', False),
           ('singular', False),
           ('axiom', True),
           ('fricas', True),
           ('kash', True),
           ('macaulay2', True),
           ('magma', True),
           ('maple', True,),
           ('mathematica', True),
           ('matlab', True),
           ('mupad', True),
           ('octave', True),
           ('scilab', True))


# Cell output control
# Maximum number of characters allowed in output.  This is needed
# avoid overloading web browser.  For example, it should be possible
# to gracefully survive:
#    while True:
#       print("hello world")
# On the other hand, we don't want to loose the output of big matrices
# and numbers, so don't make this too small.
MAX_OUTPUT = 32000
MAX_OUTPUT_LINES = 120
# Used to detect and format tracebacks.
# See :func:`.util.text.format_exception`.
TRACEBACK = 'Traceback (most recent call last):'

# Worksheet control
# Constants that control the behavior of the worksheet.
INITIAL_NUM_CELLS = 1  # number of empty cells in new worksheets
WARN_THRESHOLD = 100   # The number of seconds, so if there was no
# activity on this worksheet for this many
# seconds, then editing is considered safe.
# Used when multiple people are editing the
# same worksheet.

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
# TODO: dangerous. flask_babel translations path is not configurable.
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
# For pybabel
lazy_gettext('January')
lazy_gettext('February')
lazy_gettext('March')
lazy_gettext('April')
lazy_gettext('May')
lazy_gettext('June')
lazy_gettext('July')
lazy_gettext('August')
lazy_gettext('September')
lazy_gettext('October')
lazy_gettext('November')
lazy_gettext('December')

# GUI settings
MATHJAX = True
JEDITABLE_TINYMCE = True

# password
min_password_length = 6

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
