from flask import current_app, g
from flask.ext.themes2 import render_theme_template

def render(template, **context):
    theme = g.notebook.conf().get('theme', current_app.config['DEFAULT_THEME'])
    return render_theme_template(theme, template, **context)
