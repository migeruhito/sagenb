"""
Documentation functions

URLS to do:

###/doc/live/   - WorksheetFile(os.path.join(DOC, name)
###/doc/static/ - DOC/index.html
"""
from __future__ import absolute_import
from __future__ import print_function
from __future__ import division

import os
from flask import Blueprint
from flask import g
from flask_babel import gettext
from flask.helpers import send_from_directory

from ..config import SAGE_DOC
from ..config import SAGE_VERSION
from ..util.decorators import login_required
from ..util.templates import message as message_template
from ..util.templates import render_template
from .worksheet import worksheet_file

_ = gettext

doc = Blueprint('doc', __name__)

DOC = os.path.join(SAGE_DOC, 'output', 'html', 'en')


@doc.route('/static/', defaults={'filename': 'index.html'})
@doc.route('/static/<path:filename>')
def static(filename):
    return send_from_directory(DOC, filename)


@doc.route('/live/')
@doc.route('/live/<manual>/<path:path_static>/_static/<path:filename>')
@doc.route('/live/<path:filename>')
@login_required
def live(filename=None, manual=None, path_static=None):
    """
    The docs reference a _static URL in the current directory, even if
    the real _static directory only lives in the root of the manual.
    This function strips out the subdirectory part and returns the
    file from the _static directory in the root of the manual.

    This seems like a Sphinx bug: the generated html file should not
    reference a _static in the current directory unless there actually
    is a _static directory there.

    TODO: Determine if the reference to a _static in the current
    directory is a bug in Sphinx, and file a report or see if it has
    already been fixed upstream.
    """
    if filename is None:
        return message_template(_('nothing to see.'), username=g.username)
    if path_static is not None:
        path_static = os.path.join(DOC, manual, '_static')
        return send_from_directory(path_static, filename)

    if filename.endswith('.html'):
        filename = os.path.join(DOC, filename)
        return worksheet_file(filename)
    else:
        return send_from_directory(DOC, filename)


# Help

