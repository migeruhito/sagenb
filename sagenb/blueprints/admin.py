from __future__ import absolute_import

import os
import string
from random import choice

from flask import Blueprint
from flask import url_for
from flask import request
from flask import redirect
from flask import g
from flask import current_app
from flask.ext.babel import gettext

from . import base

from ..config import SAGE_VERSION

from ..util.decorators import admin_required
from ..util.decorators import with_lock
from ..util.templates import message as message_template
from ..util.templates import render_template
from ..util.templates import encode_response
from ..util.text import is_valid_username

_ = gettext

admin = Blueprint('admin', __name__)


def random_password(length=8):
    chara = string.letters + string.digits
    return ''.join([choice(chara) for i in range(length)])


@admin.route('/users')
@admin.route('/users/reset/<reset>')
@admin_required
@with_lock
def users(reset=None):
    template_dict = {}
    template_dict['sage_version'] = SAGE_VERSION
    if reset:
        password = random_password()
        try:
            g.notebook.user_manager().set_password(reset, password)
        except LookupError:
            pass
        else:
            template_dict['reset'] = [reset, password]

    template_dict['number_of_users'] = len(
        g.notebook.user_manager().valid_login_names(
        )) if len(g.notebook.user_manager(
        ).valid_login_names()) > 1 else None
    users = sorted(g.notebook.user_manager().valid_login_names())
    del users[users.index('admin')]
    template_dict['users'] = [g.notebook.user_manager().user(username)
                              for username in users]
    template_dict['admin'] = g.notebook.user_manager().user(
        g.username).is_admin()
    template_dict['username'] = g.username
    return render_template(os.path.join(
        'html', 'settings', 'user_management.html'), **template_dict)


@admin.route('/users/suspend/<user>')
@admin_required
@with_lock
def suspend_user(user):
    try:
        U = g.notebook.user_manager().user(user)
        U.set_suspension()
    except KeyError:
        pass
    return redirect(url_for("admin.users"))


@admin.route('/users/delete/<user>')
@admin_required
@with_lock
def del_user(user):
    if user != 'admin':
        try:
            g.notebook.user_manager().delete_user(user)
        except KeyError:
            pass
    return redirect(url_for("admin.sers"))


@admin.route('/users/toggleadmin/<user>')
@admin_required
@with_lock
def toggle_admin(user):
    try:
        U = g.notebook.user_manager().user(user)
        if U.is_admin():
            U.revoke_admin()
        else:
            U.grant_admin()
    except KeyError:
        pass
    return redirect(url_for("admin.users"))


@admin.route('/adduser', methods=['GET', 'POST'])
@admin_required
@with_lock
def add_user():
    template_dict = {
        'admin': g.notebook.user_manager().user(g.username).is_admin(),
        'username': g.username,
        'sage_version': SAGE_VERSION}
    if 'username' in request.values:
        if request.values['cancel']:
            return redirect(url_for('admin.users'))
        username = request.values['username']
        if not is_valid_username(username):
            return render_template(os.path.join('html',
                                                'settings',
                                                'admin_add_user.html'),
                                   error='username_invalid',
                                   username_input=username,
                                   **template_dict)

        chara = string.letters + string.digits
        password = ''.join([choice(chara) for i in range(8)])
        if username in g.notebook.user_manager().usernames():
            return render_template(os.path.join('html',
                                                'settings',
                                                'admin_add_user.html'),
                                   error='username_taken',
                                   username_input=username,
                                   **template_dict)
        g.notebook.user_manager().add_user(username, password, '', force=True)

        message = _('The temporary password for the new user '
                    '<em>%(username)s</em> is <em>%(password)s</em>',
                    username=username, password=password)
        return message_template(message, cont='/adduser', title=_('New User'))
    else:
        return render_template(os.path.join('html',
                                            'settings',
                                            'admin_add_user.html'),
                               **template_dict)


# New UI
@admin.route('/reset_user_password', methods=['POST'])
@admin_required
@with_lock
def reset_user_password():
    user = request.values['username']
    password = random_password()
    try:
        # U = g.notebook.user_manager().user(user)
        g.notebook.user_manager().set_password(user, password)
    except KeyError:
        pass

    return encode_response({
        'message': _(
            'The temporary password for the new user <strong>%(username)s'
            '</strong> is <strong>%(password)s</strong>',
            username=user, password=password)
    })


@admin.route('/suspend_user', methods=['POST'])
@admin_required
@with_lock
def suspend_user_nui():
    user = request.values['username']
    try:
        U = g.notebook.user_manager().user(user)
        U.set_suspension()
    except KeyError:
        pass

    return encode_response({
        'message': _(
            'User <strong>%(username)s</strong> has been '
            'suspended/unsuspended.', username=user)
    })


@admin.route('/add_user', methods=['POST'])
@admin_required
@with_lock
def add_user_nui():
    username = request.values['username']
    password = random_password()

    if not is_valid_username(username):
        return encode_response({
            'error': _('<strong>Invalid username!</strong>')
        })

    if username in g.notebook.user_manager().usernames():
        return encode_response({
            'error': _(
                'The username <strong>%(username)s</strong> is already taken!',
                username=username)
        })

    g.notebook.user_manager().add_user(username, password, '', force=True)
    return encode_response({
        'message': _(
            'The temporary password for the new user <strong>%(username)s'
            '</strong> is <strong>%(password)s</strong>',
            username=username, password=password)
    })
# New UI end


@admin.route('/notebooksettings', methods=['GET', 'POST'])
@admin_required
@with_lock
def notebook_settings():
    updated = {}
    if 'form' in request.values:
        updated = g.notebook.conf().update_from_form(request.values)

    # Changes theme
    if 'theme' in request.values:
        # Invalidate dynamic js caches so that all the themes can be
        # changed without restarting
        base.dynamic_javascript.clear_cache()
        new_theme = request.values['theme']
        if new_theme not in current_app.theme_manager.themes:
            g.notebook.conf()['theme'] = current_app.config['DEFAULT_THEME']
        else:
            g.notebook.conf()['theme'] = new_theme
        # Call this to search for new themes
        # current_app.theme_manager.refresh()

    template_dict = {}
    template_dict['sage_version'] = SAGE_VERSION
    template_dict['auto_table'] = g.notebook.conf().html_table(updated)
    template_dict['admin'] = g.notebook.user_manager().user(
        g.username).is_admin()
    template_dict['username'] = g.username

    return render_template(os.path.join('html',
                                        'settings',
                                        'notebook_settings.html'),
                           **template_dict)
