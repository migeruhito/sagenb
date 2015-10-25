from __future__ import absolute_import

import os
import string
from random import choice

from flask import Module
from flask import url_for
from flask import request
from flask import redirect
from flask import g
from flask import current_app
from flask.ext.babel import gettext

from sagenb.misc.misc import SAGE_VERSION
from sagenb.notebook.misc import is_valid_username
from sagenb.notebook.themes import render_template

from .decorators import admin_required
from .decorators import with_lock

_ = gettext

admin = Module('sagenb.flask_version.admin')

@admin.route('/users')
@admin.route('/users/reset/<reset>')
@admin_required
@with_lock
def users(reset=None):
    template_dict = {}
    template_dict['sage_version'] = SAGE_VERSION
    if reset:
        chara = string.letters + string.digits
        password = ''.join([choice(chara) for i in range(8)])
        try:
            U = g.notebook.user_manager().user(reset)
            g.notebook.user_manager().set_password(reset, password)
        except KeyError:
            pass
        template_dict['reset'] = [reset, password]

    template_dict['number_of_users'] = len(g.notebook.user_manager().valid_login_names()) if len(g.notebook.user_manager().valid_login_names()) > 1 else None
    users = sorted(g.notebook.user_manager().valid_login_names())
    del users[users.index('admin')]
    template_dict['users'] = [g.notebook.user_manager().user(username) for username in users]
    template_dict['admin'] = g.notebook.user_manager().user(g.username).is_admin()
    template_dict['username'] = g.username
    return render_template(os.path.join('html', 'settings', 'user_management.html'), **template_dict)

@admin.route('/users/suspend/<user>')
@admin_required
@with_lock
def suspend_user(user):
    try:
        U = g.notebook.user_manager().user(user)
        U.set_suspension()
    except KeyError:
        pass
    return redirect(url_for("users"))

@admin.route('/users/delete/<user>')
@admin_required
@with_lock
def del_user(user):
    if user != 'admin':
        try:
            g.notebook.user_manager().delete_user(user)
        except KeyError:
            pass
    return redirect(url_for("users"))

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
    return redirect(url_for("users"))

@admin.route('/adduser', methods = ['GET','POST'])
@admin_required
@with_lock
def add_user():
    template_dict = {'admin': g.notebook.user_manager().user(g.username).is_admin(),
            'username': g.username, 'sage_version': SAGE_VERSION}
    if 'username' in request.values:
        if request.values['cancel']:
            return redirect(url_for('users'))
        username = request.values['username']
        if not is_valid_username(username):
            return render_template(os.path.join('html', 'settings', 'admin_add_user.html'),
                                   error='username_invalid', username_input=username, **template_dict)

        chara = string.letters + string.digits
        password = ''.join([choice(chara) for i in range(8)])
        if username in g.notebook.user_manager().usernames():
            return render_template(os.path.join('html', 'settings', 'admin_add_user.html'),
                                   error='username_taken', username_input=username, **template_dict)
        g.notebook.user_manager().add_user(username, password, '', force=True)

        message = _('The temporary password for the new user <em>%(username)s</em> is <em>%(password)s</em>',
                          username=username, password=password)
        return current_app.message(message, cont='/adduser', title=_('New User'))
    else:
        return render_template(os.path.join('html', 'settings', 'admin_add_user.html'),
                               **template_dict)

@admin.route('/notebooksettings', methods=['GET', 'POST'])
@admin_required
@with_lock
def notebook_settings():
    updated = {}
    if 'form' in request.values:
        updated = g.notebook.conf().update_from_form(request.values)

    #Changes theme
    if 'theme' in request.values:
        # Invalidate dynamic js and css caches so that all the themes can be
        # without restarting
        from sagenb.flask_version import base
        from sagenb.notebook import js, css
        base._localization_cache = {}
        base._mathjax_js_cache = None
        js._cache_javascript = None
        css._css_cache = None
        # TODO: Implement a better and uniform cache system.
        new_theme = request.values['theme']
        if new_theme not in current_app.theme_manager.themes:
            g.notebook.conf()['theme'] = current_app.config['DEFAULT_THEME']
        else:
            g.notebook.conf()['theme'] = new_theme
        current_app.theme_manager.refresh()

    template_dict = {}
    template_dict['sage_version'] = SAGE_VERSION
    template_dict['auto_table'] = g.notebook.conf().html_table(updated)
    template_dict['admin'] = g.notebook.user_manager().user(g.username).is_admin()
    template_dict['username'] = g.username

    return render_template(os.path.join('html', 'settings', 'notebook_settings.html'),
                           **template_dict)
