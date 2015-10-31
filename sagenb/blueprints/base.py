#!/usr/bin/env python
from __future__ import absolute_import

import mimetypes
import os
import re
import time
from hashlib import sha1

from flask import Blueprint
from flask import url_for
from flask import request
from flask import session
from flask import redirect
from flask import g
from flask import make_response
from flask import current_app
from flask.ext.openid import OpenID
from flask.ext.babel import gettext
from flask.ext.babel import get_locale

from ..misc.misc import mathjax_macros
from ..misc.misc import N_
from ..misc.misc import nN_
from ..misc.misc import SAGE_VERSION
from ..notebook.challenge import challenge
from ..notebook.js import javascript
from ..notebook.keyboards import get_keyboard
from ..notebook.misc import is_valid_username
from ..notebook.misc import is_valid_email
from ..notebook.misc import valid_username_chars
from ..notebook.themes import render_template
from ..notebook.tutorial import notebook_help
from ..notebook.user import User

from ..util.decorators import login_required
from ..util.decorators import guest_or_login_required
from ..util.decorators import with_lock
from .worksheet import url_for_worksheet

base = Blueprint('base', __name__)
# Globals
oid = OpenID()

mimetypes.add_type('text/plain','.jmol')

#############
# Main Page #
#############
@base.route('/')
def index():
    if 'username' in session:
        # If there is a next request use that.  See issue #76
        if 'next' in request.args:
            response = redirect(request.values.get('next', ''))
            return response
        response = redirect(url_for('worksheet_listing.home', username=session['username']))
        if 'remember' in request.args:
            response.set_cookie('nb_session_%s'%g.notebook.port,
                                expires=(time.time() + 60 * 60 * 24 * 14))
        else:
            response.set_cookie('nb_session_%s'%g.notebook.port)
        response.set_cookie('cookie_test_%s'%g.notebook.port, expires=1)
        return response


    if current_app.startup_token is not None and 'startup_token' in request.args:
        if request.args['startup_token'] == current_app.startup_token:
            g.username = session['username'] = 'admin'
            session.modified = True
            current_app.startup_token = None
            return redirect(url_for('base.index'))

    return redirect(url_for('authentication.login'))

######################
# Dynamic Javascript #
######################
@base.route('/javascript/dynamic/notebook_dynamic.js')
def dynamic_js():
    # the javascript() function is cached, so there shouldn't be a big slowdown calling it
    data,datahash = javascript()
    if request.environ.get('HTTP_IF_NONE_MATCH', None) == datahash:
        response = make_response('',304)
    else:
        response = make_response(data)
        response.headers['Content-Type'] = 'text/javascript; charset=utf-8'
        response.headers['Etag']=datahash
    return response

_localization_cache = {}
@base.route('/javascript/dynamic/localization.js')
def localization_js():
    global _localization_cache
    locale=repr(get_locale())
    if _localization_cache.get(locale,None) is None:
        data = render_template(os.path.join('js/localization.js'), N_=N_, nN_=nN_)
        _localization_cache[locale] = (data, sha1(repr(data)).hexdigest())
    data,datahash = _localization_cache[locale]

    if request.environ.get('HTTP_IF_NONE_MATCH', None) == datahash:
        response = make_response('',304)
    else:
        response = make_response(data)
        response.headers['Content-Type'] = 'text/javascript; charset=utf-8'
        response.headers['Etag']=datahash
    return response

_mathjax_js_cache = None
@base.route('/javascript/dynamic/mathjax_sage.js')
def mathjax_js():
    global _mathjax_js_cache
    if _mathjax_js_cache is None:
        data = render_template('js/mathjax_sage.js', theme_mathjax_macros=mathjax_macros)
        _mathjax_js_cache = (data, sha1(repr(data)).hexdigest())
    data,datahash = _mathjax_js_cache

    if request.environ.get('HTTP_IF_NONE_MATCH', None) == datahash:
        response = make_response('',304)
    else:
        response = make_response(data)
        response.headers['Content-Type'] = 'text/javascript; charset=utf-8'
        response.headers['Etag']=datahash
    return response

@base.route('/javascript/dynamic/keyboard/<browser_os>')
def keyboard_js(browser_os):
    data = get_keyboard(browser_os)
    datahash=sha1(data).hexdigest()
    if request.environ.get('HTTP_IF_NONE_MATCH', None) == datahash:
        response = make_response('',304)
    else:
        response = make_response(data)
        response.headers['Content-Type'] = 'text/javascript; charset=utf-8'
        response.headers['Etag']=datahash
    return response

