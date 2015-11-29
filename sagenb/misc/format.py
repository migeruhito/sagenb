# -*- coding: utf-8 -*-
"""
Code formatting functions for the sage_server

Functions used to format code to be used in the sage_server.

AUTHOR:

 - (c) J. Miguel Farto, 2015.
"""
from __future__ import absolute_import


import ast


def break_code(code, nodes=True):
    tree = ast.parse(code.replace('\r\n', '\n').replace('\r', '\n'))
    limits = ((node.lineno - 1, node.col_offset) for node in tree.body)
    line_offsets = [0]
    for line in code.splitlines(True)[:-1]:
        line_offsets.append(line_offsets[-1] + len(line))
    offsets = [line_offsets[lin] + col for lin, col in limits]
    offsets.append(len(code))
    lines = []
    for i, offset in enumerate(offsets[:-1]):
        node = tree.body[i]
        line = code[offset:offsets[i + 1]].rstrip(u' \t')
        lines.append([line, node] if nodes else line)
    return lines


def test_fimp(code, code0, code1):
    node = code[1]
    test = isinstance(node, ast.ImportFrom) and node.module == '__future__'
    if test:
        code0.append(code)
    else:
        code1.append(code)
    return test


def relocate_future_imports(brk_code):
    """
    Relocates imports from __future__ to the beginning of the
    file. Raises ``SyntaxError`` if the string does not have proper
    syntax.

    OUTPUT:

    - (string, string) -- a tuple consisting of the string without
      ``__future__`` imports and the ``__future__`` imports.

    EXAMPLES::

        sage: from sagenb.misc.format import relocate_future_imports
        sage: relocate_future_imports('')
        '\n'
        sage: relocate_future_imports('foobar')
        '\nfoobar'
        sage: relocate_future_imports(
            'from __future__ import division\nprint "Hi!"')
        'from __future__ import division\n\nprint "Hi!"'
        sage: relocate_future_imports(
            'from __future__ import division;print "Testing"')
        'from __future__ import division\nprint "Testing"'
        sage: relocate_future_imports(
            'from __future__ import division\nprint "Testing!" '
            '# from __future__ import division does Blah')
        'from __future__ import division\n\nprint "Testing!" '\
        '# from __future__ import division does Blah'
        sage: relocate_future_imports(
            '# -*- coding: utf-8 -*-\nprint "Testing!"\n'
            'from __future__ import division, operator\nprint "Hey!"')
            'from __future__ import division,operator\n# -*- '\
            'coding: utf-8 -*-\nprint "Testing!"\n\nprint "Hey!"'
    """
    try:
        node = brk_code[0]
    except IndexError:
        return brk_code

    code0 = []
    code1 = []
    first = 0
    test = True
    while test:
        try:
            code = brk_code[first]
        except IndexError:
            return brk_code

        test = test_fimp(code, code0, code1)
        first += 1

    for i in range(first, len(brk_code)):
        code = brk_code[i]
        if test_fimp(code, code0, code1):
            prev = code1[-1]
            if code[0].endswith('\n') and prev[0].endswith(';'):
                prev[0] = '{}\n'.format(prev[0][:-1])

    if code0:
        code0[-1][0] = '{}\n'.format(code0[-1][0])

    code0.extend(code1)
    return code0

    fimp = (i for i, node in enumerate(brk_code)
            if isinstance(node[1], ast.ImportFrom) and
            node[1].module == '__future__')
    iprev = -1
    for i in fimp:
        code1.extend(brk_code[iprev+1:i-2])
        node = brk_code[i]
        end_char = node[0][-1]
        code0.append(('{}\n'.format(node[0]), node[1]))
        try:
            prev = brk_code[i-1]
        except IndexError:
            pass
        else:
            if end_char == '\n' and prev[0][-1] == ';':
                prev = ('{}\n'.format(prev[0][:-1]), prev[1])
        code1.append(prev)
        iprev = i
    code1.extend(brk_code[iprev+1:])
    code0.extend(code1)
    return code0


def displayhook_hack(brk_code):
    """
    Modified version of string so that ``exec``'ing it results in
    displayhook possibly being called.

    STRING:

        - ``string`` - a string

    OUTPUT:

        - string formated so that when exec'd last line is printed if
          it is an expression
    """
    code = [node[0] for node in brk_code]
    i = len(brk_code)-1
    if not isinstance(brk_code[i][1], ast.Expr):
        return ''.join(code)
    while (i > 0 and isinstance(brk_code[i-1][1], ast.Expr) and
            brk_code[i-1][0].endswith(';')):
        i -= 1
    code0 = ''.join(code[:i])
    code1 = ''.join(code[i:])
    code1 = "exec compile({!r}, '', 'single')".format(code1 if code1 else '')
    return ''.join((code0, code1))


def reformat_code(code):
    return displayhook_hack(relocate_future_imports(break_code(code)))
