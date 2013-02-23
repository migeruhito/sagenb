from flask import g
from flask.ext.themes2 import render_theme_template

def render_template(template, **context):
    theme = g.notebook.conf()['theme']
    return render_theme_template(theme, template, **context)
