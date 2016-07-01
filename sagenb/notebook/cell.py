# -*- coding: utf-8 -*-
"""
A Cell

A cell is a single input/output block. Worksheets are built out of
a list of cells.
"""

###########################################################################
#       Copyright (C) 2006 William Stein <wstein@gmail.com>
#
#  Distributed under the terms of the GNU General Public License (GPL)
#                  http://www.gnu.org/licenses/
###########################################################################
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import ast
import os
import re
import shutil
import time
from cgi import escape
from random import randint
from sys import maxint

from ..config import INTERACT_RESTART
from ..config import INTERACT_UPDATE_PREFIX
from ..config import INTERACT_TEXT
from ..config import INTERACT_HTML
from ..config import MAX_OUTPUT
from ..config import MAX_OUTPUT_LINES
from ..config import TRACEBACK
from ..util import cached_property
from ..util import encoded_str
from ..util import set_restrictive_permissions
from ..util import unicode_str
from ..util import word_wrap
from ..util.templates import render_template
from ..util.text import format_exception


# This regexp matches "cell://blah..." in a non-greedy way (the ?), so
# we don't get several of these combined in one.
re_cell = re.compile('"cell://.*?"')
re_cell_2 = re.compile("'cell://.*?'")   # same, but with single quotes
# Matches script blocks.
re_script = re.compile(r'<script[^>]*?>.*?</script>', re.DOTALL | re.I)
prompt_re = re.compile(r'^\s*(sage:|>>>|\.\.\.)', re.DOTALL | re.UNICODE)


class Cell(object):
    """
    Generic (abstract) cell
    """
    def __init__(self, id, worksheet):
        """
        Creates a new generic cell.

        INPUT:

        - ``id`` - an integer or string; this cell's ID

        - ``worksheet`` - a
          :class:`sagenb.notebook.worksheet.Worksheet` instance; this
          cell's parent worksheet

        EXAMPLES::

            sage: C = sagenb.notebook.cell.Cell(0, None)
            sage: isinstance(C, sagenb.notebook.cell.Cell)
            True
            sage: isinstance(C, sagenb.notebook.cell.TextCell)
            False
            sage: isinstance(C, sagenb.notebook.cell.Cell)
            False
        """
        # property ro
        try:
            self.__id = int(id)
        except ValueError:
            self.__id = id
        self.__input = None  # property
        self.__output = None  # property

        self.__worksheet = worksheet

    def __repr__(self):
        """
        Returns a string representation of this generic cell.

        OUTPUT:

        - a string

        EXAMPLES::

            sage: C = sagenb.notebook.cell.Cell(0, None)
            sage: C.__repr__()
            'Cell 0'
        """
        return "Cell %s" % self.id

    def __cmp__(self, right):
        """
        Compares generic cells by ID.

        INPUT:

        - ``right`` - a :class:`Cell` instance; the cell to
          compare to this cell

        OUTPUT:

        - a boolean

        EXAMPLES::

            sage: C1 = sagenb.notebook.cell.Cell(0, None)
            sage: C2 = sagenb.notebook.cell.Cell(1, None)
            sage: C3 = sagenb.notebook.cell.Cell(0, None)
            sage: [C1 == C2, C1 == C3, C2 == C3]
            [False, True, False]
            sage: C1 = sagenb.notebook.cell.TextCell('bagel', 'abc', None)
            sage: C2 = sagenb.notebook.cell.TextCell('lox', 'abc', None)
            sage: C3 = sagenb.notebook.cell.TextCell('lox', 'xyz', None)
            sage: [C1 == C2, C1 == C3, C2 == C3]
            [False, False, True]
            sage: C1 = sagenb.notebook.cell.ComputeCell(7, '3+2', '5', None)
            sage: C2 = sagenb.notebook.cell.ComputeCell(7, '3+2', 'five', None)
            sage: C3 = sagenb.notebook.cell.ComputeCell('7', '2+3', '5', None)
            sage: [C1 == C2, C1 == C3, C2 == C3]
            [True, True, True]
        """
        return cmp(self.id, right.id)

    @property
    def id(self):
        """
        Returns this generic cell's ID.

        OUTPUT:

        - an integer or string

        EXAMPLES::

            sage: C = sagenb.notebook.cell.Cell(0, None)
            sage: C.id
            0
            sage: C = sagenb.notebook.cell.ComputeCell(
                'blue', '2+3', '5', None)
            sage: C.id
            'blue'
            sage: C = sagenb.notebook.cell.TextCell('yellow', '2+3', None)
            sage: C.id
            'yellow'
        """
        return self.__id

    @property
    def input(self):
        return self.__input

    @input.setter
    def input(self, value):
        pass

    @input.deleter
    def input(self):
        pass

    def worksheet(self):
        """
        Returns this generic cell's worksheet object.

        OUTPUT:

        - a :class:`sagenb.notebook.worksheet.Worksheet` instance

        EXAMPLES::

            sage: C = sagenb.notebook.cell.Cell(0, 'worksheet object')
            sage: C.worksheet()
            'worksheet object'
            sage: nb = sagenb.notebook.notebook.Notebook(
                tmp_dir(ext='.sagenb'))
            sage: nb.user_manager.add_user(
                'sage','sage','sage@sagemath.org',force=True)
            sage: W = nb.create_wst('Test', 'sage')
            sage: C = sagenb.notebook.cell.ComputeCell(0, '2+3', '5', W)
            sage: C.worksheet() is W
            True
            sage: nb.delete()
        """
        return self.__worksheet

    def worksheet_filename(self):
        """
        Returns the filename of this generic cell's worksheet object.

        - ``publish`` - a boolean (default: False); whether to render
          a published cell

        OUTPUT:

        - a string

        EXAMPLES::


            sage: nb = sagenb.notebook.notebook.Notebook(
                tmp_dir(ext='.sagenb'))
            sage: nb.user_manager.add_user(
                'sage','sage','sage@sagemath.org',force=True)
            sage: W = nb.create_wst('Test', 'sage')
            sage: C = sagenb.notebook.cell.ComputeCell(0, '2+3', '5', W)
            sage: C.worksheet_filename()
            'sage/0'
            sage: nb.delete()
         """
        return self.worksheet().filename

    def is_auto_cell(self):
        """
        Returns whether this is an automatically evaluated generic
        cell.  This is always false for :class:`Cell`\ s and
        :class:`TextCell`\ s.

        OUTPUT:

        - a boolean

        EXAMPLES::

            sage: G = sagenb.notebook.cell.Cell(0, None)
            sage: T = sagenb.notebook.cell.TextCell(0, 'hello!', None)
            sage: [X.is_auto_cell() for X in (G, T)]
            [False, False]
        """
        return False

    def is_interactive_cell(self):
        """
        Returns whether this generic cell uses
        :func:`sagenb.notebook.interact.interact` as a function call
        or decorator.

        OUTPUT:

        - a boolean

        EXAMPLES::

            sage: G = sagenb.notebook.cell.Cell(0, None)
            sage: T = sagenb.notebook.cell.TextCell(0, 'hello!', None)
            sage: [X.is_auto_cell() for X in (G, T)]
            [False, False]
        """
        return False

    # New UI

    def basic(self):
        """
        Returns the cell as a python object
        """
        return {
            'id': self.id,
            }
    # New UI end