########
# Help #
########
@base.route('/help')
@login_required
def help():
    return render_template(
      os.path.join('html', 'docs.html'), username = g.username,
      notebook_help = notebook_help, sage_version=SAGE_VERSION)

###########
# History #
###########
@base.route('/history')
@login_required
def history():
    return render_template(os.path.join('html', 'history.html'), username = g.username,
                           text = g.notebook.user_history_text(g.username), actions = False)

@base.route('/live_history')
@login_required
def live_history():
    W = g.notebook.create_new_worksheet_from_history(gettext('Log'), g.username, 100)
    return redirect(url_for_worksheet(W))

@base.route('/loginoid', methods=['POST', 'GET'])
@guest_or_login_required
@oid.loginhandler
def loginoid():
    if not g.notebook.conf()['openid']:
        return redirect(url_for('base.index'))
    if g.username != 'guest':
        return redirect(request.values.get('next', url_for('base.index')))
    if request.method == 'POST':
        openid = request.form.get('url')
        if openid:
            return oid.try_login(openid, ask_for=['email', 'fullname', 'nickname'])
    return redirect(url_for('authentication.login'))
    #render_template('html/login.html', next=oid.get_next_url(), error=oid.fetch_error())

@oid.after_login
@with_lock
def create_or_login(resp):
    if not g.notebook.conf()['openid']:
        return redirect(url_for('base.index'))
    try:
        username = g.notebook.user_manager().get_username_from_openid(resp.identity_url)
        session['username'] = g.username = username
        session.modified = True
    except (KeyError, LookupError):
        session['openid_response'] = resp
        session.modified = True
        return redirect(url_for('set_profiles'))
    return redirect(request.values.get('next', url_for('base.index')))

@base.route('/openid_profiles', methods=['POST','GET'])
def set_profiles():
    if not g.notebook.conf()['openid']:
        return redirect(url_for('base.index'))



    show_challenge=g.notebook.conf()['challenge']
    if show_challenge:
        chal = challenge(g.notebook.conf(),
                         is_secure = g.notebook.secure,
                         remote_ip = request.environ['REMOTE_ADDR'])

    if request.method == 'GET':
        if 'openid_response' in session:
            re_invalid_username_chars = re.compile('[^(%s)]' % valid_username_chars)
            openid_resp = session['openid_response']
            if openid_resp.fullname is not None:
                openid_resp.fullname = re.sub(re_invalid_username_chars, '_', openid_resp.fullname)
            template_dict={}
            if show_challenge:
                template_dict['challenge_html'] = chal.html()

            return render_template('html/accounts/openid_profile.html', resp=openid_resp,
                                   challenge=show_challenge, **template_dict)
        else:
            return redirect(url_for('base.index'))


    if request.method == 'POST':
        if 'openid_response' in session:
            parse_dict = {'resp':session['openid_response']}
        else:
            return redirect(url_for('base.index'))

        try:
            resp = session['openid_response']
            username = request.form.get('username')

            if show_challenge:
                parse_dict['challenge'] = True
                status = chal.is_valid_response(req_args = request.values)
                if status.is_valid is True:
                    pass
                elif status.is_valid is False:
                    err_code = status.error_code
                    if err_code:
                        parse_dict['challenge_html'] = chal.html(error_code = err_code)
                    else:
                        parse_dict['challenge_invalid'] = True
                    raise ValueError("Invalid challenge")
                else:
                    parse_dict['challenge_missing'] = True
                    raise ValueError("Missing challenge")

            if not is_valid_username(username):
                parse_dict['username_invalid'] = True
                raise ValueError("Invalid username")
            if g.notebook.user_manager().user_exists(username):
                parse_dict['username_taken'] = True
                raise ValueError("Pre-existing username")
            if not is_valid_email(request.form.get('email')):
                parse_dict['email_invalid'] = True
                raise ValueError("Invalid email")
            try:
                new_user = User(username, '', email = resp.email, account_type='user')
                g.notebook.user_manager().add_user_object(new_user)
            except ValueError as msg:
                parse_dict['creation_error'] = True
                raise ValueError("Error in creating user\n%s"%msg)
            g.notebook.user_manager().create_new_openid(resp.identity_url, username)
            session['username'] = g.username = username
            session.modified = True
        except ValueError:
            return render_template('html/accounts/openid_profile.html', **parse_dict)
        return redirect(url_for('base.index'))


