from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from builtins import range

import os
from random import choice
import string

from flask import Blueprint
from flask import url_for
from flask import request
from flask import session
from flask import redirect
from flask import g
from flask import current_app
from flask_babel import gettext

from ..config import SAGE_VERSION
from ..config import UN_SYSTEM
from ..util.auth import challenge
from ..util.auth import register_make_key
from ..util.auth import register_build_msg
from ..util.auth import register_build_password_msg
from ..util.mail import send_mail
from ..util.templates import message as message_template
from ..util.templates import render_template
from ..util.text import do_passwords_match
from ..util.text import is_valid_email
from ..util.text import is_valid_password
from ..util.text import is_valid_username

from ..util.decorators import with_lock

_ = gettext

authentication = Blueprint('authentication', __name__)

##################
# Authentication #
##################


@authentication.before_request
def lookup_current_user():
    g.username = None
    if 'username' in session:
        g.username = session['username']


@authentication.route('/login', methods=['POST', 'GET'])
def login(template_dict={}):
    nb_conf = g.notebook.conf
    template_dict.update({'accounts': nb_conf['accounts'],
                          'recovery': nb_conf['email'],
                          'next': request.values.get('next', ''),
                          'sage_version': SAGE_VERSION,
                          'openid': nb_conf['openid'],
                          'username_error': False,
                          'password_error': False})

    if request.method == 'POST':
        username = request.form['email']
        password = request.form['password']

        if username == 'COOKIESDISABLED':
            return _(r'Please enable cookies or delete all Sage cookies and '
                     'localhost cookies in your browser and try again.')

        # we only handle ascii usernames.
        if is_valid_username(username):
            try:
                U = g.notebook.user_manager[username]
            except KeyError:
                U = None
                template_dict['username_error'] = True
        else:
            U = None
            template_dict['username_error'] = True

        # It is critically important that it be impossible to login as the pub,
        # _sage_, or guest users.  This _sage_ user is a fake user that is used
        # internally by the notebook for the doc browser and other tasks.
        if username in UN_SYSTEM:
            U = None
            template_dict['username_error'] = True

        if U is None:
            pass
        elif (is_valid_password(password, username) and
              g.notebook.user_manager.check_password(username, password)):
            if U.is_suspended:
                # suspended
                return _("Your account is currently suspended")
            else:
                # Valid user, everything is okay
                session['username'] = username
                session.modified = True
                return redirect(
                    request.values.get('next', url_for('base.index')))
        else:
            template_dict['password_error'] = True

    response = current_app.make_response(
        render_template('html/login.html', **template_dict))
    response.set_cookie('cookie_test_%s' % g.notebook.port, 'cookie_test')
    return response


@authentication.route('/logout/')
def logout():
    username = session.pop('username', None)
    g.notebook.logout(username)
    return redirect(url_for('base.index'))


################
# Registration #
################

# XXX: Yuck!  This global variable should not be here.
# This is data should be stored somewhere more persistant.
waiting = {}


