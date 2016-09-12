from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from flask import Blueprint
from flask import current_app
from flask import flash
from flask import g
from flask import request
from flask import redirect
from flask import url_for
from flask_babel import gettext

from . import base

from ..config import SAGE_VERSION
from ..config import UN_ADMIN

from ..util.auth import random_password
from ..util.decorators import admin_required
from ..util.decorators import login_required
from ..util.decorators import with_lock
from ..util.templates import message as message_template
from ..util.templates import render_template
from ..util.templates import encode_response
from ..util.text import is_valid_email
from ..util.text import is_valid_password
from ..util.text import is_valid_username

_ = gettext

admin = Blueprint('admin', __name__)


@admin.route('/settings', methods=['GET', 'POST'])
@login_required
@with_lock
def settings_page():
    error = None
    redirect_to_home = None
    redirect_to_logout = None
    nu = g.notebook.user_manager[g.username]

    autosave = int(request.values.get('autosave', 0)) * 60
    if autosave:
        nu['autosave_interval'] = autosave
        redirect_to_home = True

    old = request.values.get('old-pass', None)
    new = request.values.get('new-pass', None)
    two = request.values.get('retype-pass', None)

    if new or two:
        if not old:
            error = _('Old password not given')
        elif not g.notebook.user_manager.check_password(g.username, old):
            error = _('Incorrect password given')
        elif not new:
            error = _('New password not given')
        elif not is_valid_password(new, g.username):
            error = _(
                'Password not acceptable. Must be 4 to 32 characters and not '
                'contain spaces or username.')
        elif not two:
            error = _('Please type in new password again.')
        elif new != two:
            error = _('The passwords you entered do not match.')

        if not error:
            # The browser may auto-fill in "old password," even
            # though the user may not want to change her password.
            g.notebook.user_manager[g.username].password = new
            redirect_to_logout = True

    if g.notebook.conf['email']:
        newemail = request.values.get('new-email', None)
        if newemail:
            if is_valid_email(newemail):
                nu.email = newemail
                # nu.email_confirmed = False
                redirect_to_home = True
            else:
                error = _('Invalid e-mail address.')

    if error:
        return message_template(error, url_for('admin.settings_page'),
                                username=g.username)

    if redirect_to_logout:
        return redirect(url_for('authentication.logout'))

    if redirect_to_home:
        return redirect(url_for('worksheet_listing.home', username=g.username))

    td = {}
    td['sage_version'] = SAGE_VERSION
    td['username'] = g.username

    td['autosave_intervals'] = (
        (i, ' selected') if nu['autosave_interval'] // 60 == i else (i, '')
        for i in range(1, 10, 2))

    td['email'] = g.notebook.conf['email']
    if td['email']:
        td['email_address'] = nu.email or 'None'
        if nu.email_confirmed:
            td['email_confirmed'] = _('Confirmed')
        else:
            td['email_confirmed'] = _('Not confirmed')

    td['admin'] = nu.is_admin

    return render_template(
        'html/settings/account_settings.html', **td)


@admin.route('/users')
@admin_required
@with_lock
def users():
    template_dict = {}
    template_dict['sage_version'] = SAGE_VERSION

    users = sorted(g.notebook.user_manager.login_allowed_usernames)
    template_dict['number_of_users'] = len(users) if len(users) > 1 else None
    del users[users.index(UN_ADMIN)]
    template_dict['users'] = [g.notebook.user_manager[username]
                              for username in users]
    template_dict['admin'] = g.notebook.user_manager[g.username].is_admin
    template_dict['username'] = g.username
    return render_template(
        'html/settings/user_management.html', **template_dict)


@admin.route('/users/reset/<user>')
@admin_required
@with_lock
def reset_user(user):
    try:
        U = g.notebook.user_manager[user]
    except KeyError:
        flash(gettext(
                'The user <strong>%(username)s</strong> does not exist',
                username=user), 'error')
    else:
        password = random_password()
        U.password = password
        flash(gettext('The password for the user %(u)s has been reset to '
                      '<strong>%(p)s</strong>', u=user, p=password), 'success')
    return redirect(url_for("admin.users"))


@admin.route('/users/suspend/<user>')
@admin_required
@with_lock
def suspend_user(user):
    try:
        U = g.notebook.user_manager[user]
    except KeyError:
        pass
    else:
        U.is_suspended = not U.is_suspended
    return redirect(url_for("admin.users"))


@admin.route('/users/delete/<user>')
@admin_required
@with_lock
def del_user(user):
    if user != UN_ADMIN:
        try:
            del g.notebook.user_manager[user]
        except KeyError:
            pass
    return redirect(url_for("admin.users"))


@admin.route('/users/toggleadmin/<user>')
@admin_required
@with_lock
def toggle_admin(user):
    try:
        U = g.notebook.user_manager[user]
    except KeyError:
        pass
    else:
        if U.is_admin:
            U.revoke_admin()
        else:
            U.grant_admin()
    return redirect(url_for("admin.users"))


@admin.route('/adduser', methods=['GET', 'POST'])
@admin_required
@with_lock
def add_user():
    template_url = 'html/settings/admin_add_user.html'
    template_dict = {
        'admin': g.notebook.user_manager[g.username].is_admin,
        'username': g.username,
        'sage_version': SAGE_VERSION}
    if 'username' in request.values:
        if request.values['cancel']:
            return redirect(url_for('admin.users'))
        username = request.values['username']
        if not is_valid_username(username):
            return render_template(
                template_url,
                error='username_invalid', username_input=username,
                **template_dict)

        password = random_password()
        if username in g.notebook.user_manager:
            return render_template(
                template_url,
                error='username_taken', username_input=username,
                **template_dict)
        g.notebook.user_manager.add_user(username, password, '')

        message = _('The temporary password for the new user '
                    '<em>%(username)s</em> is <em>%(password)s</em>',
                    username=username, password=password)
        return message_template(message, cont='/adduser', title=_('New User'))
    else:
        return render_template(template_url, **template_dict)


# New UI
@admin.route('/suspend_user', methods=['POST'])
@admin_required
@with_lock
def suspend_user_nui():
    user = request.values['username']
    try:
        U = g.notebook.user_manager[user]
    except KeyError:
        pass
    else:
        U.is_suspended = not U.is_suspended
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

    if username in g.notebook.user_manager:
        return encode_response({
            'error': _(
                'The username <strong>%(username)s</strong> is already taken!',
                username=username)
        })

    g.notebook.user_manager.add_user(username, password, '')
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
        updated = g.notebook.conf.update_from_form(request.values)

    # Changes theme
    if 'theme' in request.values:
        # Invalidate dynamic js caches so that all the themes can be
        # changed without restarting
        base.dynamic_javascript.clear_cache()
        new_theme = request.values['theme']
        if new_theme not in current_app.theme_manager.themes:
            g.notebook.conf['theme'] = current_app.config['DEFAULT_THEME']
        else:
            g.notebook.conf['theme'] = new_theme
        # Call this to search for new themes
        # current_app.theme_manager.refresh()

    template_dict = {}
    template_dict['sage_version'] = SAGE_VERSION
    template_dict['auto_table'] = g.notebook.conf.html_table(updated)
    template_dict['admin'] = g.notebook.user_manager[g.username].is_admin
    template_dict['username'] = g.username

    return render_template(
        'html/settings/notebook_settings.html', **template_dict)
