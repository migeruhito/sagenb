from __future__ import absolute_import

import random

from .interfaces import WorksheetProcess_ReferenceImplementation
from .interfaces import WorksheetProcess_ExpectImplementation
from .interfaces import WorksheetProcess_RemoteExpectImplementation
from .interfaces import ProcessLimits


def sage(server_pool=None, max_vmem=None, max_walltime=None,
         max_processes=None, use_reference=False, python='sage -python'):
    """
    sage process factory
    """
    if use_reference:
        return WorksheetProcess_ReferenceImplementation()

    process_limits = ProcessLimits(max_vmem=max_vmem,
                                   max_walltime=max_walltime,
                                   max_processes=max_processes)

    if server_pool is None or len(server_pool) == 0:
        return WorksheetProcess_ExpectImplementation(
            process_limits=process_limits)
    else:
        user_at_host = random.choice(server_pool)
        return WorksheetProcess_RemoteExpectImplementation(
            user_at_host=user_at_host,
            process_limits=process_limits,
            remote_python=python)