@authentication.route('/register', methods=['GET', 'POST'])
@with_lock
def register():
    if not g.notebook.conf['accounts']:
        return redirect(url_for('base.index'))

    # VALIDATORS: is_valid_username, is_valid_password,
    # do_passwords_match, is_valid_email,
    # challenge.is_valid_response
    # INPUT NAMES: username, password, retype_password, email +
    # challenge fields

    # TEMPLATE VARIABLES: error, username, username_missing,
    # username_taken, username_invalid, password_missing,
    # password_invalid, passwords_dont_match,
    # retype_password_missing, email, email_missing,
    # email_invalid, email_address, challenge, challenge_html,
    # challenge_missing, challenge_invalid

    # PRE-VALIDATION setup and hooks.
    required = set(['username', 'password'])
    empty = set()
    validated = set()

    # Template variables.  We use empty_form_dict for empty forms.
    empty_form_dict = {}
    template_dict = {}

    if g.notebook.conf['email']:
        required.add('email')
        empty_form_dict['email'] = True

    if g.notebook.conf['challenge']:
        required.add('challenge')
        empty_form_dict['challenge'] = True
        chal = challenge(g.notebook.conf,
                         is_secure=g.notebook.secure,
                         remote_ip=request.environ['REMOTE_ADDR'])
        empty_form_dict['challenge_html'] = chal.html()

    template_dict.update(empty_form_dict)

    # VALIDATE FIELDS.

    # Username.  Later, we check if a user with this username
    # already exists.
    username = request.values.get('username', None)
    if username:
        if not is_valid_username(username):
            template_dict['username_invalid'] = True
        elif username in g.notebook.user_manager:
            template_dict['username_taken'] = True
        else:
            template_dict['username'] = username
            validated.add('username')
    else:
        template_dict['username_missing'] = True
        empty.add('username')

    # Password.
    password = request.values.get('password', None)
    retype_password = request.values.get('retype_password', None)
    if password:
        if not is_valid_password(password, username):
            template_dict['password_invalid'] = True
        elif not do_passwords_match(password, retype_password):
            template_dict['passwords_dont_match'] = True
        else:
            validated.add('password')
    else:
        template_dict['password_missing'] = True
        empty.add('password')

    # Email address.
    email_address = ''
    if g.notebook.conf['email']:
        email_address = request.values.get('email', None)
        if email_address:
            if not is_valid_email(email_address):
                template_dict['email_invalid'] = True
            else:
                template_dict['email_address'] = email_address
                validated.add('email')
        else:
            template_dict['email_missing'] = True
            empty.add('email')

    # Challenge (e.g., reCAPTCHA).
    if g.notebook.conf['challenge']:
        status = chal.is_valid_response(req_args=request.values)
        if status.is_valid is True:
            validated.add('challenge')
        elif status.is_valid is False:
            err_code = status.error_code
            if err_code:
                template_dict['challenge_html'] = chal.html(
                    error_code=err_code)
            else:
                template_dict['challenge_invalid'] = True
        else:
            template_dict['challenge_missing'] = True
            empty.add('challenge')

    # VALIDATE OVERALL.
    if empty == required:
        # All required fields are empty.  Not really an error.
        return render_template(
            'html/accounts/registration.html', **empty_form_dict)
    elif validated != required:
        # Error(s)!
        errors = len(required) - len(validated)
        template_dict['error'] = 'E ' if errors == 1 else 'Es '
        return render_template(
            'html/accounts/registration.html', **template_dict)

    # Create an account.  All required fields should be valid.
    g.notebook.user_manager.add_user(username, password, email_address)

    # XXX: Add logging support
    # log.msg("Created new user '%s'"%username)

    # POST-VALIDATION hooks.  All required fields should be valid.
    if g.notebook.conf['email']:

        # TODO: make this come from the server settings
        key = register_make_key()
        listenaddr = g.notebook.interface
        port = g.notebook.port
        fromaddr = 'no-reply@%s' % listenaddr
        body = register_build_msg(
            key, username, listenaddr, port, g.notebook.secure)

        # Send a confirmation message to the user.
        try:
            send_mail(fromaddr, email_address,
                      _("Sage Notebook Registration"), body)
            waiting[key] = username
        except ValueError:
            pass

    # Go to the login page.
    nb_conf = g.notebook.conf
    template_dict = {'accounts': nb_conf['accounts'],
                     'welcome_user': username,
                     'recovery': nb_conf['email'],
                     'sage_version': SAGE_VERSION}

    return render_template('html/login.html', **template_dict)


@authentication.route('/confirm')
@with_lock
def confirm():
    if not g.notebook.conf['email']:
        return message_template(_('The confirmation system is not active.'))
    key = int(request.values.get('key', '-1'))

    invalid_confirm_key = _("""\
    <h1>Invalid confirmation key</h1>
    <p>You are reporting a confirmation key that has not been assigned by this
    server. Please <a href="/register">register</a> with the server.</p>
    """)
    try:
        username = waiting[key]
        user = g.notebook.user_manager[username]
        user.email_confirmed = True
    except KeyError:
        return message_template(invalid_confirm_key, '/register')
    success = _(
        """<h1>Email address confirmed for user %(username)s</h1>""",
        username=username)
    del waiting[key]
    return message_template(success, title=_('Email Confirmed'),
                            username=username)


@authentication.route('/forgotpass')
@with_lock
def forgot_pass():
    if not g.notebook.conf['email']:
        return message_template(
            _('The account recovery system is not active.'))

    username = request.values.get('username', '').strip()
    if not username:
        return render_template('html/accounts/account_recovery.html')

    def error(msg):
        return message_template(msg, url_for('forgot_pass'))

    try:
        user = g.notebook.user_manager[username]
    except KeyError:
        return error(_('Username is invalid.'))

    if not user.email_confirmed:
        return error(_("The e-mail address hasn't been confirmed."))

    # XXX: some of this could be factored out into a random passowrd
    # function.  There are a few places in admin.py that also use it.
    chara = string.ascii_letters + string.digits
    password = ''.join([choice(chara) for i in range(8)])

    # TODO: make this come from the server settings

    listenaddr = g.notebook.interface
    port = g.notebook.port
    fromaddr = 'no-reply@%s' % listenaddr
    body = register_build_password_msg(
        password, username, listenaddr, port, g.notebook.secure)
    destaddr = user.email
    try:
        send_mail(fromaddr, destaddr, _(
            "Sage Notebook Account Recovery"), body)
    except ValueError:
        # the email address is invalid
        return error(
            _("The new password couldn't be sent to %(dest)s.", dest=destaddr))
    else:
        g.notebook.user_manager[username].password = password

    return message_template(
        _("A new password has been sent to your e-mail address."),
        url_for('base.index'))
