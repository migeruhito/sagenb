# -*- coding: utf-8 -*
"""
This is a stand-in for Sage's inspection code in
sage.misc.sageinspect.  If Sage is available, that code will be used
here. Otherwise, use simple-minded replacements based on Python's
inspect module.

AUTHORS:

- John Palmieri, Simon King

MODIFIED BY:
- J Miguel Farto, 2015
"""
from __future__ import absolute_import

import inspect
from ..util import import_from


def sagenb_getdef(obj, obj_name=''):
    r"""
    Return the definition header for any callable object.

    INPUT:

    - ``obj`` - function
    - ``obj_name`` - string (optional, default '')

    This calls inspect.getargspec, formats the result, and prepends
    ``obj_name``.

    EXAMPLES::

        sage: from sagenb.misc.sageinspect import sagenb_getdef
        sage: def f(a, b=0, *args, **kwds): pass
        sage: sagenb_getdef(f, 'hello')
        'hello(a, b=0, *args, **kwds)'
    """
    return obj_name + inspect.formatargspec(*inspect.getargspec(obj))


def sagenb_getdoc(obj, obj_name=''):
    r"""
    Return the docstring associated to ``obj`` as a string.
    This is essentially a front end for inspect.getdoc.

    INPUT: ``obj``, a function, module, etc.: something with a docstring.
    If "self" is present in the docmentation, then replace it with `obj_name`.

    EXAMPLES::

        sage: from sagenb.misc.sageinspect import sagenb_getdoc
        sage: sagenb_getdoc(sagenb.misc.sageinspect.sagenb_getdoc)[0:55]
        'Return the docstring associated to ``obj`` as a string.'
    """
    s = inspect.getdoc(obj)
    if obj_name != '':
        i = obj_name.find('.')
        if i != -1:
            obj_name = obj_name[:i]
        s = s.replace('self.', '%s.' % obj_name)
    return s


sage_getargspec = import_from(
    'sage.misc.sageinspect', 'sage_getargspec',
    default=lambda: inspect.getargspec)
sage_getdef = import_from(
    'sage.misc.sageinspect', 'sage_getdef', default=lambda: sagenb_getdef)
sage_getdoc = import_from(
    'sage.misc.sageinspect', 'sage_getdoc', default=lambda: sagenb_getdoc)
sage_getfile = import_from(
    'sage.misc.sageinspect', 'sage_getfile', default=lambda: inspect.getfile)
sage_getsourcelines = import_from(
    'sage.misc.sageinspect', 'sage_getsourcelines',
    default=lambda: inspect.getsourcelines)
