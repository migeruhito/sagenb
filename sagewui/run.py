#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script to start the notebook form the command line
"""

#############################################################################
#       Copyright (C) 2009 William Stein <wstein@gmail.com>
#                 (C) 2014, 2015 J. Miguel Farto <jmfarto@gmail.com>
#  Distributed under the terms of the GNU General Public License (GPL)
#  The full text of the GPL is available at:
#                  http://www.gnu.org/licenses/
#############################################################################
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from builtins import input
from builtins import object
from builtins import open
from builtins import str
from future.utils import native_str

from future.moves.urllib.parse import quote

import os
import random
import argparse
import logging
import getpass
import signal
from os.path import join as joinpath

from sagewui.app import create_app
from sagewui.config import min_password_length
from sagewui.config import BROWSER_PATH
from sagewui.config import DB_PATH
from sagewui.config import DEFAULT_NB_NAME
from sagewui.config import HOME_PATH
from sagewui.config import PID_FILE_TEMPLATE
from sagewui.config import PID_PATH
from sagewui.config import SSL_PATH
from sagewui.config import UAT_USER
from sagewui.config import UAT_GUEST
from sagewui.config import UN_ADMIN
from sagewui.config import UN_GUEST
from sagewui.config import UN_PUB
from sagewui.config import UN_SAGE
from sagewui.gui import notebook
from sagewui.util import abspath
from sagewui.util import cached_property
from sagewui.util import find_next_available_port
from sagewui.util import get_module
from sagewui.util import makedirs
from sagewui.util import open_page
from sagewui.util import print_open_msg
from sagewui.util import securepath
from sagewui.util import system_command
from sagewui.util import testpaths
from sagewui.util import which


class NotebookFrontend(object):
    def __init__(self, **kwargs):
        self.servers = {
            'twistd': self.twisted,
            'werkzeug': self.werkzeug,
            'flask': self.werkzeug,
            'tornado': self.tornado,
            }

        self.conf = {
            # Not parsed configuration parameters
            'cwd': os.getcwd(),
            'startup_token': None,
            }

        self.default_paths = {
            'dbdir': abspath(DB_PATH),
            'piddir': abspath(PID_PATH),
            'ssldir': abspath(SSL_PATH),
            'homedir': abspath(HOME_PATH),
            'upload': None,
            }
        self.app_path_names = ('dbdir', 'piddir', 'ssldir')

        self.notebook = None

    @cached_property()
    def msg(self):
        return {
            'path': '\n'.join((
                'Warning:',
                '    --{} {} does not exists.',
                '    Taking the default {} instead',
                )),
            'upload':
                'Unable to find the file {} to upload',
            'ssl':
                'HTTPS cannot be used without pyOpenSSL installed. '
                'See the Sage README for more information.',
            'insecure': '\n'.join((
                '*' * 70,
                'WARNING: Insecure notebook server listening on external '
                'interface.',
                'Unless you are running this via ssh port forwarding, you are',
                '**crazy**! You should run sagewui with the option --secure.',
                '*' * 70,
                )),
            'alogin':
                'If your web browser does not open, you have to '
                'manually open it to the above URL.',
            'ssl_setup':
                'I must setup ssl stuff in order to use an SECURE encrypted '
                'notebook',
            'passchange': 'Password changed for user {!r}.',
            'admincreated': '\n'.join((
                'User admin created with the password you specified.',
                '',
                '',
                '*' * 70,
                '',
                )),
            'adminlogin':
                'Login to the Sage notebook as admin with the password you '
                'specified above.',
            'passreset': '\n'.join((
                'There is an admin account. If you do not remember the '
                'password,',
                'quit the notebook and type `sagenb --reset`.',
            )),
            'server': 'Executing Sage Notebook with {} server',
            'ssl_wzeug':
                'HTTPS cannot be used without pyOpenSSL installed. See the '
                'Sage README for more information.'

        }

    @property
    def parser(self):
        parser = argparse.ArgumentParser(description='Starts sage notebook')
        for path, default in self.default_paths.items():
            parser.add_argument(
                '--{}'.format(path),
                dest=path,
                default=default,
                action='store',
                )

        parser.add_argument(
            '--nbname',
            dest='nbname',
            default=DEFAULT_NB_NAME,
            action='store',
            )

        parser.add_argument(
            '--port',
            dest='port',
            default=8080,
            action='store',
            type=int,
            )
        parser.add_argument(
            '--interface',
            dest='interface',
            default='localhost',
            action='store',
            )
        parser.add_argument(
            '--port_tries',
            dest='port_tries',
            default=50,
            action='store',
            type=int,
            )
        parser.add_argument(
            '--secure',
            dest='secure',
            action='store_true',
            )
        parser.add_argument(
            '--reset',
            dest='reset',
            action='store_true',
            )
        parser.add_argument(
            '--accounts',
            dest='accounts',
            action='store_true',
            )
        parser.add_argument(
            '--openid',
            dest='openid',
            action='store_true',
            )

        parser.add_argument(
            '--server_pool',
            dest='server_pool',
            default=None,
            nargs='+',
            )
        parser.add_argument(
            '--ulimit',
            dest='ulimit',
            default='',
            action='store',
            )

        parser.add_argument(
            '--timeout',
            dest='timeout',
            default=None,
            action='store',
            type=int,
            )
        parser.add_argument(
            '--doc_timeout',
            dest='doc_timeout',
            default=None,
            action='store',
            type=int,
            )

        parser.add_argument(
            '--no_automatic_login',
            dest='automatic_login',
            action='store_false',
            )

        parser.add_argument(
            '--quiet',
            dest='quiet',
            action='store_true',
            )

        parser.add_argument(
            '--server',
            dest='server',
            default='twistd',
            action='store',
            choices=tuple(self.servers),
            )
        parser.add_argument(
            '--debug',
            dest='debug',
            action='store_true',
            )

        return parser

    def __call__(self, args=None):
        self.run(args)

    def parse(self, args=None):
        self.conf.update(vars(self.parser.parse_args(args)))

    def update_conf(self):
        C = self.conf
        M = self.msg

        makedirs(*(self.default_paths[p] for p in self.app_path_names))
        C['nbname'] = securepath(C['nbname'])

        for path, default in self.default_paths.items():
            C[path] = abspath(C[path])
            if not testpaths(C[path]):
                print(M['path'].format(path, C[path], default))
                C[path] = default

        C['directory'] = abspath(C['dbdir'], C['nbname'])

        C['pidfile'] = joinpath(
            C['piddir'], PID_FILE_TEMPLATE.format(C['nbname']))

        C['priv_pem'] = joinpath(C['ssldir'], 'private.pem')
        C['pub_pem'] = joinpath(C['ssldir'], 'public.pem')

        os.chdir(C['homedir'])  # If not readable, twisted fails in server mode

        if C['debug']:
            C['server'] = 'werkzeug'

        if C['interface'] != 'localhost' and not C['secure']:
            print(M['insecure'])

        C['port'] = find_next_available_port(
            C['interface'], C['port'], C['port_tries'])

        if C['automatic_login']:
            print(M['alogin'])
            C['startup_token'] = '{0:x}'.format(random.randint(0, 2**128))

        # Check whether pyOpenSSL is installed or not (see Sage trac #13385)
        if C['secure'] and get_module('OpenSSL') is None:
            raise RuntimeError(M['ssl'])
        if C['secure'] and not testpaths(C['priv_pem'], C['pub_pem']):
            print(M['ssl_setup'])
            self.ssl_setup()

        #################################################################
        # Update notebook

        self.notebook = notebook.load_notebook(
            C['directory'],
            interface=C['interface'],
            port=C['port'],
            secure=C['secure'])
        nb = self.notebook

        C['directory'] = nb.dir

        if not C['quiet']:
            print('The notebook files are stored in:', nb.dir)

        if C['timeout'] is not None:
            nb.conf['idle_timeout'] = C['timeout']
        if C['doc_timeout'] is not None:
            nb.conf['doc_timeout'] = C['doc_timeout']

        nb.conf['openid'] = C['openid']

        if C['accounts'] is not None:
            nb.conf['accounts'] = (C['accounts'])

        if ('root' in nb.user_manager and
                UN_ADMIN not in nb.user_manager):
            # This is here only for backward compatibility with one
            # version of the notebook.
            nb.create_user_with_same_password(UN_ADMIN, 'root')
            # It would be a security risk to leave an escalated account around.

        if UN_ADMIN not in nb.user_manager:
            C['reset'] = True

        if C['reset']:
            passwd = self.get_admin_passwd()
            if UN_ADMIN in nb.user_manager:
                nb.user_manager[UN_ADMIN].password = passwd
                print(M['passchange'].format(UN_ADMIN))
            else:
                nb.user_manager.create_default_users(passwd)
                print(M['admincreated'])
                if C['secure']:
                    print(M['adminlogin'])
            # nb.del_user('root')

        # For old notebooks, make sure that default users are always created.
        # This fixes issue #175 (https://github.com/sagemath/sagenb/issues/175)
        um = nb.user_manager
        for user in (UN_SAGE, UN_PUB):
            if user not in um:
                um.add_user(user, '', '', account_type=UAT_USER)
        if UN_GUEST not in um:
            um.add_user(UN_GUEST, '', '', account_type=UAT_GUEST)

        nb.set_server_pool(C['server_pool'])
        nb.set_ulimit(C['ulimit'])

        nb.upgrade_model()
        nb.save()

    def run(self, args=None):
        self.parse(args)
        self.update_conf()
        if not self.conf['quiet']:
            print_open_msg(self.conf['interface'], self.conf['port'],
                           secure=self.conf['secure'])
        if self.conf['secure'] and not self.conf['quiet']:
            print(self.msg['passreset'])
        print(self.msg['server'].format(self.conf['server']))

        # TODO: This must be a conf parameter of the notebook
        self.notebook.DIR = self.conf['cwd']

        flask_app = create_app(self.notebook,
                               startup_token=self.conf['startup_token'],
                               debug=self.conf['debug'],
                               )
        self.servers[self.conf['server']](flask_app)

    def exit(self):
        self.save_notebook()
        os.unlink(self.conf['pidfile'])
        os.chdir(self.conf['cwd'])

    def werkzeug(self, flask_app):
        self.write_pid()

        if self.conf['secure']:
            try:
                from OpenSSL import SSL
                ssl_context = SSL.Context(SSL.SSLv23_METHOD)
                ssl_context.use_privatekey_file(self.conf['priv_pem'])
                ssl_context.use_certificate_file(self.conf['pub_pem'])
            except ImportError:
                raise RuntimeError(self.msg['ssl_wzeug'])
        else:
            ssl_context = None

        logger = logging.getLogger('werkzeug')
        logger.setLevel(
            logging.DEBUG if self.conf['debug'] else logging.WARNING)
        # logger.setLevel(logging.INFO) # to see page requests
        logger.addHandler(logging.StreamHandler())

        self.open_page()

        try:
            flask_app.run(host=self.conf['interface'], port=self.conf['port'],
                          threaded=True, ssl_context=ssl_context)
        finally:
            self.exit()

    def twisted(self, flask_app):
        from twisted.internet import reactor
        from twisted.internet.error import ReactorNotRunning
        from twisted.web import server
        from twisted.web.wsgi import WSGIResource
        from twisted.application import service, strports
        from twisted.scripts._twistd_unix import ServerOptions
        from twisted.scripts._twistd_unix import UnixApplicationRunner

        if self.conf['secure']:
            self.conf['strport'] = 'ssl:{port}:'\
                                   'interface={interface}:'\
                                   'privateKey={priv_pem}:'\
                                   'certKey={pub_pem}'.format(**self.conf)
        else:
            self.conf['strport'] = 'tcp:{port}:'\
                                   'interface={interface}'.format(**self.conf)
        # Options as in twistd command line utility
        self.conf['twisted_opts'] = '--pidfile={pidfile} -no'.format(
            **self.conf).split()
        ####################################################################
        # See
        # http://twistedmatrix.com/documents/current/web/howto/
        #       using-twistedweb.html
        #  (Serving WSGI Applications) for the basic ideas of the below code
        ####################################################################

        def my_sigint(x, n):
            try:
                reactor.stop()
            except ReactorNotRunning:
                pass
            signal.signal(signal.SIGINT, signal.SIG_DFL)

        signal.signal(signal.SIGINT, my_sigint)

        resource = WSGIResource(reactor, reactor.getThreadPool(), flask_app)

        class QuietSite(server.Site):
            def log(*args, **kwargs):
                '''Override the logging so that requests are not logged'''
                pass
        # Log only errors, not every page hit
        site = QuietSite(resource)
        # To log every single page hit, uncomment the following line
        # site = server.Site(resource)

        application = service.Application("Sage Notebook")
        s = strports.service(native_str(self.conf['strport']), site)
        self.open_page()
        s.setServiceParent(application)

        # This has to be done after sagenb.create_app is run
        reactor.addSystemEventTrigger('before', 'shutdown', self.save_notebook)

        # Run the application without .tac file
        class AppRunner(UnixApplicationRunner):
            '''
            twisted application runner. The application is provided on init,
            not read from file
            '''
            def __init__(self, app, conf):
                super(self.__class__, self).__init__(conf)
                self.app = app

            def createOrGetApplication(self):
                '''Overrides the reading of the application from file'''
                return self.app

        twisted_conf = ServerOptions()
        twisted_conf.parseOptions(self.conf['twisted_opts'])

        AppRunner(application, twisted_conf).run()

    def tornado(self, flask_app):
        from tornado.wsgi import WSGIContainer
        from tornado.httpserver import HTTPServer
        from tornado.ioloop import IOLoop

        self.write_pid()

        ssl_options = {
            'certfile': self.conf['pub_pem'],
            'keyfile': self.conf['priv_pem']
            } if self.conf['secure'] else None

        self.open_page()
        wsgi_app = WSGIContainer(flask_app)
        http_server = HTTPServer(wsgi_app, ssl_options=ssl_options)
        http_server.listen(self.conf['port'], address=self.conf['interface'])
        try:
            IOLoop.instance().start()
        except KeyboardInterrupt:
            pass
        finally:
            self.exit()

    def open_page(self):
        # If we have to login and upload a file, then we do them
        # in that order and hope that the login is fast enough.
        if self.conf['automatic_login']:
            open_page(BROWSER_PATH, self.conf['interface'], self.conf['port'],
                      self.conf['secure'],
                      '/?startup_token={}'.format(self.conf['startup_token']))
        if self.conf['upload']:
            open_page(
                BROWSER_PATH, self.conf['interface'], self.conf['port'],
                self.conf['secure'],
                '/upload_worksheet?url=file://{}'.format(
                    quote(self.conf['upload'])))

    def write_pid(self):
        with open(self.conf['pidfile'], "w") as pidfile:
            pidfile.write(str(os.getpid()))  # py2: str

    def save_notebook(self):
        print('Quitting all running worksheets...')
        self.notebook.quit()
        print('Saving notebook...')
        self.notebook.save()
        print('Notebook cleanly saved.')

    def get_admin_passwd(self):
        print(
            '',
            '',
            'Please choose a new password for the '
            'Sage Notebook {!r} user'.format(UN_ADMIN),
            'Do _not_ choose a stupid password, since anybody who could guess '
            'your password',
            'and connect to your machine could access or delete your files.',
            'NOTE: Only the hash of the password you type is stored by Sage.',
            'You can change your password by typing notebook(reset=True).',
            '',
            '',
            sep='\n')
        while True:
            passwd = getpass.getpass("Enter new password: ")
            if len(passwd) < min_password_length:
                print('That password is way too short. Enter a password with '
                      'at least {} characters.'.format(min_password_length))
                continue
            passwd2 = getpass.getpass('Retype new password: ')
            if passwd != passwd2:
                print('Sorry, passwords do not match.')
            else:
                break

        print('Please login to the notebook with the username {!r} and the '
              'above password.'.format(UN_ADMIN))
        return passwd

    def ssl_setup(self):
        makedirs(self.conf['ssldir'])

        if which('openssl') is None:
            raise RuntimeError('You must install openssl to use the secure'
                               'notebook server.')

        dn = input('Domain name [localhost]: ').strip()
        if dn == '':
            print('Using default localhost')
            dn = 'localhost'

        # Key and certificate data
        bits = 2048
        days = 10000
        distinguished_name = "'/{}/'".format('/'.join((
            'CN={}'.format(dn),
            'C=US',
            'ST=Washington',
            'O=SAGE (at localhost)',
            'OU=389',
            'emailAddress=sage@sagemath.org',
            'UID=sage_user',
            )))

        # We use openssl since it is open
        # *vastly* faster on Linux, for some weird reason.
        system_command(
            'openssl genrsa -out {} {}'.format(self.conf['priv_pem'], bits),
            'Using openssl to generate key')
        system_command(
            'openssl req  -key {} -out {} -newkey rsa:{} -x509 '
            '-days {} -subj {}'.format(
                self.conf['priv_pem'], self.conf['pub_pem'], bits,
                days, distinguished_name))

        # Set permissions on private cert
        os.chmod(self.conf['priv_pem'], 0o600)

        print('Successfully configured ssl.')


if __name__ == '__main__':
    nf = NotebookFrontend()
    nf()
