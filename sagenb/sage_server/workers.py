from __future__ import absolute_import

import random

from .interfaces import SageServerReference
from .interfaces import SageServerExpect
from .interfaces import SageServerExpectRemote
from .interfaces import ProcessLimits

sage_init_code_tpt = '\n'.join((
    'import sagenb.notebook.interact as _interact_'
    '  # for setting current cell id',
    '',
    '_support_.init(None, globals())',
    '',
    '# The following is Sage-specific -- this immediately bombs out if sage '
    'isn\'t',
    '# installed.',
    'from sage.all_notebook import *',
    'sage.plot.plot.EMBEDDED_MODE=True',
    'sage.misc.latex.EMBEDDED_MODE=True',
    '# TODO: For now we take back sagenb interact; do this until the sage '
    'notebook',
    '# gets removed from the sage library.',
    'from sagenb.notebook.all import *',
    'try:',
    '    load(os.path.join(os.environ["DOT_SAGE"], "init.sage"),',
    '         globals())',
    'except (KeyError, IOError):',
    '    pass',))


def sage(server_pool=None, max_vmem=None, max_walltime=None, max_cputime=None,
         max_processes=None, use_reference=False, python='sage -python',
         init_code=None):
    """
    sage process factory
    """
    init_code = sage_init_code_tpt.format(
        '' if init_code is None else init_code)
    if use_reference:
        return SageServerReference()

    process_limits = ProcessLimits(max_vmem=max_vmem,
                                   max_walltime=max_walltime,
                                   max_cputime=max_cputime,
                                   max_processes=max_processes)

    if server_pool is None or len(server_pool) == 0:
        return SageServerExpect(
            process_limits=process_limits, init_code=init_code)
    else:
        user_at_host = random.choice(server_pool)
        return SageServerExpectRemote(
            user_at_host=user_at_host,
            process_limits=process_limits,
            remote_python=python, init_code=init_code)
