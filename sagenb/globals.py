from __future__ import absolute_import

import os
from babel import Locale
from babel.core import UnknownLocaleError
from pkg_resources import Requirement
from pkg_resources import resource_filename
from pkg_resources import working_set

from .misc.misc import import_from

# TODO: sage dependency
SAGE_ROOT = os.environ['SAGE_ROOT']
# TODO: sage dependency
SAGE_ROOT_SHARE = os.path.join(SAGE_ROOT, 'local', 'share')

# TODO: sage dependency
SAGE_VERSION = import_from('sage.version', 'version', default='')
# TODO: sage dependency
SAGE_URL = import_from('sage.env', 'SAGE_URL', default='http://sagemath.org')
# TODO: sage dependency
SAGE_DOC = import_from('sage.env', 'SAGE_DOC', default='')
# TODO: sage dependency
SAGE_SRC = import_from('sage.env', 'SAGE_SRC', default=os.environ.get(
    'SAGE_SRC', os.path.join(SAGE_ROOT, 'src')))
SRC = os.path.join(SAGE_SRC, 'sage')

# TODO: This must be in sync with flask app base path. Should be removed from
# here
SAGENB_ROOT = resource_filename(__name__, '')
try:
    DOT_SAGENB = os.environ['DOT_SAGENB']
except KeyError:
    try:
        DOT_SAGENB = os.environ['DOT_SAGE']
    except KeyError:
        DOT_SAGENB = os.path.join(os.environ['HOME'], '.sagenb')
try:
    SAGENB_VERSION = working_set.find(Requirement.parse('sagenb')).version
except AttributeError:
    SAGENB_VERSION = ''

# TODO: sage dependency
JMOL = os.path.join(SAGE_ROOT_SHARE, 'jmol')
# TODO: sage dependency
JSMOL = os.path.join(SAGE_ROOT_SHARE, 'jsmol')
# TODO: sage dependency
J2S = os.path.join(JSMOL, 'j2s')

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
