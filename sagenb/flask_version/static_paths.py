# (c) 2015 J Miguel Farto, jmfarto@gmail.com
r'''
Aditional static paths
'''
from __future__ import absolute_import

import os

from flask import Blueprint
from flask import current_app as app
from flask.helpers import send_from_directory


static_paths = Blueprint('static_paths', __name__)


# TODO: sage dependency
SAGE_ROOT = os.environ['SAGE_ROOT']
SAGE_ROOT_SHARE = os.path.join(SAGE_ROOT, 'local', 'share')

JMOL = os.path.join(SAGE_ROOT_SHARE, 'jmol')
JSMOL = os.path.join(SAGE_ROOT_SHARE, 'jsmol')
J2S = os.path.join(JSMOL, 'j2s')

@static_paths.route('/css/<path:filename>')
def css(filename):
    # send_static file secures filename
    return app.send_static_file(os.path.join('sage', 'css', filename))


@static_paths.route('/images/<path:filename>')
def images(filename):
    # send_static file secures filename
    return app.send_static_file(os.path.join('sage', 'images', filename))


@static_paths.route('/javascript/<path:filename>')
@static_paths.route('/java/<path:filename>')
def static_file(filename):
    return app.send_static_file(filename)


@static_paths.route('/java/jmol/<path:filename>')
def jmol(filename):
    return send_from_directory(JMOL, filename)


@static_paths.route('/jsmol/<path:filename>')
def jsmol(filename):
    return send_from_directory(JSMOL, filename)


@static_paths.route('/j2s/<path:filename>')
def j2s(filename):
    return send_from_directory(J2S, filename)
