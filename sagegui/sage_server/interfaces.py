# -*- coding: utf-8 -*
"""
sage_server interfaces

AUTHORS:

  - William Stein

  - J Miguel Farto
"""

#############################################################################
#
#       Copyright (C) 2009 William Stein <wstein@gmail.com>
#       Copyright (C) 2015 J Miguel Farto <jmfarto@gmail.com>
#  Distributed under the terms of the GNU General Public License (GPL)
#  The full text of the GPL is available at:
#                  http://www.gnu.org/licenses/
#
#############################################################################

from __future__ import absolute_import
from __future__ import print_function
from __future__ import division
from __future__ import unicode_literals

import os
import re
import shutil
import stat
import tempfile
from time import time as walltime

from base64 import b64encode

import pexpect


class SageServerABC(object):
    """
    A controlled Python process that executes code.  This is a
    reference implementation.
    """

    def __init__(self, **kwds):
        """
        Initialize this worksheet process.
        """
        raise NotImplementedError

    def __repr__(self):
        """
        Return string representation of this worksheet process.
        """
        return "Worksheet process"

    def __getstate__(self):
        """
        Used for pickling.  We return an empty state otherwise
        this could not be pickled.
        """
        return {}

    def interrupt(self):
        """
        Send an interrupt signal to the currently running computation
        in the controlled process.  This may or may not succeed.  Call
        ``self.is_computing()`` to find out if it did.
        """
        raise NotImplementedError

    def quit(self):
        """
        Quit this worksheet process.
        """
        raise NotImplementedError

    def start(self):
        """
        Start this worksheet process running.
        """
        raise NotImplementedError

    def update(self):
        """
        Update this worksheet process
        """
        # default implementation is to do nothing.

    def is_computing(self):
        """
        Return True if a computation is currently running in this worksheet
        subprocess.

        OUTPUT:

            - ``bool``
        """
        raise NotImplementedError

    def is_started(self):
        """
        Return true if this worksheet subprocess has already been started.

        OUTPUT:

            - ``bool``
        """
        raise NotImplementedError

    def execute(self, string, data=None):
        """
        Start executing the given string in this subprocess.

        INPUT:

            - ``string`` -- a string containing code to be executed.

            - ``data`` -- a string or None; if given, must specify an
              absolute path on the server host filesystem.   This may
              be ignored by some worksheet process implementations.

        """
        raise NotImplementedError

    def output_status(self):
        """
        Return OutputStatus object, which includes output from the
        subprocess from the last executed command up until now,
        information about files that were created, and whether
        computing is now done.

        OUTPUT:

            - ``OutputStatus`` object.
        """
        raise NotImplementedError


