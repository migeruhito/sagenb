# -*- coding: utf-8 -*
"""
Worksheet process base clase

AUTHORS:

  - William Stein
"""

#############################################################################
#
#       Copyright (C) 2009 William Stein <wstein@gmail.com>
#  Distributed under the terms of the GNU General Public License (GPL)
#  The full text of the GPL is available at:
#                  http://www.gnu.org/licenses/
#
#############################################################################

from __future__ import absolute_import

import os
import re
import shutil
import StringIO
import sys
import traceback
import tempfile

import pexpect

from ..misc.format import displayhook_hack
from ..misc.format import format_for_pexpect
from ..misc.misc import set_permissive_permissions
from ..misc.misc import set_restrictive_permissions
from ..misc.misc import walltime


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


class SageServerReference(SageServerABC):
    """
    A controlled Python process that executes code.  This is a reference
    implementation.
    """
    @staticmethod
    def execute_code(string, state, data=None):
        # print "execute: '''%s'''"%string
        string = displayhook_hack(string)

        # Now execute the code capturing the output and files that are
        # generated.
        back = os.path.abspath('.')
        tempdir = tempfile.mkdtemp()
        if data is not None:
            # make a symbolic link from the data directory into local tmp
            # directory
            os.symlink(data, os.path.join(tempdir, os.path.split(data)[1]))

        s = StringIO.StringIO()
        saved_stream = sys.stdout
        sys.stdout = s
        try:
            os.chdir(tempdir)
            exec string in state
        except Exception:
            traceback.print_exc(file=s)
        finally:
            sys.stdout = saved_stream
            os.chdir(back)
        s.seek(0)
        out = str(s.read())
        files = [os.path.join(tempdir, x) for x in os.listdir(tempdir)]
        return out, files, tempdir

    def __init__(self, **kwds):
        for key in kwds.keys():
            print(
                "SageServerReference: does not support "
                "'%s' option.  Ignored." % key)
        self._output_status = OutputStatus('', [], True, None)
        self._state = {}

    def __repr__(self):
        """
        Return string representation of this worksheet process.
        """
        return "Reference implementation of worksheet process"

    def interrupt(self):
        """
        Send an interrupt signal to the currently running computation
        in the controlled process.  This may or may not succeed.  Call
        ``self.is_computing()`` to find out if it did.
        """
        pass

    def quit(self):
        """
        Quit this worksheet process.
        """
        self._state = {}

    def start(self):
        """
        Start this worksheet process running.
        """
        pass

    def is_computing(self):
        """
        Return True if a computation is currently running in this worksheet
        subprocess.

        OUTPUT:

            - ``bool``
        """
        return False

    def is_started(self):
        """
        Return true if this worksheet subprocess has already been started.

        OUTPUT:

            - ``bool``
        """
        return True

    def execute(self, string, data=None):
        """
        Start executing the given string in this subprocess.

        INPUT:

            ``string`` -- a string containing code to be executed.

            - ``data`` -- a string or None; if given, must specify an
              absolute path on the server host filesystem.   This may
              be ignored by some worksheet process implementations.
        """
        out, files, tempdir = self.execute_code(string, self._state, data)
        self._output_status = OutputStatus(out, files, True, tempdir)

    def output_status(self):
        """
        Return OutputStatus object, which includes output from the
        subprocess from the last executed command up until now,
        information about files that were created, and whether
        computing is now done.

        OUTPUT:

            - ``OutputStatus`` object.
        """
        OS = self._output_status
        self._output_status = OutputStatus('', [], True)
        return OS


