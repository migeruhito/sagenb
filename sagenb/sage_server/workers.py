"""
sage_server workers

AUTHORS:

  - J Miguel Farto
"""

#############################################################################
#
#       Copyright (C) 2015 J Miguel Farto <jmfarto@gmail.com>
#  Distributed under the terms of the GNU General Public License (GPL)
#  The full text of the GPL is available at:
#                  http://www.gnu.org/licenses/
#
#############################################################################

from __future__ import absolute_import

import os
import random

from .interfaces import SageServerExpect
from .interfaces import SageServerExpectRemote
from .interfaces import ProcessLimits


def sage(server_pool=None, max_vmem=None, max_walltime=None, max_cputime=None,
         max_processes=None, python='sage -python',
         init_code=None):
    """
    sage process factory
    """
    sage_code = os.path.join(os.path.split(__file__)[0], 'sage_code')

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
            remote_python=python, init_code=init_code, sage_code=sage_code)