class SageServerExpect(SageServerABC):
    """
    A controlled Python process that executes code using expect.

    INPUT:
        - ``process_limits`` -- None or a ProcessLimits objects as defined by
          the ``sagenb.interfaces.ProcessLimits`` object.
    """

    modes = ['raw', 'python', 'sage']

    def __init__(self,
                 process_limits=None,
                 timeout=0.05,
                 python='sage --python',
                 init_code=None,
                 sage_code=None):
        """
        Initialize this worksheet process.
        """
        self._output_status = OutputStatus('', [], True)
        self._expect = None
        self._is_started = False
        self._is_computing = True
        self._timeout = timeout
        self._prompt = "__SAGE__"
        self._all_tempdirs = []
        self._process_limits = process_limits
        self._max_walltime = None
        self._start_walltime = None
        self._data_dir = None
        self._python = python
        self._so_far = ''
        self._start_label = None
        self._tempdir = ''

        if sage_code is None:
            sage_code = os.path.join(os.path.split(__file__)[0], 'sage_code')
        self._init_script = os.path.join(sage_code, 'init.py')

        limit_code = '\n'.join((
            'import resource',
            'def process_limit(lim, rlimit, alt_rlimit=None):',
            '    if lim is not None:',
            '       rlimit = getattr(resource, rlimit, alt_rlimit)',
            '       if rlimit is not None:',
            '           hard_lim = resource.getrlimit(rlimit)[1]',
            '           if hard_lim == resource.RLIM_INFINITY or '
            'lim <= hard_lim:',
            '               resource.setrlimit(rlimit, (lim, hard_lim))',
            '',
            '',
            ))

        if process_limits is not None:
            lim_tpt = '{}process_limit({}, "RLIMIT_{}", alt_rlimit={}'\
                      ')\n'
            limit_code = lim_tpt.format(limit_code, process_limits.max_vmem,
                                        'VMEM', 'resource.RLIMIT_AS')
            limit_code = lim_tpt.format(limit_code, process_limits.max_cputime,
                                        'CPU', None)
            limit_code = lim_tpt.format(limit_code,
                                        process_limits.max_processes,
                                        'NPROC', None)

        init_code = '{}{}\n\n_support_.sys.ps1 = "{}"'.format(
            limit_code, init_code, self._prompt)

        if process_limits and process_limits.max_walltime:
            self._max_walltime = process_limits.max_walltime
        self.execute(init_code, mode='raw')
        self.execute('print("INIT OK")', mode='python')

    def command(self):
        return '{} -i {}'.format(self._python, self._init_script)

    def __del__(self):
        try:
            self._cleanup_tempfiles()
        except:
            pass
        try:
            self._cleanup_data_dir()
        except:
            pass

    def _cleanup_data_dir(self):
        if self._data_dir is not None:
            os.chmod(self._data_dir, stat.S_IRWXU)

    def _cleanup_tempfiles(self):
        for X in self._all_tempdirs:
            try:
                shutil.rmtree(X, ignore_errors=True)
            except:
                pass

    def __repr__(self):
        """
        Return string representation of this worksheet process.
        """
        return "Pexpect implementation of worksheet process"

    def interrupt(self):
        """
        Send an interrupt signal to the currently running computation
        in the controlled process.  This may or may not succeed.  Call
        ``self.is_computing()`` to find out if it did.
        """
        if self._expect is None:
            return
        try:
            self._expect.sendline(chr(3))
        except:
            pass

    def quit(self):
        """
        Quit this worksheet process.
        """
        if self._expect is None:
            return
        try:
            self._expect.sendline(chr(3))  # send ctrl-c
            self._expect.sendline('quit_sage()')
        except:
            pass
        try:
            os.killpg(self._expect.pid, 9)
            os.kill(self._expect.pid, 9)
        except OSError:
            pass
        self._expect = None
        self._is_started = False
        self._is_computing = False
        self._start_walltime = None
        self._cleanup_tempfiles()
        self._cleanup_data_dir()

    def start(self):
        """
        Start this worksheet process running.
        """
        self._expect = pexpect.spawn(self.command())
        self._expect.setecho(False)
        self._is_started = True
        self._is_computing = False
        self._number = 0
        self._read()
        self._start_walltime = walltime()

    def update(self):
        """
        This should be called periodically by the server processes.
        It does things like checking for timeouts, etc.
        """
        self._check_for_walltimeout()

    def _check_for_walltimeout(self):
        """
        Check if the walltimeout has been reached, and if so, kill
        this worksheet process.
        """
        if (self._is_started and
                self._max_walltime and self._start_walltime and
                walltime() - self._start_walltime > self._max_walltime):
            self.quit()

    def is_computing(self):
        """
        Return True if a computation is currently running in this worksheet
        subprocess.

        OUTPUT:

            - ``bool``
        """
        return self._is_computing

    def is_started(self):
        """
        Return true if this worksheet subprocess has already been started.

        OUTPUT:

            - ``bool``
        """
        return self._is_started

    def get_tmpdir(self):
        """
        Return two strings (local, remote), where local is the name
        of a pre-created temporary directory, and remote is the name
        of the same directory but on the machine on which the actual
        worksheet process is running.

        OUTPUT:

            - local directory

            - remote directory
        """
        # In this implementation the remote process is just running
        # as the same user on the local machine.
        s = tempfile.mkdtemp()
        return (s, s)

    def execute(self, code, data=None, mode='sage', print_time=False):
        """
        Start executing the given code in this subprocess.

        INPUT:

            - ``code`` -- a code containing code to be executed.

            - ``data`` -- a code or None; if given, must specify an
              absolute path on the server host filesystem.   This may
              be ignored by some worksheet process implementations.
        """
        if self._expect is None:
            self.start()

        if self._expect is None:
            raise RuntimeError(
                "unable to start subprocess using command '%s'" % self.command(
                    ))

        if mode != 'raw':
            self._number += 1
            self._start_label = 'START{}'.format(self._number)
            local, remote = self.get_tmpdir()
            code = '_support_.os.chdir("{}")\n{}'.format(remote, code)
            if data is not None:
                # make a symbolic link from the data directory into local tmp
                # directory
                self._data = os.path.split(data)[1]
                self._data_dir = data
                os.chmod(data, stat.S_IRWXO | stat.S_IRWXU | stat.S_IRWXG)
                os.symlink(data, os.path.join(local, self._data))
            else:
                self._data = ''

            self._tempdir = local
            self._so_far = ''
            self._is_computing = True

            self._all_tempdirs.append(self._tempdir)

        try:
            self._expect.sendline(
                '_support_.execute_code('
                '"{}", globals(), mode="{}", start_label="{}", '
                'print_time={})'.format(
                    b64encode(code.encode('utf-8')).decode('utf-8'),
                    mode, self._start_label, print_time))
        except OSError as msg:
            self._is_computing = False
            self._so_far = str(msg)

    def _read(self):
        try:
            self._expect.expect(pexpect.EOF, self._timeout)
            # got EOF subprocess must have crashed; cleanup
            print("got EOF subprocess must have crashed...")
            print(self._expect.before)
            self.quit()
        except:
            pass

    def output_status(self):
        """
        Return OutputStatus object, which includes output from the
        subprocess from the last executed command up until now,
        information about files that were created, and whether
        computing is now done.

        OUTPUT:

            - ``OutputStatus`` object.
        """
        self._read()
        if self._expect is None:
            self._is_computing = False
        else:
            self._so_far = self._expect.before.decode('utf-8')

        v = re.findall('{}.*{}'.format(self._start_label, self._prompt),
                       self._so_far, re.DOTALL)
        if len(v) > 0:
            self._is_computing = False
            s = v[0][len(self._start_label):-len(self._prompt)]
        else:
            v = re.findall('{}.*'.format(self._start_label),
                           self._so_far, re.DOTALL)
            if len(v) > 0:
                s = v[0][len(self._start_label):]
            else:
                s = ''

        if s.endswith(self._prompt):
            s = s[:-len(self._prompt)]

        files = []
        if os.path.exists(self._tempdir):
            files = [os.path.join(self._tempdir, x) for x in os.listdir(
                self._tempdir) if x != self._data]

        return OutputStatus(s, files, not self._is_computing)


