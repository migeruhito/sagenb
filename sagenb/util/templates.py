from __future__ import absolute_import

import os
from ..notebook.themes import render_template

def message(msg, cont='/', username=None, **kwds):
    """Returns an error message to the user."""
    template_dict = {'msg': msg, 'cont': cont, 'username': username}
    template_dict.update(kwds)
    return render_template(os.path.join('html', 'error_message.html'),
                           **template_dict)


