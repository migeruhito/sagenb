# -*- coding: utf-8 -*
from __future__ import absolute_import

import os
import resource
import signal
import socket
import stat
import subprocess
import sys
import tempfile
import time

from importlib import import_module


def import_from(mod, obj, default=lambda: None):
    """
    Returns the object from module mod if the given module exists and has such
    object, else 'default' parameter.
    The object is not assigned to the caller's namespace
    """
    try:
        return getattr(get_module(mod), obj)
    except AttributeError:
        return default()


def get_module(module, pkg=None, default=lambda: None):
    """
    Returns the module if the given module exists, else 'default' parameter.
    The module is not assigned to the caller's namespace
    """
    try:
        return import_module(module, pkg)
    except ImportError:
        return default()


def sage_var(name, fallback=lambda: None, sage_mod='env'):
    try:
        fb_value = os.environ[name]
    except KeyError:
        pass
    else:
        def fallback():
            return fb_value

    return import_from('sage.{}'.format(sage_mod), name, default=fallback)


def which(cmd, mode=os.F_OK | os.X_OK, path=None):
    # From python3 shutil
    """Given a command, mode, and a PATH string, return the path which
    conforms to the given mode on the PATH, or None if there is no such
    file.

    `mode` defaults to os.F_OK | os.X_OK. `path` defaults to the result
    of os.environ.get("PATH"), or can be overridden with a custom search
    path.

    """
    # Check that a given file can be accessed with the correct mode.
    # Additionally check that `file` is not a directory, as on Windows
    # directories pass the os.access check.
    def _access_check(fn, mode):
        return (os.path.exists(fn) and os.access(fn, mode) and
                not os.path.isdir(fn))

    # If we're given a path with a directory part, look it up directly rather
    # than referring to PATH directories. This includes checking relative to
    # the current directory, e.g. ./script
    if os.path.dirname(cmd):
        if _access_check(cmd, mode):
            return cmd
        return None

    if path is None:
        path = os.environ.get("PATH", os.defpath)
    if not path:
        return None
    path = path.split(os.pathsep)

    if sys.platform == "win32":
        # The current directory takes precedence on Windows.
        if os.curdir not in path:
            path.insert(0, os.curdir)

        # PATHEXT is necessary to check on Windows.
        pathext = os.environ.get("PATHEXT", "").split(os.pathsep)
        # See if the given file matches any of the expected path extensions.
        # This will allow us to short circuit when given "python.exe".
        # If it does match, only test that one, otherwise we have to try
        # others.
        if any(cmd.lower().endswith(ext.lower()) for ext in pathext):
            files = [cmd]
        else:
            files = [cmd + ext for ext in pathext]
    else:
        # On other platforms you don't have things like PATHEXT to tell you
        # what file suffixes are executable, so just pass on cmd as-is.
        files = [cmd]

    seen = set()
    for dir in path:
        normdir = os.path.normcase(dir)
        if normdir not in seen:
            seen.add(normdir)
            for thefile in files:
                name = os.path.join(dir, thefile)
                if _access_check(name, mode):
                    return name
    return None


def tmp_filename(name='tmp', ext='', **kwargs):
    # TODO: rethink this
    # based on sage.misc.temporary_file
    handle, tmp = tempfile.mkstemp(prefix=name, suffix=ext, **kwargs)
    os.close(handle)
    return tmp


def tmp_dir(name='dir', ext='', **kwargs):
    # TODO: rethink this
    # based on sage.misc.temporary_file
    tmp = tempfile.mkdtemp(prefix=name, suffix=ext, **kwargs)
    return '{}{}'.format(tmp, os.sep)


def cputime(t=0):
    # TODO: Not used
    try:
        t = float(t)
    except TypeError:
        t = 0.0
    u, s = resource.getrusage(resource.RUSAGE_SELF)[:2]
    return u + s - t


def walltime(t=0):
    return time.time() - t


def set_restrictive_permissions(filename, allow_execute=False):
    x = stat.S_IRWXU
    if allow_execute:
        x = x | stat.S_IXGRP | stat.S_IXOTH
    os.chmod(filename, x)


def set_permissive_permissions(filename):
    # TODO: Not used
    os.chmod(filename, stat.S_IRWXO | stat.S_IRWXU | stat.S_IRWXG)