notebook_help = [
    (_('Find Help and Documentation'),
     [(_('Get Started with Sage'),
       _('<a href="/doc/live/tutorial/index.html">Work through the tutorial'
         '</a> (if you have trouble with it, view the '
         '<a href="/doc/static/tutorial/index.html">static version</a>).')),
      (_('Help About'),
       _('Type ? immediately after the object or function and press tab or '
         'shift-enter (shift-enter overwrites output and saves to '
         'worksheet).  Doing this twice or more toggles with formatted source '
         'code.')),
      (_('Source Code'),
       _('Put ?? after the object and press tab or shift-enter (shift-enter '
           'overwrites output and saves to worksheet).  Doing this twice or '
           'more toggles with just the documentation.')),
      (_('Full Text Search of Docs and Source'),
       _('Search the SAGE documentation by typing <pre>search_doc("my query")'
         '</pre> in an input cell and press shift-enter.  Search the source '
         'code of SAGE by typing <pre>search_src("my query")</pre> and '
         'pressing shift-enter.  Arbitrary regular expressions are allowed as '
         'queries.')),
      (_('Live Documentation'),
       _('Use <a href="/doc/live/index.html">live documentation</a> to try '
         'out the full Sage documentation "live". (Only new compute cells '
         'allowed, click the icon.)')),
      # ('More Help',
      #  'Type "help(sagenb.notebook.notebook)" for a detailed discussion of '
      #  'the architecture of the SAGE notebook and a tutorial (or see the '
      #  'SAGE reference manual).'),
      ]
     ),
    (_('Key and Mouse Bindings'),
     [(_('Evaluate Input'),
       _('Press <strong>shift-enter</strong> or click the "evaluate" button.  '
         'You can start several calculations at once.  If you press '
         '<strong>alt-enter</strong> instead, then a new cell is created '
         'after the current one.  If you press <strong>ctrl-enter</strong> '
         'then the cell is split and both pieces are evaluated separately.')),
      (_('Tab Completion'),
       _('Press <strong>tab</strong> while the cursor is on an identifier. '
         'On some web browsers (e.g., Opera) you must use control-space '
         'instead of tab.')),
      (_('Insert New Cell'),
       _('Put the mouse between an output and input until the blue horizontal '
         'line appears and click, or click the "plus" icon.  If you press '
         'Alt-Enter in a cell, the cell is evaluated and a new cell is '
         'inserted after it.')),
      (_('Delete Cell'),
       _('Delete all cell contents, then press <strong>backspace</strong>.')),
      (_('Split and Join Cells'),
       _('Press <strong>ctrl-;</strong> in a cell to split it into two cells, '
           'and <strong>ctrl-backspace</strong> to join them.  Press '
           '<strong>ctrl-enter</strong> to split a cell and evaluate both '
           'pieces.')),
      (_('Insert New Text Cell'),
       _('Move the mouse between cells until a blue bar appears.  '
         '<strong>Shift-click</strong> on the blue bar, or click on the '
         'text bubble icon, to create a new text cell.  Use $...$ and $$...$$ '
         'to include typeset math in the text block.  Click the button to '
         'save changes, or press <strong>shift-enter</strong>.')),
      (_('Edit Text Cell'),
       _('Double click on existing text to edit it.')),
      (_('Hide/Show Output'),
       _('Click on the left side of output to toggle between hidden, shown '
         'with word wrap, and shown without word wrap.')),
      (_('Indenting Blocks'),
       _('Highlight text and press > to indent it all and < to unindent it '
         'all (works in Safari and Firefox).  In Firefox you can also press '
         'tab and shift-tab.')),
      (_('Comment/Uncomment Blocks'),
       _('Highlight text and press <strong>ctrl-.</strong> to comment it and '
         '<strong>ctrl-,</strong> to uncomment it. As an alternative '
         '(necessary in some browsers), use <strong>ctrl-3</strong> and '
         '<strong>ctrl-4</strong>.')),
      (_('Paren matching'),
       _('To fix unmatched or mis-matched parentheses, braces or brackets, '
         'press <strong>ctrl-0</strong>.  Parentheses before the cursor will '
         'be matched, minding strings and (Python) comments.')),
      # ('Emacs Keybindings',
      #  'If you are using GNU/Linux, you can change (or create) a '
      #  '<tt>.gtkrc-2.0</tt> file.  Add the line <tt>gtk-key-theme-name = '
      #  '"Emacs"</tt> to it.  See <a target="_blank" '
      #  'href="http://kb.mozillazine.org/Emacs_Keybindings_(Firefox)">'
      #  'this page</a> [mozillazine.org] for more details.'),
      ]),
    (_('Interrupt and Restart Sessions'),
     [(_('Interrupt Running Calculations'),
       _('Click <u>Interrupt</u> or press escape in any input cell. This will '
         '(attempt) to interrupt SAGE by sending many interrupt signals.')),
      (_('Restart'),
       _('Type "restart" to restart the SAGE interpreter for a given '
         'worksheet.  (You have to interrupt first.)')),
      ]),
    (_('Special Cell Blocks'),
     [(_('Evaluate Cell using GAP, Singular, etc.'),
       _('Put "%%gap", "%%singular", etc. as the first input line of a cell; '
         'the rest of the cell is evaluated in that system.')),
      (_('Shell Scripts'),
       _('Begin a block with %%sh to have the rest of the block evaluated as '
         'a shell script.  The current working directory is maintained.')),
      (_('Interactive Dynamic Widgets'),
       _('Put @interact on the line before a function definition.  Type '
         'interact? for more details.')),
      (_('Autoevaluate Cells on Load'),
       _('Any cells with "#auto" in the input is automatically evaluated when '
         'the worksheet is first opened.')),
      (_('Time'),
       _('Type "%%time" at the beginning of the cell.')),
      ]),
    (_('Useful Tips'),
     [(_('Input Rules'),
       _("Code is evaluated by exec'ing (after preparsing).  Only the output "
         "of the last line of the cell is implicitly printed.  If any line "
         "starts with \"sage:\" or \">>>\" the entire block is assumed to "
         "contain text and examples, so only lines that begin with a prompt "
         "are executed.   Thus you can paste in complete examples from the "
         "docs without any editing, and you can write input cells that "
         "contains non-evaluated plain text mixed with examples by starting "
         "the block with \">>>\" or including an example.")),
      (_('History'),
       _('Click <a href="/history">log</a> commands you have entered in any '
         'worksheet of this notebook.')),
      (_('Typesetting All Output'),
       _('Type pretty_print_default() in an input cell and press '
         'shift-enter.  All future output will be typeset automatically.')),
      ]),
    (_('Files and Scripts'),
     [(_('Loading SAGE/Python Scripts'),
       _('Use "load filename.sage" and "load filename.py".  Load is relative '
         'to the path you started the notebook in.  The .sage files are '
         'preparsed and .py files are not.   You may omit the .sage or .py '
         'extension.  Files may load other files.')),
      (_('Attaching Scripts'),
       _('(Currently no different from "load", see <a '
         'href="https://github.com/sagemath/sagenb/issues/169" '
         'target="_blank">bug report</a>) Use "attach filename.sage" or '
         '"attach filename.py".  Attached files are automatically reloaded '
         'when the file changes.  The file $HOME/.sage/init.sage is attached '
         'on startup if it exists.')),
      (_('Working Directory'),
       _('Each block of code is run from its own directory.  If any images '
         'are created as a side effect, they will automatically be '
         'displayed.')),
      (_('DIR Variable'),
       _('The variable DIR contains the directory from which you started the '
         'SAGE notebook.  For example, to open a file in that directory, do '
         '"open(DIR+\'filename\')".')),
      (_('DATA Variable'),
       _('Use the Data menu to upload images and other files, and create new '
         'files that can be shared between worksheets.  The DATA variable '
         'contains the path to the data files.  For example, to open a file '
         'in that directory, do "open(DATA+\'filename\')".  If foo.sage is a '
         'Sage file that you uploaded, type "load foo.sage"; if foo.py is a '
         'Python file, you can import it by typing "import foo".')),
      (_('Loading and Saving Objects'),
       _('Use "save(obj1,DATA+\'foo\')" to save an object to the data '
         'directory of a worksheet, and "obj1 = load(DATA+\'foo\')" to load '
         'it again.  To use such objects between worksheets, you may save to '
         'any filename (given as a string) Sage can write to on your '
         'system.')),
      (_('Loading and Saving Sessions'),
       _('Use "save_session(\'name\')" to save all variables to an object.  '
         'Use "load_session(\'name\')" to <i>merge</i> in all variables from '
         'a saved session.')),
      (_('Customizing the Notebook'),
       _('Sage Notebook comes with several built-in themes. If you create'
         'a <tt>$HOME/.sage/themes</tt> directory, you can populate it with '
         'your own custom themes. To get started, follow the steps below.'
         '<ul><li> Copy from <tt>SAGE_ROOT/devel/sagenb/sagenb/themes/</tt> '
         'one of the built-in temes (other than <tt>Default</tt>) to '
         '<tt>$HOME/.sage/themes</tt>.</li>'
         '<li>Change the copied directory name as desired '
         '(e.g. my_fancy_theme). Spaces are not allowed.</li>'
         '<li>Edit <tt>SAGE_ROOT/devel/sagenb/sagenb/themes/my_fancy_theme/'
         'info.json</tt> '
         'and set the <tt>identifier</tt> field to the directory\'s name of '
         'the theme (e.g. my_fancy_theme). Do not change the '
         '<tt>application</tt> field.</li>'
         '<li>Hack on it. Great results may be attained by only changing css '
         'files. For extensive changes in the template system, some knowledge '
         'of notebook internals is needed. If your notebook becomes totally '
         'broken, remove the disturbing theme from your themes directory and '
         'restart your notebook. '
         '</li></ul>'))
      ])
]


@doc.route('/help')
@login_required
def help():
    return render_template(
        os.path.join('html', 'docs.html'), username=g.username,
        notebook_help=notebook_help, sage_version=SAGE_VERSION)
