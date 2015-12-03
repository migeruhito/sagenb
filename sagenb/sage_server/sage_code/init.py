# ## Adapted from sage.all_notebook
from sage.all import *
from sage.calculus.predefined import x
from sage.misc.python import python
from sage.misc.html import html
from support import help, automatic_names

sage_mode = 'notebook'

from sage.misc.latex import Latex, pretty_print_default, MathJax
latex = Latex(density=130)
latex_debug = Latex(debug=True, density=130)
slide = Latex(slide=True, density=256)
slide_debug = Latex(slide=True, debug=True, density=256)
pdflatex = Latex(density=130, pdflatex=True)
pdflatex_debug = Latex(density=130, pdflatex=True, debug=True)

# # Set user globals to notebook worksheet globals
# from sage.repl.user_globals import set_globals
# set_globals(sys._getframe(1).f_globals)

sage.misc.session.init()
# ## END sage.all_notebook

# TODO: Sagenb dependency.
# ## Extracted from sagenb.all
# from sagenb.notebook.sage_email import email ## included in sage.all
# from sagenb.notebook.interact import interact  ## included in sage.all
from sagenb.notebook.interact import input_box
from sagenb.notebook.interact import slider
from sagenb.notebook.interact import range_slider
from sagenb.notebook.interact import selector
from sagenb.notebook.interact import checkbox
from sagenb.notebook.interact import input_grid
from sagenb.notebook.interact import text_control
from sagenb.notebook.interact import color_selector
# For doctesting.
import sagenb
# ## END sagenb.all

# TODO: Sagenb dependency
import sagenb.notebook.interact as _interact_ # for setting current cell id

import support as _support_
_support_.init(None, globals())

# The following is Sage-specific -- this immediately bombs out if sage isn't
# installed.
sage.plot.plot.EMBEDDED_MODE = True
sage.misc.latex.EMBEDDED_MODE = True
try:
    load(os.path.join(os.environ["DOT_SAGE"], "init.sage"),
         globals())
except (KeyError, IOError):
    pass