def ignore_nonexistent_files(curdir, dirlist):
    """
    Returns a list of non-existent files, given a directory and its
    contents.  The returned list includes broken symbolic links.  Use
    this, e.g., with :func:`shutil.copytree`, as shown below.

    INPUT:

    - ``curdir`` - a string; the name of the current directory

    - ``dirlist`` - a list of strings; names of ``curdir``'s contents

    OUTPUT:

    - a list of strings; names of ``curdir``'s non-existent files

    EXAMPLES::

        sage: import os, shutil
        sage: from sagenb.misc.misc import ignore_nonexistent_files
        sage: opj = os.path.join; ope = os.path.exists; t = tmp_dir()
        sage: s = opj(t, 'src'); t = opj(t, 'trg'); hi = opj(s, 'hi.txt');
        sage: os.makedirs(s)
        sage: f = open(hi, 'w'); f.write('hi'); f.close()
        sage: os.symlink(hi, opj(s, 'good.txt'))
        sage: os.symlink(opj(s, 'bad'), opj(s, 'bad.txt'))
        sage: slist = sorted(os.listdir(s)); slist
        ['bad.txt', 'good.txt', 'hi.txt']
        sage: map(lambda x: ope(opj(s, x)), slist)
        [False, True, True]
        sage: map(lambda x: os.path.islink(opj(s, x)), slist)
        [True, True, False]
        sage: shutil.copytree(s, t)
        Traceback (most recent call last):
        ...
        Error: [('.../src/bad.txt',
                 '.../trg/bad.txt',
                 "[Errno 2] No such file or directory: '.../src/bad.txt'")]
        sage: shutil.rmtree(t); ope(t)
        False
        sage: shutil.copytree(s, t, ignore = ignore_nonexistent_files)
        sage: tlist = sorted(os.listdir(t)); tlist
        ['good.txt', 'hi.txt']
        sage: map(lambda x: ope(opj(t, x)), tlist)
        [True, True]
        sage: map(lambda x: os.path.islink(opj(t, x)), tlist)  # Note!
        [False, False]
    """
    ignore = []
    for x in dirlist:
        if not os.path.exists(os.path.join(curdir, x)):
            ignore.append(x)
    return ignore


def word_wrap(s, ncols=85):
    t = []
    if ncols == 0:
        return s
    for x in s.split('\n'):
        if len(x) == 0 or x.lstrip()[:5] == 'sage:':
            t.append(x)
            continue
        while len(x) > ncols:
            k = ncols
            while k > 0 and x[k] != ' ':
                k -= 1
            if k == 0:
                k = ncols
                end = '\\'
            else:
                end = ''
            t.append(x[:k] + end)
            x = x[k:]
            k = 0
            while k < len(x) and x[k] == ' ':
                k += 1
            x = x[k:]
        t.append(x)
    return '\n'.join(t)


def encoded_str(obj, encoding='utf-8'):
    ur"""
    Takes an object and returns an encoded str human-readable representation.

    EXAMPLES::

        sage: from sagenb.misc.misc import encoded_str
        sage: encoded_str(
            u'\u011b\u0161\u010d\u0159\u017e\xfd\xe1\xed\xe9\u010f\u010e'
            ) == 'ěščřžýáíéďĎ'
        True
        sage: encoded_str(u'abc')
        'abc'
        sage: encoded_str(123)
        '123'
    """
    if isinstance(obj, unicode):
        return obj.encode(encoding, 'ignore')
    return str(obj)


def unicode_str(obj, encoding='utf-8'):
    ur"""
    Takes an object and returns a unicode human-readable representation.

    EXAMPLES::

        sage: from sagenb.misc.misc import unicode_str
        sage: unicode_str('ěščřžýáíéďĎ'
            ) == u'\u011b\u0161\u010d\u0159\u017e\xfd\xe1\xed\xe9\u010f\u010e'
        True
        sage: unicode_str('abc')
        u'abc'
        sage: unicode_str(123)
        u'123'
    """
    if isinstance(obj, str):
        return obj.decode(encoding, 'ignore')
    elif isinstance(obj, unicode):
        return obj
    return unicode(obj)


def N_(message):
    return message


def nN_(message_singular, message_plural):
    return [message_singular, message_plural]


def print_open_msg(address, port, secure=False, path=""):
    """
    Print a message on the screen suggesting that the user open their
    web browser to a certain URL.

    INPUT:

    - ``address`` -- a string; a computer address or name

    - ``port`` -- an int; a port number

    - ``secure`` -- a bool (default: False); whether to prefix the URL
      with 'http' or 'https'

    - ``path`` -- a string; the URL's path following the port.

    EXAMPLES::

        sage: from sagenb.misc.misc import print_open_msg
        sage: print_open_msg('localhost', 8080, True)
        ┌──────────────────────────────────────────────────┐
        │                                                  │
        │ Open your web browser to https://localhost:8080  │
        │                                                  │
        └──────────────────────────────────────────────────┘
        sage: print_open_msg('sagemath.org', 8080, False)
        ┌────────────────────────────────────────────────────┐
        │                                                    │
        │ Open your web browser to http://sagemath.org:8080  │
        │                                                    │
        └────────────────────────────────────────────────────┘
        sage: print_open_msg('sagemath.org', 90, False)
        ┌──────────────────────────────────────────────────┐
        │                                                  │
        │ Open your web browser to http://sagemath.org:90  │
        │                                                  │
        └──────────────────────────────────────────────────┘
        sage: print_open_msg('sagemath.org', 80, False)
        ┌────────────────────────────────────────────────┐
        │                                                │
        │  Open your web browser to http://sagemath.org  │
        │                                                │
        └────────────────────────────────────────────────┘
    """
    if port == 80:
        port = ''
    else:
        port = ':%s' % port
    s = "Open your web browser to http%s://%s%s%s" % (
        's' if secure else '', address, port, path)
    t = len(s)
    if t % 2:
        t += 1
        s += ' '
    n = max(t + 4, 50)
    k = n - t - 1
    j = k / 2
    msg = '┌' + '─' * (n - 2) + '┐\n'
    msg += '│' + ' ' * (n - 2) + '│\n'
    msg += '│' + ' ' * j + s + ' ' * j + '│\n'
    msg += '│' + ' ' * (n - 2) + '│\n'
    msg += '└' + '─' * (n - 2) + '┘'
    print msg


