# -*- coding: utf-8 -*-
"""
HTML Templating for the Notebook

AUTHORS:

- J. Miguel Farto (2013-02-23): initial version
"""
#############################################################################
#       Copyright (C) 2007 William Stein <wstein@gmail.com>
#  Distributed under the terms of the GNU General Public License (GPL)
#  The full text of the GPL is available at:
#                  http://www.gnu.org/licenses/
#############################################################################
from flask import g, current_app
from flask.ext.themes2 import render_theme_template, Theme
from jinja2.exceptions import TemplateNotFound

def render_template(template, **context):
    """
    For themes to work this replacement of flask.render_template must be used.

    INPUT:

    - As in flask.render_template
    
    OUTPUT:

    - As in flask.render_template, but if the current theme miss the template, the application's normal template is served.

    EXAMPLES::

        sage: from sagenb.notebook.themes import render_template
        sage: type(render_template)
    """
    theme = g.notebook.conf()['theme']
    return render_theme_template(theme, template, **context)

def get_theme_template(app, theme, template_name, _fallback=True):
    """
    As flask.templating.Environment.get_template(), but returns if possible a theme'd template. 
    If ``_fallback`` is True and the template does not exist within the theme,
    it will fall back on trying to render the template using the application's
    normal templates.
    This function maybe should be in flask.ext.themes2
    
    INPUT:
    
    - ``app`` - a flask.Flask instance
    - ``theme`` - Either the identifier of the theme to use, or an actual `Theme` instance.
    - ``template_name`` - a path for a template.
    - ``_fallback`` -  Whether to fall back to the default

    OUTPUT:
    
    - a template instance or raise TemplateNotFound Exception

    EXAMPLES::

        sage: from sagenb.notebook.themes import get_theme_template 
        sage: type(get_theme_template)
    """
    if isinstance(theme, Theme):
        theme = theme.identifier
    try:
        return app.jinja_env.get_template(
                '_themes/{}/{}'.format(theme, template_name))   
    except TemplateNotFound:
        if _fallback:
            return app.jinja_env.get_template(template_name)
        else:
            raise

def get_template(template_name):
    """
    Get a current theme'd template.
    
    INPUT:
    
    - ``template_name`` - a path for a template.

    OUTPUT:
    
    - a template instance.

    EXAMPLES::

        sage: from sagenb.notebook.themes import get_template 
        sage: type(get_template)
    """
    theme = g.notebook.conf()['theme']
    return get_theme_template(current_app, theme, template_name)
