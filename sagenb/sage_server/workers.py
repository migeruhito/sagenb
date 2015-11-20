from __future__ import absolute_import

import random

from .interfaces import SageServerReference
from .interfaces import SageServerExpect
from .interfaces import SageServerExpectRemote
from .interfaces import ProcessLimits


def sage(server_pool=None, max_vmem=None, max_walltime=None,
         max_processes=None, use_reference=False, python='sage -python',
         init_code=None):
    """
    sage process factory
    """
    if use_reference:
        return SageServerReference()

    process_limits = ProcessLimits(max_vmem=max_vmem,
                                   max_walltime=max_walltime,
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