class SageServerExpectRemote(SageServerExpect):
    """
    This worksheet process class implements computation of worksheet
    code as another user possibly on another machine, with the
    following requirements:

       1. ssh keys are setup for passwordless login from the server to the
          remote user account, and

       2. there is a shared filesystem that both users can write to,
          which need not be mounted in the same location.

    VULNERABILITIES: It is possible for a malicious user to see code
    input by other notebook users whose processes are currently
    running.  However, the moment any calculation finishes, the file
    results are moved back to the the notebook server in a protected
    placed, and everything but the input file is deleted, so the
    damage that can be done is limited.  In particular, users can't
    simply browse much from other users.

    INPUT:

        - ``user_at_host`` -- a string of the form 'username@host'
          such that 'ssh user@host' does not require a password, e.g.,
          setup by typing ``ssh-keygen`` as the notebook server and
          worksheet users, then putting ~/.ssh/id_rsa.pub as the file
          .ssh/authorized_keys.  You must make the permissions of
          files and directories right.

        - ``local_directory`` -- (default: None) name of a directory on
          the local computer that the notebook server can write to,
          which the remote computer also has read/write access to.  If
          set to ``None``, then first try the environment variable
          :envvar:`SAGENB_TMPDIR` if it exists, then :envvar:`TMPDIR`.
          Otherwise, fall back to ``/tmp``.

        - ``remote_directory`` -- (default: None) if the local_directory is
          mounted on the remote machine as a different directory name,
          this string is that directory name.

        - ``process_limits`` -- None or a ProcessLimits objects as defined by
          the ``sagenb.interfaces.ProcessLimits`` object.
    """

    def __init__(self,
                 user_at_host,
                 remote_python,
                 local_directory=None,
                 remote_directory=None,
                 process_limits=None,
                 timeout=0.05,
                 **kwargs):
        SageServerExpect.__init__(
            self, process_limits, timeout=timeout, **kwargs)
        self._user_at_host = user_at_host

        if local_directory is None:
            local_directory = os.environ.get("SAGENB_TMPDIR")
        if local_directory is None:
            local_directory = os.environ.get("TMPDIR")
        if local_directory is None:
            local_directory = "/tmp"
        self._local_directory = local_directory

        if remote_directory is None:
            remote_directory = local_directory
        self._remote_directory = remote_directory

        self._remote_python = remote_python

    def command(self):
        c = self._remote_python
        return 'sage-native-execute ssh -t %s "%s"' % (self._user_at_host, c)

    def get_tmpdir(self):
        """
        Return two strings (local, remote), where local is the name
        of a pre-created temporary directory, and remote is the name
        of the same directory but on the machine on which the actual
        worksheet process is running.
        """
        # In this implementation the remote process is just running
        # as the same user on the local machine.
        local = tempfile.mkdtemp(dir=self._local_directory)
        remote = os.path.join(self._remote_directory, local[
                              len(self._local_directory):].lstrip(os.path.sep))
        # Make it so local is world read/writable -- so that the remote
        # worksheet process can write to it.
        os.chmod(local, stat.S_IRWXO | stat.S_IRWXU | stat.S_IRWXG)
        return (local, remote)