def find_next_available_port(interface, start, max_tries=100, verbose=False):
    """
    Find the next available port at a given interface, that is, a port for
    which a current connection attempt returns a 'Connection refused'
    error message.  If no port is found, raise a RuntimeError exception.

    INPUT:

    - ``interface`` - address to check

    - ``start`` - an int; the starting port number for the scan

    - ``max_tries`` - an int (default: 100); how many ports to scan

    - ``verbose`` - a bool (default: True); whether to print information
      about the scan

    OUTPUT:

    - an int - the port number

    EXAMPLES::

        sage: from sagenb.misc.misc import find_next_available_port
        sage: find_next_available_port(
            '127.0.0.1',
            9000, verbose=False)   # random output -- depends on network
        9002
    """
    def handler(signum, frame):
        raise UserWarning('timed out')

    alarm_count = 0
    for port in range(start, start + max_tries + 1):
        signal.signal(signal.SIGALRM, handler)
        signal.alarm(5)
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.connect((interface, port))
        except socket.error, msg:
            if msg[1] == 'Connection refused':
                if verbose:
                    print "Using port = %s" % port
                return port
        except UserWarning:
            if verbose:
                print "Port %s timed out." % port
                print "Trying next port..."
            continue
        except KeyboardInterrupt:
            if verbose:
                print "alarm"
            alarm_count += 1
            if alarm_count >= 10:
                break
        finally:
            signal.signal(signal.SIGALRM, signal.SIG_DFL)
            signal.alarm(0)
        if verbose:
            print "Port %s is already in use." % port
            print "Trying next port..."
    raise RuntimeError("no available port.")


def open_page(browser, address, port, secure, path=""):
    rsrc = 'https' if secure else 'http'

    os.system('%s %s://%s:%s%s 1>&2 > /dev/null &' %
              (browser, rsrc, address, port, path))


def system_command(cmd, msg=None):
    msg = cmd if msg is None else '\n'.join((msg, cmd))
    print(msg)
    subprocess.call([cmd], shell=True)


def cached_property(function):
    attr_name = '__{}'.format(function.__name__)

    def get_cached_property(self):
        try:
            output = getattr(self, attr_name)
        except AttributeError:
            output = function(self)
            setattr(self, attr_name, output)
        return output

    def del_cached_property(self):
        try:
            delattr(self, attr_name)
        except AttributeError:
            pass

    return property(fget=get_cached_property, fdel=del_cached_property)


def writable_cached_property(function):
    attr_name = '__{}'.format(function.__name__)

    def get_cached_property(self):
        try:
            output = getattr(self, attr_name)
        except AttributeError:
            output = function(self)
            setattr(self, attr_name, output)
        return output

    def del_cached_property(self):
        try:
            delattr(self, attr_name)
        except AttributeError:
            pass

    def set_cached_property(self, value):
        setattr(self, attr_name, value)

    return property(fget=get_cached_property, fset=set_cached_property,
                    fdel=del_cached_property)


def next_available_id(v):
    """
    Return smallest nonnegative integer not in v.
    """
    i = 0
    while i in v:
        i += 1
    return i


def make_path_relative(dir):
    r"""
    Replace an absolute path with a relative path, if possible.
    Otherwise, return the given path.

    INPUT:

    - ``dir`` - a string containing, e.g., a directory name

    OUTPUT:

    - a string
    """
    base, file = os.path.split(dir)
    if os.path.exists(file):
        return file
    return dir


def sort_worksheet_list(v, sort, reverse):
    """
    Sort a given list on a given key, in a given order.

    INPUT:

    - ``sort`` - a string; 'last_edited', 'owner', 'rating', or 'name'

    - ``reverse`` - a bool; if True, reverse the order of the sort.

    OUTPUT:

    - the sorted list
    """
    def key_last_edited(a):
        return -a.last_edited()
    if sort == 'last_edited':
        v.sort(key=key_last_edited, reverse=reverse)
    elif sort in ['name', 'owner']:
        v.sort(key=lambda a: (getattr(a, sort)().lower(), key_last_edited(a)),
               reverse=reverse)
    elif sort == 'rating':
        v.sort(key=lambda a: (getattr(a, sort)(), key_last_edited(a)),
               reverse=reverse)
    else:
        raise ValueError('Invalid sort key {!r}'.format(sort))
