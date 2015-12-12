# -*- coding: utf-8 -*
"""nodoctest
"""
from __future__ import absolute_import

import copy

from flask.ext.babel import lazy_gettext

from ..config import TRANSLATIONS
from ..config import CHOICES
from ..config import DESC
from ..config import GROUP
from ..config import TYPE
from ..config import T_CHOICE

from .conf import Configuration

defaults = {'max_history_length': 1000,
            'default_system': 'sage',
            'autosave_interval': 60 * 60,   # 1 hour in seconds
            'default_pretty_print': False,
            'next_worksheet_id_number': -1,  # not yet initialized
            'language': 'default'
            }

defaults_descriptions = {
    'language': {
        DESC: lazy_gettext('Language'),
        GROUP: lazy_gettext('Appearance'),
        TYPE: T_CHOICE,
        CHOICES: ['default'] + TRANSLATIONS,
    },
}


def UserConfiguration_from_basic(basic):
    c = UserConfiguration()
    c.confs = copy.copy(basic)
    return c


class UserConfiguration(Configuration):

    def defaults(self):
        return defaults

    def defaults_descriptions(self):
        return defaults_descriptions