class TextCell(Cell):
    """
    Text cell
    """
    super_class = Cell

    def __init__(self, id, input, worksheet):
        """
        Creates a new text cell.

        INPUT:

        - ``id`` - an integer or string; this cell's ID

        - ``text`` - a string; this cell's contents

        - ``worksheet`` - a
          :class:`sagenb.notebook.worksheet.Worksheet` instance; this
          cell's parent worksheet

        EXAMPLES::

            sage: C = sagenb.notebook.cell.TextCell(0, '2+3', None)
            sage: C == loads(dumps(C))
            True
        """
        self.super_class.__init__(self, id, worksheet)
        self.input = unicode_str(input)

    def __repr__(self):
        """
        Returns a string representation of this text cell.

        OUTPUT:

        - a string

        EXAMPLES::

            sage: C = sagenb.notebook.cell.TextCell(0, '2+3', None)
            sage: C.__repr__()
            'TextCell 0: 2+3'
        """
        return "TextCell %s: %s" % (self.id, encoded_str(self.input))

    @property
    def input(self):
        return self.__input

    @input.setter
    def input(self, value):
        self.__input = unicode_str(value)

    @input.deleter
    def input(self):
        self.__input = u''

    def delete_output(self):
        """
        Delete all output in this text cell.  This does nothing since
        text cells have no output.

        EXAMPLES::

            sage: C = sagenb.notebook.cell.TextCell(0, '2+3', None)
            sage: C
            TextCell 0: 2+3
            sage: C.delete_output()
            sage: C
            TextCell 0: 2+3
        """
        pass  # nothing to do -- text cells have no output

    # New UI

    def basic(self):
        """
        Returns the cell as a python object
        """
        r = {}

        r['id'] = self.id
        r['type'] = 'text'
        r['input'] = self.input

        return r
    # New UI end

    def html(self, wrap=None, div_wrap=True, do_print=False,
             editing=False, publish=False):
        """
        Returns HTML code for this text cell, including its contents
        and associated script elements.

        INPUT:

        - ``wrap`` -- an integer (default: None); number of columns to
          wrap at (not used)

        - ``div_wrap`` -- a boolean (default: True); whether to wrap
          in a div (not used)

        - ``do_print`` - a boolean (default: False); whether to render the
          cell for printing

        - ``editing`` - a boolean (default: False); whether to open an
          editor for this cell

        OUTPUT:

        - a string

        EXAMPLES::

            sage: nb = sagenb.notebook.notebook.Notebook(
                tmp_dir(ext='.sagenb'))
            sage: nb.user_manager.add_user(
                'sage','sage','sage@sagemath.org',force=True)
            sage: W = nb.create_wst('Test', 'sage')
            sage: C = sagenb.notebook.cell.TextCell(0, '2+3', W)
            sage: C.html()
            u'...text_cell...2+3...'
            sage: C.input = "$2+3$"
        """
        return render_template(
            os.path.join('html', 'notebook', 'text_cell.html'),
            cell=self, wrap=wrap, div_wrap=div_wrap,
            do_print=do_print,
            editing=editing, publish=publish)

    @property
    def plain_text(self):
        ur"""
        Returns a plain text version of this text cell.

        INPUT:

        - ``prompts`` - a boolean (default: False); whether to strip
          interpreter prompts from the beginning of each line

        OUTPUT:

        - a string

        EXAMPLES::

            sage: C = sagenb.notebook.cell.TextCell(0, '2+3', None)
            sage: C.plain_text
            u'2+3'
            sage: C = sagenb.notebook.cell.TextCell(0, 'ěščřžýáíéďĎ', None)
            sage: C.plain_text
            u'\u011b\u0161\u010d\u0159\u017e\xfd\xe1\xed\xe9\u010f\u010e'
        """
        return self.input

    @property
    def edit_text(self):
        """
        Returns the text to be displayed for this text cell in the
        Edit window.

        OUTPUT:

        - a string

        EXAMPLES::

            sage: C = sagenb.notebook.cell.TextCell(0, '2+3', None)
            sage: C.edit_text
            u'2+3'
        """
        return self.input


