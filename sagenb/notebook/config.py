# -*- coding: utf-8 -*
r"""
Notebook Keybindings

This module is responsible for setting the keyboard bindings for the notebook. 

These are the standard key and mouse bindings available in the
notebook:

- *Evaluate Input:* Press **shift-enter**. You can start several calculations at once. If you press **alt-enter** instead, then a new cell is created after the current one. If you press **ctrl-enter** then the cell is split and both pieces are evaluated separately.

..

- *Tab Completion:* Press **tab** while the cursor is on an identifier. On some web browsers (e.g., Opera) you must use control-space instead of tab.

..

- *Insert New Cell:* Put the mouse between an output and input until the horizontal line appears and click. If you press Alt-Enter in a cell, the cell is evaluated and a new cell is inserted after it.

..

- *Delete Cell:* Delete all cell contents, then press **backspace**.

..

- *Split and Join Cells:* Press **ctrl-;** in a cell to split it into two cells, and **ctrl-backspace** to join them. Press **ctrl-enter** to split a cell and evaluate both pieces.

..

- *Insert New HTML Cell:* Shift click between cells to create a new HTML cell. Double click on existing HTML to edit it. Use \$...\$ and \$\$...\$\$ to include typeset math in the HTML block.

..

- *Hide/Show Output:* Click on the left side of output to toggle between hidden, shown with word wrap, and shown without word wrap.

..

- *Indenting Blocks:* Highlight text and press **>** to indent it all and **<** to unindent it all (works in Safari and Firefox). In Firefox you can also press tab and shift-tab.

..

- *Comment/Uncomment Blocks:* Highlight text and press **ctrl-.** to comment it and **ctrl-,** to uncomment it. Alternatively, use **ctrl-3** and **ctrl-4**.

..

- *Parenthesis matching:* To fix unmatched or mis-matched parentheses, braces or brackets, press **ctrl-0**.  Parentheses, brackets or braces to the left of or above the cursor will be matched, minding strings and comments.  Note, only Python comments are recognized, so this won\'t work for c-style multiline comments, etc.

"""

#############################################################################
#       Copyright (C) 2007 William Stein <wstein@gmail.com>
#  Distributed under the terms of the GNU General Public License (GPL)
#  The full text of the GPL is available at:
#                  http://www.gnu.org/licenses/
#############################################################################
from __future__ import absolute_import


KEYS=(
('request_introspections', {'key': "KEY_SPC", 'ctrl': True}),  # control space
('request_introspections', {'key': "KEY_TAB", 'shift': False}),  # tab
('indent', {'key': "KEY_TAB", 'shift': False}),  # tab
('indent', {'key': "KEY_GT", 'shift': False}),  # tab
('unindent', {'key': "KEY_TAB", 'shift': True}),  # tab
('unindent', {'key': "KEY_LT", 'shift': False}), 
('request_history', {'key': "KEY_Q", 'ctrl': True}),
('request_history', {'key': "KEY_QQ", 'ctrl': True}),
('request_log', {'key': "KEY_P", 'ctrl': True}),
('request_log', {'key': "KEY_PP", 'ctrl': True}),
('close_helper', {'key': "KEY_ESC"}),
('interrupt', {'key': "KEY_ESC"}),
('send_input', {'key': "KEY_RETURN", 'shift': True}),
('send_input', {'key': "KEY_ENTER", 'shift': True}),
('send_input_newcell', {'key': "KEY_RETURN", 'alt': True}),
('send_input_newcell', {'key': "KEY_ENTER", 'alt': True}),
('prev_cell', {'key': "KEY_UP", 'ctrl' : True}),
('next_cell', {'key': "KEY_DOWN", 'ctrl' : True}),
('page_up', {'key': "KEY_PGUP"}),
('page_down', {'key': "KEY_PGDN"}),
('delete_cell', {'key': "KEY_BKSPC"}),
('generic_submit', {'key': "KEY_ENTER"}),
('up_arrow', {'key': "KEY_UP"}),
('down_arrow', {'key': "KEY_DOWN"}),
('comment', {'key': "KEY_DOT", 'ctrl': True}),
('uncomment', {'key': "KEY_COMMA", 'ctrl': True}),
('comment', {'key': "KEY_3", 'ctrl': True}),
('uncomment', {'key': "KEY_4", 'ctrl': True}),
('fix_paren', {'key': "KEY_0", 'ctrl': True}),

('control', {'key': "KEY_CTRL"}),
('backspace', {'key': "KEY_BKSPC"}),
('enter', {'key': "KEY_ENTER"}),
('enter', {'key': "KEY_RETURN"}),
('enter_shift', {'key': "KEY_ENTER", 'shift': True}),
('enter_shift', {'key': "KEY_RETURN", 'shift': True}),
('spliteval_cell', {'key': "KEY_ENTER", 'ctrl': True}),
('spliteval_cell', {'key': "KEY_RETURN",'ctrl': True}),
('spliteval_cell', {'key': "KEY_CTRLENTER", 'ctrl': True}),  # needed on OS X Firefox
('join_cell', {'key': "KEY_BKSPC", 'ctrl': True}),
('split_cell', {'key': "KEY_SEMI", 'ctrl': True}),
('split_cell_noctrl', {'key': "KEY_SEMI"}),

('menu_left', {'key': "KEY_LEFT"}),
('menu_up', {'key': "KEY_UP"}),
('menu_right', {'key': "KEY_RIGHT"}),
('menu_down', {'key': "KEY_DOWN"}),
('menu_pick', {'key': "KEY_ENTER"}),
('menu_pick', {'key': "KEY_RETURN"}),
)

"""
8  -- backspace
9  -- tab
13 -- return
27 -- esc
32 -- space
37 -- left
38 -- up
39 -- right
40 -- down
"""
