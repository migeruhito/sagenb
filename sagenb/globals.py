from __future__ import absolute_import

import os
from babel import Locale
from babel.core import UnknownLocaleError
from pkg_resources import Requirement
from pkg_resources import resource_filename
from pkg_resources import working_set

from .util import sage_var  # if py3, from shutil import which
from .util import which  # if py3, from shutil import which
from .misc.misc import import_from


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


# sage paths
SAGE_ROOT = sage_var('SAGE_ROOT', _sage_root_fb)
SAGE_VERSION = sage_var('SAGE_VERSION', _sage_version_fb)
SAGE_DOC = sage_var('SAGE_DOC', _sage_doc_fb)
SAGE_SHARE = sage_var('SAGE_SHARE', _sage_share_fb)
SAGE_URL = 'http://sagemath.org'  # SAGE_URL is broken in sage.env (ver 6.8)
SAGE_SRC = sage_var('SAGE_SRC', _sage_src_fb)
DOT_SAGE = sage_var('DOT_SAGE', _dot_sage_fb)

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