class OutputStatus:
    """
    Object that records current status of output from executing some
    code in a worksheet process.  An OutputStatus object has three
    attributes:

            - ``output`` - a string, the output so far

            - ``filenames`` -- list of names of files created by this execution

            - ``done`` -- bool; whether or not the computation is now done

    """

    def __init__(self, output, filenames, done, tempdir=None):
        """
        INPUT:

           - ``output`` -- a string

           - ``filenames`` -- a list of filenames

           - ``done`` -- bool, if True then computation is done, so ``output``
             is complete.

           - ``tempdir`` -- (default: None) a filename of a directory; after
             computation is done, the caller is responsible for
             deleting this directory.
        """
        self.output = output
        self.filenames = filenames
        self.done = done
        self.tempdir = tempdir

    def __repr__(self):
        """
        Return string representation of this output status.
        """
        return (
            "Output Status:\n\toutput: '%s'\n\tfilenames: %s\n\tdone: %s" % (
                self.output, self.filenames, self.done))


class ProcessLimits:
    """
    INPUT:

        - ``max_vmem`` -- maximum virtual memory available to worksheet
          process in megabytes, e.g., 500 would limit worksheet to
          use 500 megabytes.

        - ``max_cputime`` -- maximum cpu time in seconds available to
          worksheet process.  After this amount of cputime is used,
          the worksheet process is killed.

        - ``max_walltime`` -- maximum wall time in seconds available
          to worksheet process. After this amount of time elapses, the
          worksheet subprocess is killed.

        - ``max_processes`` -- maximum number of processes the
          worksheet process can create
    """

    def __init__(self,
                 max_vmem=None,     # maximum amount of virtual memory
                                    # available to the shell in megabytes
                 max_cputime=None,  # maximum cpu time in seconds
                 max_walltime=None,  # maximum wall time in seconds
                 max_processes=None,
                 ):
        self.max_vmem = max_vmem
        self.max_cputime = max_cputime
        self.max_walltime = max_walltime
        self.max_processes = max_processes

    def __repr__(self):
        return 'Process limit object:' + \
               '\n\tmax_vmem = %s MB' % self.max_vmem +  \
               '\n\tmax_cputime = %s' % self.max_cputime + \
               '\n\tmax_walltime = %s' % self.max_walltime + \
               '\n\tmax_processes = %s' % self.max_processes