class ComputeCell(Cell):
    """
    Compute cell
    """
    super_class = Cell

    def __init__(self, id, input, output, worksheet):
        """
        Creates a new compute cell.

        INPUT:

        - ``id`` - an integer or string; the new cell's ID

        - ``input`` - a string; this cell's input

        - ``output`` - a string; this cell's output

        - ``worksheet`` - a
          :class:`sagenb.notebook.worksheet.Worksheet` instance; this
          cell's worksheet object

        EXAMPLES::

            sage: C = sagenb.notebook.cell.ComputeCell(0, '2+3', '5', None)
            sage: C == loads(dumps(C))
            True
        """

        # Data model
        self.super_class.__init__(self, id, worksheet)

        # State
        # start with a random integer so that evaluations of the cell
        # from different runs have different version numbers.
        self.version = randint(0, maxint)
        self.interrupted = False
        self.evaluated = False
        self.__interact_input = None
        self.__interact_output = None
        self.has_new_output = False
        self.__changed_input = u''  # property
        # self.introspect = False
        self.__introspect = False
        self.__introspect_html = u''  # property

        # Data model
        self.__input = unicode_str(input)  # property
        self.__output = unicode_str(output).replace('\r', '')

    @property
    def introspect(self):
        return self.__introspect

    @introspect.setter
    def introspect(self, value):
        if value:
            print('\n{1}\n{0}\n{1}\n'.format(value[0], '='*80))
            print('\n{1}\n{0}\n{1}\n'.format(value[1], '='*80))
        self.__introspect = value

    def __repr__(self):
        """
        Returns a string representation of this compute cell.

        OUTPUT:

        - a string

        EXAMPLES::

            sage: C = sagenb.notebook.cell.ComputeCell(0, '2+3', '5', None); C
            Cell 0: in=2+3, out=5
        """
        return 'Cell %s: in=%s, out=%s' % (self.id, self.input, self.__output)

    # Input

    @property
    def input(self):
        """
        Returns this compute cell's input text.

        OUTPUT:

        - a string

        EXAMPLES::

            sage: C = sagenb.notebook.cell.ComputeCell(0, '2+3', '5', None)
            sage: C.input
            u'2+3'
        """
        return self.__input

    @input.setter
    def input(self, input):
        """
        Sets the input text of this compute cell.

        INPUT:

        - ``input`` - a string; the new input text

        TODO: Add doctests for the code dealing with interact.

        EXAMPLES::

            sage: nb = sagenb.notebook.notebook.Notebook(
                tmp_dir(ext='.sagenb'))
            sage: nb.user_manager.add_user(
                'sage','sage','sage@sagemath.org',force=True)
            sage: W = nb.create_wst('Test', 'sage')
            sage: C = W.new_cell_after(0, "2^2")
            sage: C.evaluate()
            sage: W.check_comp(
                wait=9999)     # random output -- depends on computer speed
            ('d', Cell 1: in=2^2, out=
            4
            )
            sage: initial_version=C.version
            sage: C.input = '3+3'
            sage: C.input
            u'3+3'
            sage: C.evaluated
            False
            sage: C.version-initial_version
            1
            sage: W.quit()
            sage: nb.delete()
        """
        # Stuff to deal with interact
        input = unicode_str(input)

        if input.startswith(INTERACT_UPDATE_PREFIX):
            self.__interact_input = input[len(INTERACT_UPDATE_PREFIX) + 1:]
            self.version += 1
            return
        else:
            self.__interact_input = None
            self.__interact_output = None

        # We have updated the input text so the cell can't have
        # been evaluated.
        self.evaluated = False
        self.version += 1
        self.__input = input

        # Uncache system, percent directives and cleaned_input.
        del self.__parsed_input

    @property
    def changed_input(self):
        """
        Returns the changed input text for this compute cell, deleting
        any previously stored text.

        OUTPUT:

        - a string

        EXAMPLES::

            sage: C = sagenb.notebook.cell.ComputeCell(0, '2+3', '5', None)
            sage: initial_version=C.version
            sage: C.changed_input
            u''
            sage: C.changed_input = '3+3'
            sage: C.input
            u'3+3'
            sage: C.changed_input
            u'3+3'
            sage: C.changed_input
            u''
            sage: C.version-initial_version
            0
        """
        t = self.__changed_input
        del self.changed_input
        return t

    @changed_input.setter
    def changed_input(self, value):
        """
        Updates this compute cell's changed input text.  Note: This
        does not update the version of the cell.  It's typically used,
        e.g., for tab completion.

        INPUT:

        - ``new_text`` - a string; the new changed input text

        EXAMPLES::

            sage: C = sagenb.notebook.cell.ComputeCell(0, '2+3', '5', None)
            sage: C.changed_input = '3+3'
            sage: C.input
            u'3+3'
            sage: C.changed_input
            u'3+3'
        """
        self.__changed_input = unicode_str(value)
        self.__input = self.__changed_input

    @changed_input.deleter
    def changed_input(self):
        self.__changed_input = u''

    @cached_property()
    def __parsed_input(self):
        r"""
        Parses this compute cell's percent directives, determines its
        system (if any), and returns the "cleaned" input text.

        OUTPUT:

        - a string

        EXAMPLES::

            sage: C = sagenb.notebook.cell.ComputeCell(
                0, '%hide\n%maxima\n%pi+3', '5', None)
            sage: C.parse_percent_directives()
            u'%pi+3'
            sage: C.percent_directives
            [u'hide', u'maxima']
        """
        percent, text = re.match(
            r'((?:(?:^|(?<=\n))\s*(?:%.*?|#auto)\s*(?:\n|$))*)(.*)',
            self.input, re.DOTALL).groups()
        percent = re.findall(
            r'(?:%|#(?=auto))(.*?|auto)\s*(?:\n|$)', percent)
        systems = [d for d in percent if d not in ['auto', 'hide', 'hideall',
                                                   'save_server', 'time',
                                                   'timeit']]
        system = systems[-1] if systems else None

        text = text.rstrip() if system == 'fortran' else text.strip()
        return system, percent, text

    @property
    def system(self):
        r"""
        Returns the system used to evaluate this compute cell.  The
        system is specified by a percent directive like '%maxima' at
        the top of a cell.

        Returns None, if no system is explicitly specified.  In this
        case, the notebook evaluates the cell using the worksheet's
        default system.

        OUTPUT:

        - a string

        EXAMPLES::

            sage: C = sagenb.notebook.cell.ComputeCell(
                0, '%maxima\n2+3', '5', None)
            sage: C.system
            u'maxima'
            sage: prefixes = ['%hide', '%time', '']
            sage: cells = [sagenb.notebook.cell.ComputeCell(
                0, '%s\n2+3'%prefix, '5', None) for prefix in prefixes]
            sage: [(C, C.system) for C in cells if C.system is not None]
            []
        """
        return self.__parsed_input[0]

    @property
    def percent_directives(self):
        r"""
        Returns a list of this compute cell's percent directives.

        OUTPUT:

        - a list of strings

        EXAMPLES::

            sage: C = sagenb.notebook.cell.ComputeCell(
                0, '%hide\n%maxima\n2+3', '5', None)
            sage: C.percent_directives
            [u'hide', u'maxima']
        """
        return self.__parsed_input[1]

    @property
    def cleaned_input_text(self):
        r"""
        Returns this compute cell's "cleaned" input text, i.e., its
        input with all of its percent directives removed.  If this
        cell is interacting, it returns the interacting text.

        OUTPUT:

        - a string

        EXAMPLES::

            sage: C = sagenb.notebook.cell.ComputeCell(
                0, '%hide\n%maxima\n2+3', '5', None)
            sage: C.cleaned_input_text
            u'2+3'
        """
        return (self.__interact_input if self.__interact_input is not None
                else self.__parsed_input[2])

    # Output

    def output_text(self, ncols=0, html=True, raw=False, allow_interact=True):
        ur"""
        Returns this compute cell's output text.

        INPUT:

        - ``ncols`` - an integer (default: 0); the number of word wrap
          columns

        - ``html`` - a boolean (default: True); whether to output HTML

        - ``raw`` - a boolean (default: False); whether to output raw
          text (takes precedence over HTML)

        - ``allow_interact`` - a boolean (default: True); whether to
          allow :func:`sagenb.notebook.interact.interact`\ ion

        OUTPUT:

        - a string

        EXAMPLES::

            sage: nb = sagenb.notebook.notebook.Notebook(
                tmp_dir(ext='.sagenb'))
            sage: nb.user_manager.add_user(
                'sage','sage','sage@sagemath.org',force=True)
            sage: W = nb.create_wst('Test', 'sage')
            sage: C = sagenb.notebook.cell.ComputeCell(0, '2+3', '5', W)
            sage: C.output_text()
            u'<pre class="shrunk">5</pre>'
            sage: C.output_text(html=False)
            u'<pre class="shrunk">5</pre>'
            sage: C.output_text(raw=True)
            u'5'
            sage: C = sagenb.notebook.cell.ComputeCell(
                0, 'ěščřžýáíéďĎ', 'ěščřžýáíéďĎ', W)
            sage: C.output_text()
            u'<pre class="shrunk">'
            u'\u011b\u0161\u010d\u0159\u017e\xfd\xe1\xed\xe9\u010f\u010e</pre>'
            sage: C.output_text(raw=True)
            u'\u011b\u0161\u010d\u0159\u017e\xfd\xe1\xed\xe9\u010f\u010e'
        """
        if allow_interact and self.__interact_output is not None:
            # Get the input template
            z = self.output_text(ncols, html, raw, allow_interact=False)
            if INTERACT_TEXT not in z or INTERACT_HTML not in z:
                return z
            if ncols:
                # Get the output template
                # Fill in the output template
                output, html = self.__interact_output
                output = self.parse_html(output, ncols, False)
                z = z.replace(INTERACT_TEXT, output)
                z = z.replace(INTERACT_HTML, html)
                return z
            else:
                # Get rid of the interact div to avoid updating the
                # wrong output location during interact.
                return ''

        self.__output = unicode_str(self.__output)

        is_interact = self.is_interactive_cell()
        if is_interact and ncols == 0:
            if 'Traceback (most recent call last)' in self.__output:
                s = self.__output.replace('cell-interact', '')
                is_interact = False
            else:
                return (u'<h2>Click to the left again to hide and once more '
                        u'to show the dynamic interactive window</h2>')
        else:
            s = self.__output

        if raw:
            return s

        s = s.strip('\n')
        pre_wrapping = len(s.strip()) > 0 and not \
            (is_interact or self.is_html() or '<div class="docstring">' in s)
        if html:
            s = self.parse_html(s, ncols, pre_wrapping)
        elif pre_wrapping:
            s = u'<pre class="shrunk">{}</pre>'.format(s)
        return s

    def set_output_text(self, output, html):
        r"""
        Sets this compute cell's output text.

        INPUT:

        - ``output`` - a string; the updated output text

        - ``html`` - a string; updated output HTML

        - ``sage`` - a :class:`sage` instance (default: None); the
          sage instance to use for this cell(?)

        EXAMPLES::

            sage: C = sagenb.notebook.cell.ComputeCell(0, '2+3', '5', None)
            sage: len(C.plain_text)
            11
            sage: C.set_output_text('10', '10')
            sage: len(C.plain_text)
            12
        """
        output = unicode_str(output)
        html = unicode_str(html)
        if output.count(INTERACT_TEXT) > 1:
            html = (u'<h3><font color="red">WARNING: multiple @interacts in '
                    u'one cell disabled (not yet implemented).</font></h3>')
            output = u''

        # In interacting mode, we just save the computed output
        # (do not overwrite).
        if self.__interact_input is not None:
            self.__interact_output = (output, html)
            if INTERACT_RESTART in output:
                # We forfeit any interact output template (in
                # self.__output), so that the restart message propagates
                # out.  When the set_output_text function in
                # notebook_lib.js gets the message, it should
                # re-evaluate the cell from scratch.
                self.__output = output
            return

        output = output.replace('\r', '')
        # We do not truncate if "notruncate" or "Output truncated!" already
        # appears in the output.  This notruncate tag is used right now
        # in sagenb.notebook.interact, sage.misc.html, and
        # sage.database.sql_db.
        if ('notruncate' not in output and
            'Output truncated!' not in output and
            (len(output) > MAX_OUTPUT or
             output.count('\n') > MAX_OUTPUT_LINES)):
            url = ""
            if not self.computing:
                file = os.path.join(self.directory(), "full_output.txt")
                open(file, "w").write(encoded_str(output))
                url = ("<a target='_new' href='%s/full_output.txt' "
                       "class='file_link'>full_output.txt</a>" % (
                           self.url_to_self()))
                html += "<br>" + url
            lines = output.splitlines()
            start = '\n'.join(lines[:MAX_OUTPUT_LINES // 2])[:MAX_OUTPUT // 2]
            end = '\n'.join(lines[-MAX_OUTPUT_LINES // 2:])[-MAX_OUTPUT // 2:]
            warning = 'WARNING: Output truncated!  '
            if url:
                # make the link to the full output appear at the top too.
                warning += '\n<html>%s</html>\n' % url
            output = warning + '\n\n' + start + '\n\n...\n\n' + end
        self.__output = output
        if not self.is_interactive_cell():
            self._out_html = html

    def delete_output(self):
        r"""
        Deletes all output in this compute cell. This also deletes the
        files, since they appear as output of the cell.

        EXAMPLES::

            sage: C = sagenb.notebook.cell.ComputeCell(0, '2+3', '5', None); C
            Cell 0: in=2+3, out=5
            sage: C.delete_output()
            sage: C
            Cell 0: in=2+3, out=

        When output is deleted, any files in the cell directory are deleted as
        well::

            sage: nb = sagenb.notebook.notebook.load_notebook(
                tmp_dir(ext='.sagenb'))
            sage: nb.user_manager.add_user(
                'sage','sage','sage@sagemath.org',force=True)
            sage: W = nb.create_wst('Test', 'sage')
            sage: W.edit_save('{{{\nplot(sin(x),(x,0,5))\n///\n20\n}}}')
            sage: C = W.cells[0]
            sage: C.evaluate()
            sage: W.check_comp(
                wait=9999)     # random output -- depends on computer speed
            ('d', Cell 0; in=plot(sin(x),(x,0,5)), out=
            <html><font color='black'><img src='cell://sage0.png'></font>
            </html>
            <BLANKLINE>
            )
            sage: C.files()     # random output -- depends on computer speed
            ['sage0.png']
            sage: C.delete_output()
            sage: C.files()
            []
            sage: W.quit()
            sage: nb.delete()
        """
        self.__output = u''
        self._out_html = u''
        self.evaluated = False
        self.delete_files()

    def update_html_output(self, output=''):
        """
        Updates this compute cell's the file list with HTML-style
        links or embeddings.

        For interactive cells, the HTML output section is always
        empty, mainly because there is no good way to distinguish
        content (e.g., images in the current directory) that goes into
        the interactive template and content that would go here.

        INPUT:

        - ``output`` - a string (default: ''); the new output

        EXAMPLES::

            sage: nb = sagenb.notebook.notebook.Notebook(
                tmp_dir(ext='.sagenb'))
            sage: nb.user_manager.add_user(
                'sage','sage','sage@sagemath.org',force=True)
            sage: W = nb.create_wst('Test', 'sage')
            sage: C = sagenb.notebook.cell.ComputeCell(
                0, 'plot(sin(x),0,5)', '', W)
            sage: C.evaluate()
            sage: W.check_comp(
                wait=9999)     # random output -- depends on computer speed
            ('d', Cell 0: in=plot(sin(x),0,5), out=
            <html><font color='black'><img src='cell://sage0.png'></font>
            </html>
            <BLANKLINE>
            )
            sage: C.update_html_output()
            sage: C.output_html(
                )     # random output -- depends on computer speed
            '<img src="/home/sage/0/cells/0/sage0.png?...">'
            sage: W.quit()
            sage: nb.delete()
        """
        if self.is_interactive_cell():
            self._out_html = u""
        else:
            self._out_html = self.files_html(output)

    @property
    def word_wrap_cols(self):
        """
        Returns the number of columns for word wrapping this compute
        cell.  This defaults to 70, but the default setting for a
        notebook is 72.

        OUTPUT:

        - an integer

        EXAMPLES::

            sage: C = sagenb.notebook.cell.ComputeCell(0, '2+3', '5', None)
            sage: C.word_wrap_cols
            70
            sage: nb = sagenb.notebook.notebook.Notebook(
                tmp_dir(ext='.sagenb'))
            sage: nb.user_manager.add_user(
                'sage','sage','sage@sagemath.org',force=True)
            sage: W = nb.create_wst('Test', 'sage')
            sage: C = sagenb.notebook.cell.ComputeCell(0, '2+3', '5', W)
            sage: C.word_wrap_cols
            72
            sage: nb.delete()
        """
        try:
            return self.worksheet().notebook().conf['word_wrap_cols']
        except AttributeError:
            return 70

    def format_text(self, plain=True, ncols=0, max_out=None):
        r"""
        Returns the plain text version of this compute cell.

        INPUT:

        - ``ncols`` - an integer (default: 0); the number of word wrap
          columns

        - ``plain`` - a boolean (default: False); whether to strip
          interpreter plain from the beginning of each line

        - ``max_out`` - an integer (default: None); the maximum number
          of characters to return

        OUTPUT:

        - ``text`` - Plaintext string of the cell

        EXAMPLES::

            sage: C = sagenb.notebook.cell.ComputeCell(0, '2+3', '5', None)
            sage: len(C.format_text())
            11
        """
        if ncols == 0:
            ncols = self.word_wrap_cols

        if plain and not prompt_re.search(self.input):
            text = re.sub(
                r'(^(?=.)|\n)(?!\.\.\.)', r'\1sage: ',
                re.sub(r'(\n\.\.\.   .*?)(?=$|\n(?!\.\.\.))', r'\1\n...',
                       re.sub(r'\n(\s+|else:)', r'\n...   \1',
                              re.sub(r'\n\s*\n', '\n', self.input.strip()))))
        else:
            text = self.input

        if plain:
            msg = TRACEBACK
            if self.__output.strip().startswith(msg):
                out = re.sub(r'({})(\n +.*)*'.format(re.escape(msg)),
                             r'\1\n...', self.output.strip())
            else:
                out = self.output_text(ncols, raw=True, html=False)
        else:
            out = '///\n{}'.format(
                self.output_text(ncols, raw=True, html=False,
                                 allow_interact=False).strip('\n'))

        if max_out is not None and len(out) > max_out:
            out = out[:max_out] + '...'

        # Get rid of spurious carriage returns
        text = '\n'.join((
            text.strip('\n'), out.strip('\r\n')))

        return text if plain else u'{{{id=%s|\n%s\n}}}' % (
            self.id, text.rstrip('\n'))

    @property
    def plain_text(self):
        return self.format_text()

    @property
    def edit_text(self):
        ur"""
        Returns the text displayed for this compute cell in the Edit
        window.

        INPUT:

        - ``ncols`` - an integer (default: 0); the number of word wrap
          columns

        - ``prompts`` - a boolean (default: False); whether to strip
          interpreter prompts from the beginning of each line

        - ``max_out`` - an integer (default: None); the maximum number
          of characters to return

        OUTPUT:

        - a string

        EXAMPLES::

            sage: C = sagenb.notebook.cell.ComputeCell(0, '2+3', '5', None)
            sage: C.edit_text
            u'{{{id=0|\n2+3\n///\n5\n}}}'
            sage: C = sagenb.notebook.cell.ComputeCell(
                0, 'ěščřžýáíéďĎ', 'ěščřžýáíéďĎ', None)
            sage: C.edit_text
            u'{{{id=0|\n\u011b\u0161\u010d\u0159\u017e\xfd\xe1\xed\xe9\u010f'
            u'\u010e\n///\n\u011b\u0161\u010d\u0159\u017e\xfd\xe1\xed\xe9'
            u'\u010f\u010e\n}}}'
        """
        return self.format_text(plain=False)

    def interrupt(self):
        """
        Sets this compute cell's evaluation as interrupted.

        EXAMPLES::

            sage: nb = sagenb.notebook.notebook.Notebook(
                tmp_dir(ext='.sagenb'))
            sage: nb.user_manager.add_user(
                'sage','sage','sage@sagemath.org',force=True)
            sage: W = nb.create_wst('Test', 'sage')
            sage: C = W.new_cell_after(0, "2^2")
            sage: C.interrupt()
            sage: C.interrupted
            True
            sage: C.evaluated
            False
            sage: nb.delete()
        """
        self.interrupted = True
        self.evaluated = False

    @property
    def computing(self):
        """
        Returns whether this compute cell is queued for evaluation by
        its worksheet object.

        OUTPUT:

        - a boolean

        EXAMPLES::

            sage: nb = sagenb.notebook.notebook.Notebook(
                tmp_dir(ext='.sagenb'))
            sage: nb.user_manager.add_user(
                'sage','sage','sage@sagemath.org',force=True)
            sage: W = nb.create_wst('Test', 'sage')
            sage: C = W.new_cell_after(0, "2^2")
            sage: C.computing
            False
            sage: nb.delete()
        """
        return self in self.worksheet().queue

    def is_interactive_cell(self):
        r"""
        Returns whether this compute cell contains
        :func:`sagenb.notebook.interact.interact` either as a function
        call or decorator.

        OUTPUT:

        - a boolean

        EXAMPLES::

            sage: nb = sagenb.notebook.notebook.Notebook(
                tmp_dir(ext='.sagenb'))
            sage: nb.user_manager.add_user(
                'sage','sage','sage@sagemath.org',force=True)
            sage: W = nb.create_wst('Test', 'sage')
            sage: C = W.new_cell_after(
                0, "@interact\ndef f(a=slider(0,10,1,5):\n    print(a^2)")
            sage: C.is_interactive_cell()
            True
            sage: C = W.new_cell_after(C.id, "2+2")
            sage: C.is_interactive_cell()
            False
            sage: nb.delete()
        """
        # Do *not* cache
        try:
            nodes = ast.parse(self.input.replace('^^', '^'))
        except SyntaxError:
            return False

        void = tuple()
        name = 'interact'
        for node in nodes.body:
            if getattr(getattr(getattr(node, 'value', void), 'func', void),
                       'id', void) == name:
                return True
            for decorator in getattr(node, 'decorator_list', void):
                if getattr(getattr(decorator, 'func', decorator),
                           'id', void) == name:
                    return True
        return False

    def is_auto_cell(self):
        r"""
        Returns whether this compute cell is evaluated automatically
        when its worksheet object starts up.

        OUTPUT:

        - a boolean

        EXAMPLES::

            sage: C = sagenb.notebook.cell.ComputeCell(0, '2+3', '5', None)
            sage: C.is_auto_cell()
            False
            sage: C = sagenb.notebook.cell.ComputeCell(
                0, '#auto\n2+3', '5', None)
            sage: C.is_auto_cell()
            True
        """
        return 'auto' in self.percent_directives

    # New UI

    def basic(self):
        """
        Returns the cell as a python object
        """

        r = {}
        r['id'] = self.id
        r['type'] = 'evaluate'
        r['input'] = self.input
        r['output'] = self.output_text()
        r['output_html'] = self.output_html()
        r['output_wrapped'] = self.output_text(self.word_wrap_cols)
        r['percent_directives'] = self.percent_directives
        r['system'] = self.system
        r['auto'] = self.is_auto_cell()
        r['introspect_output'] = u''
        return r
    # New UI end

    def output_html(self):
        """
        Returns this compute cell's HTML output.

        OUTPUT:

        - a string

        EXAMPLES::

            sage: C = sagenb.notebook.cell.ComputeCell(0, '2+3', '5', None)
            sage: C.output_html()
            ''
            sage: C.set_output_text('5', '<strong>5</strong>')
            sage: C.output_html()
            u'<strong>5</strong>'
        """
        try:
            return self._out_html
        except AttributeError:
            self._out_html = ''
            return ''

    def process_cell_urls(self, urls):
        """
        Processes this compute cell's ``'cell://.*?'`` URLs, replacing
        the protocol with the cell's path and appending the version number
        to prevent cached copies from shadowing the updated copy.

        INPUT:

        - ``urls`` - a string; the URLs to process

        OUTPUT:

        - a string

        EXAMPLES::

            sage: nb = sagenb.notebook.notebook.Notebook(
                tmp_dir(ext='.sagenb'))
            sage: nb.user_manager.add_user(
                'sage','sage','sage@sagemath.org',force=True)
            sage: W = nb.create_wst('Test', 'sage')
            sage: C = sagenb.notebook.cell.ComputeCell(0, '2+3', '5', W)
            sage: C.process_cell_urls('"cell://foobar"')
            '/home/sage/0/cells/0/foobar?...'
        """
        end = '?%d' % self.version
        begin = self.url_to_self()
        for s in re_cell.findall(urls) + re_cell_2.findall(urls):
            urls = urls.replace(s, begin + s[7:-1] + end)
        return urls

    def parse_html(self, s, ncols, pre_wrapping):
        r"""
        Parses HTML for output, escaping and wrapping HTML and
        removing script elements.

        INPUT:

        - ``s`` - a string; the HTML to parse

        - ``ncols`` - an integer; the number of word wrap columns

        - ``pre_wrapping`` -- boolean indicating necessity of wrapping in pre

        OUTPUT:

        - a string

        EXAMPLES::

            sage: nb = sagenb.notebook.notebook.Notebook(
                tmp_dir(ext='.sagenb'))
            sage: nb.user_manager.add_user(
                'sage','sage','sage@sagemath.org',force=True)
            sage: W = nb.create_wst('Test', 'sage')
            sage: C = sagenb.notebook.cell.ComputeCell(0, '2+3', '5', W)
            sage: C.parse_html(
                    '<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01//EN">'
                    '\n<html><head></head><body>Test</body></html>', 80, False)
            '&lt;!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01//EN"&gt;\n<head>
            </head><body>Test</body>'
            sage: C.parse_html(
                    '<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01//EN">'
                    '\n<html><head></head><body>Test</body></html>', 80, True)
            u'<pre class="shrunk">
            &lt;!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01//EN"&gt;\n</pre>
            <head></head><body>Test</body>'
        """
        def format(x):
            x = word_wrap(escape(x), ncols)
            if pre_wrapping:
                x = u'<pre class="shrunk">{}</pre>'.format(x)
            return x

        def format_html(x):
            return self.process_cell_urls(x)

        # If there is an error in the output, specially format it.
        if not self.is_interactive_cell():
            s = format_exception(format_html(s), ncols)

        # Everything not wrapped in <html> ... </html> should be
        # escaped and word wrapped.
        t = ''

        while len(s) > 0:
            i = s.find('<html>')
            if i == -1:
                t += format(s)
                break
            j = s.find('</html>')
            if j == -1:
                t += format(s[:i])
                break
            t += format(s[:i]) + format_html(s[i + 6:j])
            s = s[j + 7:]
        t = t.replace('</html>', '')

        # Get rid of the <script> tags, since we do not want them to
        # be evaluated twice.  They are only evaluated in the wrapped
        # version of the output.
        if ncols == 0:
            t = re_script.sub('', t)
        #  This is a temporary hack
        # re_inline = re.compile('<script type="math/tex">(.*?)</script>')
        # re_display = re.compile(
        #     '<script type="math/tex; mode=display">(.*?)</script>')
        # t = re_inline.sub('<span class="math">\1</span>', t)
        # t = re_display.sub('<div class="math">\1</div>', t)
        # t = t.replace(
        #     '<script type="math/tex">(.*?)</script>',
        #     '<span class="math">\1</span>')
        # t = t.replace('<script type="math/tex; mode=display">(.*?)</script>',
        #               '<div class="math">\1</div>')
        # t = t.replace('<script type="math/tex">', '<span class="math">')
        # t = t.replace('</script>', '</span>')
        return t

    def has_output(self):
        """
        Returns whether this compute cell has any output.

        OUTPUT:

        - a boolean

        EXAMPLES::

            sage: C = sagenb.notebook.cell.ComputeCell(0, '2+3', '5', None)
            sage: C.has_output()
            True
            sage: C = sagenb.notebook.cell.ComputeCell(0, '2+3', '', None)
            sage: C.has_output()
            False
        """
        return len(self.__output.strip()) > 0

    def is_html(self):
        r"""
        Returns whether this is an HTML compute cell, e.g., its system
        is 'html'.  This is typically specified by the percent
        directive ``%html``.

        OUTPUT:

        - a boolean

        EXAMPLES::

            sage: C = sagenb.notebook.cell.ComputeCell(
                0, "%html\nTest HTML", None, None)
            sage: C.system
            u'html'
            sage: C.is_html()
            True
            sage: C = sagenb.notebook.cell.ComputeCell(
                0, "Test HTML", None, None)
            sage: C.is_html()
            False
        """
        return self.system == 'html'

    # Introspection

    @property
    def introspect_html(self):
        """
        Returns this compute cell's introspection text, setting it to
        '', if none is available.

        OUTPUT:

        - a string

        EXAMPLES::

            sage: nb = sagenb.notebook.notebook.Notebook(
                tmp_dir(ext='.sagenb'))
            sage: nb.user_manager.add_user(
                'sage','sage','sage@sagemath.org',force=True)
            sage: W = nb.create_wst('Test', 'sage')
            sage: C = sagenb.notebook.cell.ComputeCell(0, 'sage?', '', W)
            sage: C.introspect
            False
            sage: C.evaluate(username='sage')
            sage: W.check_comp(
                9999)     # random output -- depends on computer speed
            ('d', Cell 0: in=sage?, out=)
            sage: C.introspect_html
            # random output -- depends on computer speed
            u'...<div class="docstring">...sage...</pre></div>...'
            sage: W.quit()
            sage: nb.delete()
        """
        return u'' if not self.introspect else self.__introspect_html

    @introspect_html.setter
    def introspect_html(self, html):
        ur"""
        Sets this compute cell's introspection text.

        INPUT:

        - ``html`` - a string; the updated text

        - ``completing`` - a boolean (default: False); whether the
          completions menu is open

        - ``raw`` - a boolean (default: False)

        EXAMPLES::

            sage: nb = sagenb.notebook.notebook.Notebook(
                tmp_dir(ext='.sagenb'))
            sage: nb.user_manager.add_user(
                'sage','sage','sage@sagemath.org',force=True)
            sage: W = nb.create_wst('Test', 'sage')
            sage: C = sagenb.notebook.cell.ComputeCell(0, 'sage?', '', W)
            sage: C.introspect
            False
            sage: C.evaluate(username='sage')
            sage: W.check_comp(
                9999)     # random output -- depends on computer speed
            ('d', Cell 0: in=sage?, out=)
            sage: C.introspect_html = 'foobar'
            sage: C.introspect_html
            u'foobar'
            sage: C.introspect_html = '`foobar`'
            sage: C.introspect_html
            u'`foobar`'
            sage: C.introspect_html = 'ěščřžýáíéďĎ'
            sage: C.introspect_html
            u'\u011b\u0161\u010d\u0159\u017e\xfd\xe1\xed\xe9\u010f\u010e'
            sage: W.quit()
            sage: nb.delete()
        """
        self.__introspect_html = unicode_str(html)

    def evaluate(self, introspect=False, username=None):
        r"""
        Evaluates this compute cell.

        INPUT:

        - ``introspect`` - a pair [``before_cursor``,
          ``after_cursor``] of strings (default: False)

        - ``username`` - a string (default: None); name of user doing
          the evaluation

        EXAMPLES:

        We create a notebook, worksheet, and cell and evaluate it
        in order to compute `3^5`::

            sage: nb = sagenb.notebook.notebook.load_notebook(
                tmp_dir(ext='.sagenb'))
            sage: nb.user_manager.add_user(
                'sage','sage','sage@sagemath.org',force=True)
            sage: W = nb.create_wst('Test', 'sage')
            sage: W.edit_save('{{{\n3^5\n}}}')
            sage: C = W.cells[0]; C
            Cell 0: in=3^5, out=
            sage: C.evaluate(username='sage')
            sage: W.check_comp(
                wait=9999)     # random output -- depends on computer speed
            ('d', Cell 0: in=3^5, out=
            243
            )
            sage: C     # random output -- depends on computer speed
            Cell 0: in=3^5, out=
            243
            sage: W.quit()
            sage: nb.delete()
        """
        # Cell run through TAB-introspection or S-enter/eval link
        self.eval_method = 'introspect' if introspect else 'eval'
        self.interrupted = False
        self.evaluated = True
        self.introspect = introspect
        self.worksheet().enqueue(self, username=username)
        # TODO:  move to storage backend
        self.delete_files()

    @property
    def time(self):
        r"""
        Returns whether to print timing information about the
        evaluation of this compute cell.

        OUTPUT:

        - a boolean

        EXAMPLES::

            sage: C = sagenb.notebook.cell.ComputeCell(0, '2+3', '5', None)
            sage: C.time
            False
            sage: C = sagenb.notebook.cell.ComputeCell(
                0, '%time\n2+3', '5', None)
            sage: C.time
            True
        """
        return ('time' in self.percent_directives or
                'timeit' in self.percent_directives)

    def html(self, wrap=None, div_wrap=True, do_print=False, publish=False):
        r"""
        Returns the HTML for this compute cell.

        INPUT:

        - ``wrap`` - an integer (default: None); the number of word
          wrap columns

        - ``div_wrap`` - a boolean (default: True); whether to wrap
          the output in outer div elements

        - ``do_print`` - a boolean (default: False); whether to return
          output suitable for printing

        - ``publish`` - a boolean (default: False); whether to render
          a published cell

        OUTPUT:

        - a string

        EXAMPLES::

            sage: nb = sagenb.notebook.notebook.load_notebook(
                tmp_dir(ext='.sagenb'))
            sage: nb.user_manager.add_user(
                'sage','sage','sage@sagemath.org',force=True)
            sage: W = nb.create_wst('Test', 'sage')
            sage: C = sagenb.notebook.cell.ComputeCell(0, '2+3', '5', W)
            sage: C.html()
            u'...cell_outer_0...2+3...5...'
        """
        if wrap is None:
            wrap = self.word_wrap_cols

        return render_template(os.path.join('html', 'notebook', 'cell.html'),
                               cell=self, wrap=wrap, div_wrap=div_wrap,
                               do_print=do_print, publish=publish)

    def url_to_self(self):
        """
        Returns a notebook URL for this compute cell.

        OUTPUT:

        - a string

        EXAMPLES::

            sage: nb = sagenb.notebook.notebook.Notebook(
                tmp_dir(ext='.sagenb'))
            sage: nb.user_manager.add_user(
                'sage','sage','sage@sagemath.org',force=True)
            sage: W = nb.create_wst('Test', 'sage')
            sage: C = sagenb.notebook.cell.ComputeCell(0, '2+3', '5', W)
            sage: C.url_to_self()
            '/home/sage/0/cells/0'
        """
        try:
            return self._url_to_self
        except AttributeError:
            self._url_to_self = '/home/%s/cells/%s' % (
                self.worksheet_filename(), self.id)
            return self._url_to_self

    def url_to_worksheet(self):
        """
        Returns a URL for the worksheet

        OUTPUT:

        - a string

        EXAMPLES::

            sage: nb = sagenb.notebook.notebook.Notebook(
                tmp_dir(ext='.sagenb'))
            sage: nb.user_manager.add_user(
                'sage','sage','sage@sagemath.org',force=True)
            sage: W = nb.create_wst('Test', 'sage')
            sage: C = sagenb.notebook.cell.ComputeCell(0, '2+3', '5', W)
            sage: C.url_to_worksheet()
            '/home/sage/0'
        """
        return '/home/{0}'.format(self.worksheet_filename())

    def directory(self):
        """
        Returns the name of this compute cell's directory, creating
        it, if it doesn't already exist.

        OUTPUT:

        - a string

        EXAMPLES::

            sage: nb = sagenb.notebook.notebook.Notebook(
                tmp_dir(ext='.sagenb'))
            sage: nb.user_manager.add_user(
                'sage','sage','sage@sagemath.org',force=True)
            sage: W = nb.create_wst('Test', 'sage')
            sage: C = sagenb.notebook.cell.ComputeCell(0, '2+3', '5', W)
            sage: C.directory()
            '.../home/sage/0/cells/0'
            sage: nb.delete()
        """
        # TODO:  move to storage backend
        dir = self._directory_name()
        if not os.path.exists(dir):
            os.makedirs(dir)
        set_restrictive_permissions(dir)
        return dir

    def _directory_name(self):
        """
        Returns the name of this compute cell's directory.

        OUTPUT:

        - a string

        EXAMPLES::

            sage: nb = sagenb.notebook.notebook.Notebook(
                tmp_dir(ext='.sagenb'))
            sage: nb.user_manager.add_user(
                'sage','sage','sage@sagemath.org',force=True)
            sage: W = nb.create_wst('Test', 'sage')
            sage: C = sagenb.notebook.cell.ComputeCell(0, '2+3', '5', W)
            sage: C._directory_name()
            '.../home/sage/0/cells/0'
            sage: nb.delete()
        """
        # TODO:  move to storage backend
        return os.path.join(self.worksheet().directory, 'cells',
                            str(self.id))

    def files(self):
        """
        Returns a list of all the files in this compute cell's
        directory.

        OUTPUT:

        - a list of strings

        EXAMPLES::

            sage: nb = sagenb.notebook.notebook.Notebook(
                tmp_dir(ext='.sagenb'))
            sage: nb.user_manager.add_user(
                'sage','sage','sage@sagemath.org',force=True)
            sage: W = nb.create_wst('Test', 'sage')
            sage: C = sagenb.notebook.cell.ComputeCell(
                0, 'plot(sin(x),0,5)', '', W)
            sage: C.evaluate()
            sage: W.check_comp(
                wait=9999)     # random output -- depends on computer speed
            ('d', Cell 0: in=plot(sin(x),0,5), out=
            <html><font color='black'><img src='cell://sage0.png'></font>
            </html>
            <BLANKLINE>
            )
            sage: C.files()     # random output -- depends on computer speed
            ['sage0.png']
            sage: W.quit()
            sage: nb.delete()
        """
        # TODO:  move to storage backend
        dir = self.directory()
        D = os.listdir(dir)
        return D

    def delete_files(self):
        """
        Deletes all of the files associated with this compute cell.

        EXAMPLES::

            sage: nb = sagenb.notebook.notebook.Notebook(
                tmp_dir(ext='.sagenb'))
            sage: nb.user_manager.add_user(
                'sage','sage','sage@sagemath.org',force=True)
            sage: W = nb.create_wst('Test', 'sage')
            sage: C = sagenb.notebook.cell.ComputeCell(
                0, 'plot(sin(x),0,5)', '', W)
            sage: C.evaluate()
            sage: W.check_comp(
                wait=9999)     # random output -- depends on computer speed
            ('d', Cell 0: in=plot(sin(x),0,5), out=
            <html><font color='black'><img src='cell://sage0.png'></font>
            </html>
            <BLANKLINE>
            )
            sage: C.files()     # random output -- depends on computer speed
            ['sage0.png']
            sage: C.delete_files()
            sage: C.files()
            []
            sage: W.quit()
            sage: nb.delete()
        """
        # TODO:  move to storage backend
        dir = self._directory_name()
        if os.path.exists(dir):
            shutil.rmtree(dir, ignore_errors=True)

    def files_html(self, out):
        """
        Returns HTML to display the files in this compute cell's
        directory.

        INPUT:

        - ``out`` - a string; files to exclude.  To exclude bar, foo,
          ..., use the format ``'cell://bar cell://foo ...'``

        OUTPUT:

        - a string

        EXAMPLES::

            sage: nb = sagenb.notebook.notebook.Notebook(
                tmp_dir(ext='.sagenb'))
            sage: nb.user_manager.add_user(
                'sage','sage','sage@sagemath.org',force=True)
            sage: W = nb.create_wst('Test', 'sage')
            sage: C = sagenb.notebook.cell.ComputeCell(
                0, 'plot(sin(x),0,5)', '', W)
            sage: C.evaluate()
            sage: W.check_comp(
                wait=9999)     # random output -- depends on computer speed
            ('d', Cell 0: in=plot(sin(x),0,5), out=
            <html><font color='black'><img src='cell://sage0.png'></font>
            </html>
            <BLANKLINE>
            )
            sage: C.files_html(
                '')     # random output -- depends on computer speed
            '<img src="/home/sage/0/cells/0/sage0.png?...">'
            sage: W.quit()
            sage: nb.delete()
        """
        D = self.files()
        D.sort()
        if len(D) == 0:
            return ''
        images = []
        files = []
        # Flags to allow processing of old worksheets that include Jmol
        hasjmol = False
        hasjmolimages = False
        # The question mark trick here is so that images will be
        # reloaded when the async request requests the output text for
        # a computation.  This is inspired by
        # http://www.irt.org/script/416.htm/.
        for F in D:
            if 'cell://%s' % F in out:
                continue
            url = os.path.join(self.url_to_self(), F)
            if (F.endswith('.png') or F.endswith('.bmp') or
                    F.endswith('.jpg') or F.endswith('.gif')):
                images.append('<img src="%s?%d">' % (url, time.time()))
            elif F.endswith('.obj'):
                images.append(
                    '<a href="javascript:sage3d_show(\'%s\', \'%s_%s\', '
                    '\'%s\');">Click for interactive view.</a>' % (
                        url, self.id, F, F[:-4]))
            elif F.endswith('.mtl') or F.endswith(".objmeta"):
                pass  # obj data
            elif F.endswith('.svg'):
                images.append(
                    '<embed src="%s" type="image/svg+xml" name="emap">' % url)
            elif F.endswith('.jmol'):
                hasjmol = True
            elif F.endswith('.canvas3d'):
                script = (
                    '<div><script>canvas3d.viewer("%s?%s");</script></div>' % (
                        url, time.time()))
                images.append(script)
            elif F.startswith('.jmol_'):
                # static jmol data and images
                hasjmolimages = True
            else:
                link_text = str(F)
                if len(link_text) > 40:
                    link_text = link_text[:10] + '...' + link_text[-20:]
                files.append(
                    '<a target="_new" href="%s" class="file_link">%s</a>' % (
                        url, link_text))

        if(hasjmol and not hasjmolimages):
            images.append(
                'Cannot make image '
                'from old data. Please reevaluate cell.')

        if len(images) == 0:
            images = ''
        else:
            images = "%s" % '<br>'.join(images)
        if len(files) == 0:
            files = ''
        else:
            files = ('&nbsp' * 3).join(files)

        files = unicode_str(files)
        images = unicode_str(images)
        return images + files