class SageServerExpect(SageServerABC):
    """
    A controlled Python process that executes code using expect.

    INPUT:
        - ``process_limits`` -- None or a ProcessLimits objects as defined by
          the ``sagenb.interfaces.ProcessLimits`` object.
    """

    def __init__(self,
                 process_limits=None,
                 timeout=0.05,
                 python='python',
                 init_code=None):
        """
        Initialize this worksheet process.
        """
        self._init_code = init_code
        self._output_status = OutputStatus('', [], True)
        self._expect = None
        self._is_started = False
        self._is_computing = False
        self._timeout = timeout
        self._prompt = "__SAGE__"
        self._filename = ''
        self._all_tempdirs = []
        self._process_limits = process_limits
        self._max_walltime = None
        self._start_walltime = None
        self._data_dir = None
        self._python = python

        if process_limits:
            u = ''
            if process_limits.max_vmem is not None:
                u += ' -v %s' % (int(process_limits.max_vmem) * 1000)
            if process_limits.max_cputime is not None:
                u += ' -t %s' % (int(process_limits.max_cputime))
            if process_limits.max_processes is not None:
                u += ' -u %s' % (int(process_limits.max_processes))
            # prepend ulimit options
            if u == '':
                self._ulimit = u
            else:
                self._ulimit = 'ulimit %s' % u
        else:
            self._ulimit = ''

        if process_limits and process_limits.max_walltime:
            self._max_walltime = process_limits.max_walltime

    def command(self):
        return self._python
        # TODO: The following simply doesn't work -- this is not a valid way to
        # run ulimited.  Also we should check if ulimit is available before
        # even doing this.
        return '&&'.join([x for x in [self._ulimit, self._python] if x])

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
            set_restrictive_permissions(self._data_dir)

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
        # print "Starting worksheet with command: '%s'"%self.command()
        self._expect = pexpect.spawn(self.command())
        self._is_started = True
        self._is_computing = False
        self._number = 0
        self._read()
        self._start_walltime = walltime()
        self._sage_init()

    def _sage_init(self):
        cmd = '\n'.join((
            'import base64',
            'import sagenb.misc.support as _support_',
            'import sagenb.notebook.interact as _interact_ '
            '# for setting current cell id',
            '',
            '{}'.format(
                self._init_code) if self._init_code is not None else '',
            'import sys; sys.path.append(DATA)',
            '_support_.init(None, globals())',
            '',
            '# The following is Sage-specific -- this immediately bombs out '
            'if sage isn\'t',
            '# installed.',
            'from sage.all_notebook import *',
            'sage.plot.plot.EMBEDDED_MODE=True',
            'sage.misc.latex.EMBEDDED_MODE=True',
            '# TODO: For now we take back sagenb interact; do this until the '
            'sage notebook',
            '# gets removed from the sage library.',
            'from sagenb.notebook.all import *',
            'try:',
            '    load(os.path.join(os.environ["DOT_SAGE"], "init.sage"),',
            '         globals(), attach=True)',
            'except (KeyError, IOError):',
            '    pass',))
        self.execute(cmd)
        self.output_status()

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

    def execute(self, string, data=None):
        """
        Start executing the given string in this subprocess.

        INPUT:

            - ``string`` -- a string containing code to be executed.

            - ``data`` -- a string or None; if given, must specify an
              absolute path on the server host filesystem.   This may
              be ignored by some worksheet process implementations.
        """
        if self._expect is None:
            self.start()

        if self._expect is None:
            raise RuntimeError(
                "unable to start subprocess using command '%s'" % self.command(
                    ))

        self._number += 1

        local, remote = self.get_tmpdir()

        if data is not None:
            # make a symbolic link from the data directory into local tmp
            # directory
            self._data = os.path.split(data)[1]
            self._data_dir = data
            set_permissive_permissions(data)
            os.symlink(data, os.path.join(local, self._data))
        else:
            self._data = ''

        self._tempdir = local
        sage_input = '_sage_input_%s.py' % self._number
        self._filename = os.path.join(self._tempdir, sage_input)
        self._so_far = ''
        self._is_computing = True

        self._all_tempdirs.append(self._tempdir)
        open(self._filename, 'w').write(
                format_for_pexpect(string, self._prompt,
                                   self._number))
        try:
            self._expect.sendline(
                '\nimport os;os.chdir("%s");\nexecfile("%s")' % (
                    remote, sage_input))
        except OSError as msg:
            self._is_computing = False
            self._so_far = str(msg)

    def _read(self):
        try:
            self._expect.expect(pexpect.EOF, self._timeout)
            # got EOF subprocess must have crashed; cleanup
            print "got EOF subprocess must have crashed..."
            print self._expect.before
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
            self._so_far += self._expect.before

        v = re.findall('START%s.*%s' %
                       (self._number, self._prompt), self._so_far, re.DOTALL)
        if len(v) > 0:
            self._is_computing = False
            s = v[0][len('START%s' % self._number):-len(self._prompt)]
        else:
            v = re.findall('START%s.*' % self._number, self._so_far, re.DOTALL)
            if len(v) > 0:
                s = v[0][len('START%s' % self._number):]
            else:
                s = ''

        if s.endswith(self._prompt):
            s = s[:-len(self._prompt)]

        files = []
        if os.path.exists(self._tempdir):
            files = [os.path.join(self._tempdir, x) for x in os.listdir(
                self._tempdir) if x != self._data]
            files = [x for x in files if x != self._filename]

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
        if self._ulimit == '':
            c = self._remote_python
        else:
            c = '&&'.join(
                [x for x in [self._ulimit, self._remote_python] if x])
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
        set_permissive_permissions(local)
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
