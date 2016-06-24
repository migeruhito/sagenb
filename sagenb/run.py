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

import os
import random
import argparse
import logging
import urllib
import getpass
import signal

from sagenb.app import create_app
from sagenb.config import min_password_length
from sagenb.config import DOT_SAGENB
from sagenb.config import SAGE_BROWSER
from sagenb.config import UAT_USER
from sagenb.config import UAT_GUEST
from sagenb.config import UN_ADMIN
from sagenb.config import UN_GUEST
from sagenb.config import UN_PUB
from sagenb.config import UN_SAGE
from sagenb.util import find_next_available_port
from sagenb.util import open_page
from sagenb.util import print_open_msg
from sagenb.util import system_command
from sagenb.notebook import notebook
from sagenb.util import get_module
from sagenb.util import which


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
            'conf_path': os.path.join(DOT_SAGENB, 'notebook'),
            }

        self.notebook = None

    @property
    def parser(self):
        parser = argparse.ArgumentParser(description='Starts sage notebook')

        parser.add_argument(
            '--directory',
            dest='directory',
            default=None,
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
            '--upload',
            dest='upload',
            default=None,
            action='store',
            )
        parser.add_argument(
            '--no_automatic_login',
            dest='automatic_login',
            action='store_false',
            )

        parser.add_argument(
            '--start_path',
            dest='start_path',
            default='',
            action='store',
            )
        parser.add_argument(
            '--fork',
            dest='fork',
            action='store_true',
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
        parser.add_argument(
            '--profile',
            dest='profile',
            action='store_true',
            )

        # Not supported options
        parser.add_argument(
            '--subnets',
            dest='subnets',
            default=None,
            action='store',
            )
        parser.add_argument(
            '--require_login',
            dest='require_login',
            default=None,
            action='store',
            )
        parser.add_argument(
            '--open_viewer',
            dest='open_viewer',
            default=None,
            action='store',
            )
        parser.add_argument(
            '--address',
            dest='address',
            default=None,
            action='store',
            )

        return parser

    def __call__(self, args=None):
        self.run(args)

    def non_supported(self):
        if self.conf['subnets'] is not None:
            raise ValueError(
                'The subnets parameter is no longer supported. Please use a '
                'firewall to block subnets, or even better, volunteer to '
                'wite the code to implement subnets again.')
        if (self.conf['require_login'] is not None or
                self.conf['open_viewer'] is not None):
            raise ValueError(
                'The require_login and open_viewer parameters are no longer '
                'supported. Please use automatic_login=True to automatically'
                'log in as admin, or use automatic_login=False to not '
                'automatically log in.')
        if self.conf['address'] is not None:
            raise ValueError('Use "interface" instead of "address" when '
                             'calling notebook(...).')

    def parse(self, args=None):
        self.conf.update(vars(self.parser.parse_args(args)))

    def update_conf(self):
        if self.conf['debug']:
            self.conf['server'] = 'werkzeug'

        self.conf['private_pem'] = os.path.join(self.conf['conf_path'],
                                                'private.pem')
        self.conf['public_pem'] = os.path.join(self.conf['conf_path'],
                                               'public.pem')
        self.conf['template_file'] = os.path.join(self.conf['conf_path'],
                                                  'cert.cfg')

        # Check whether pyOpenSSL is installed or not (see Sage trac #13385)
        if self.conf['secure'] and get_module('OpenSSL') is None:
            raise RuntimeError('HTTPS cannot be used without pyOpenSSL '
                               'installed. '
                               'See the Sage README for more information.')

        # Turn it into a full path for later conversion to a file URL
        upload = self.conf['upload']
        if upload:
            upload = os.path.abspath(os.path.expanduser(upload))
            if not os.path.exists(upload):
                raise ValueError('Unable to find the file {} to upload'.format(
                                 upload))
            self.conf['upload'] = upload

        self.non_supported()

        directory = self.conf['directory']
        if directory is None:
            directory = os.path.join(DOT_SAGENB, 'sage_notebook.sagenb')
        else:
            directory = directory.rstrip(os.sep)
            if not directory.endswith('.sagenb'):
                directory += '.sagenb'
        # First change to the directory that contains the notebook directory
        wd, directory = os.path.split(directory)
        if not wd:
            wd = self.conf['cwd']
        os.chdir(wd)
        self.conf['wd'] = wd
        self.conf['directory'] = directory
        self.conf['absdirectory'] = os.path.abspath(directory)

        self.conf['pidfile'] = os.path.join(directory, 'sagenb.pid')

        if not self.conf['secure'] and self.conf['interface'] != 'localhost':
            print(
                '*' * 70,
                'WARNING: Running the notebook insecurely not on localhost is '
                'dangerous',
                'because its possible for people to sniff passwords and gain '
                'access to',
                'your account. Make sure you know what you are doing.',
                '*' * 70,
                sep='\n')

        if self.conf['interface'] != 'localhost' and not self.conf['secure']:
            print(
                '*' * 70,
                'WARNING: Insecure notebook server listening on external '
                'interface.',
                'Unless you are running this via ssh port forwarding, you are',
                '**crazy**! You should run the notebook with the option '
                'secure=True.',
                '*' * 70,
                sep='\n')

        self.conf['port'] = find_next_available_port(
            self.conf['interface'], self.conf['port'], self.conf['port_tries'])
        if self.conf['automatic_login']:
            print("Automatic login isn't fully implemented. You have to "
                  'manually open your web browser to the above URL.')
            self.conf['startup_token'] = '{0:x}'.format(
                random.randint(0, 2**128))
        if self.conf['secure']:
            if (not os.path.exists(self.conf['private_pem']) or
                    not os.path.exists(self.conf['public_pem'])):
                print(
                    'In order to use an SECURE encrypted notebook, you must '
                    'first run notebook.setup().',
                    'Now running notebook.setup()',
                    sep='\n')
                self.notebook_setup()
            if (not os.path.exists(self.conf['private_pem']) or
                    not os.path.exists(self.conf['public_pem'])):
                print('Failed to setup notebook.  Please try notebook.setup() '
                      'again manually.')
        #################################################################

        # first use provided values, if none, use loaded values,
        # if none use defaults

        self.notebook = notebook.load_notebook(
            self.conf['absdirectory'],
            interface=self.conf['interface'],
            port=self.conf['port'],
            secure=self.conf['secure'])
        nb = self.notebook

        self.conf['directory'] = nb.dir

        if not self.conf['quiet']:
            print('The notebook files are stored in:', nb.dir)

        if self.conf['timeout'] is not None:
            nb.conf['idle_timeout'] = self.conf['timeout']
        if self.conf['doc_timeout'] is not None:
            nb.conf['doc_timeout'] = self.conf['doc_timeout']

        nb.conf['openid'] = self.conf['openid']

        if self.conf['accounts'] is not None:
            nb.conf['accounts'] = (self.conf['accounts'])

        if ('root' in nb.user_manager and
                UN_ADMIN not in nb.user_manager):
            # This is here only for backward compatibility with one
            # version of the notebook.
            nb.create_user_with_same_password(UN_ADMIN, 'root')
            # It would be a security risk to leave an escalated account around.

        if UN_ADMIN not in nb.user_manager:
            self.conf['reset'] = True

        if self.conf['reset']:
            passwd = self.get_admin_passwd()
            if UN_ADMIN in nb.user_manager:
                nb.user_manager[UN_ADMIN].password = passwd
                print("Password changed for user {!r}.".format(UN_ADMIN))
            else:
                nb.user_manager.create_default_users(passwd)
                print(
                    'User admin created with the password you specified.',
                    '',
                    '',
                    '*' * 70,
                    '',
                    sep='\n')
                if self.conf['secure']:
                    print('Login to the Sage notebook as admin with the '
                          'password you specified above.')
            # nb.del_user('root')

        # For old notebooks, make sure that default users are always created.
        # This fixes issue #175 (https://github.com/sagemath/sagenb/issues/175)
        um = nb.user_manager
        for user in (UN_SAGE, UN_PUB):
            if user not in um:
                um.add_user(user, '', '', account_type=UAT_USER)
        if UN_GUEST not in um:
            um.add_user(UN_GUEST, '', '', account_type=UAT_GUEST)

        nb.set_server_pool(self.conf['server_pool'])
        nb.set_ulimit(self.conf['ulimit'])

        if os.path.exists('{}/nb-older-backup.sobj'.format(
                self.conf['directory'])):
            nb._migrate_worksheets()
            os.unlink('{}/nb-older-backup.sobj'.format(self.conf['directory']))
            print('Updating to new format complete.')

        nb.upgrade_model()
        nb.save()

    def run(self, args=None):
        self.parse(args)
        self.update_conf()
        if not self.conf['quiet']:
            print_open_msg(self.conf['interface'], self.conf['port'],
                           secure=self.conf['secure'])
        if self.conf['secure'] and not self.conf['quiet']:
            print(
                'There is an admin account. If you do not remember the '
                'password,',
                'quit the notebook and type `sagenb --reset`.',
                sep='\n')
        print('Executing Sage Notebook with {} server'.format(
            self.conf['server']))

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
                ssl_context.use_privatekey_file(self.conf['private_pem'])
                ssl_context.use_certificate_file(self.conf['public_pem'])
            except ImportError:
                raise RuntimeError('HTTPS cannot be used without pyOpenSSL '
                                   'installed. See the Sage README for more '
                                   'information.')
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
                                   'privateKey={private_pem}:'\
                                   'certKey={public_pem}'.format(**self.conf)
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
        s = strports.service(self.conf['strport'], site)
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
            'certfile': self.conf['public_pem'],
            'keyfile': self.conf['private_pem']
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
            open_page(SAGE_BROWSER, self.conf['interface'], self.conf['port'],
                      self.conf['secure'],
                      '/?startup_token={}'.format(self.conf['startup_token']))
        if self.conf['upload']:
            open_page(
                SAGE_BROWSER, self.conf['interface'], self.conf['port'],
                self.conf['secure'],
                '/upload_worksheet?url=file://{}'.format(
                    urllib.quote(self.conf['upload'])))

    def write_pid(self):
        with open(self.conf['pidfile'], "w") as pidfile:
            pidfile.write(str(os.getpid()))

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

    def notebook_setup(self):
        if not os.path.exists(self.conf['conf_path']):
            os.makedirs(self.conf['conf_path'])

        if which('openssl') is None:
            raise RuntimeError('You must install openssl to use the secure'
                               'notebook server.')

        dn = raw_input('Domain name [localhost]: ').strip()
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
            'openssl genrsa -out {} {}'.format(self.conf['private_pem'], bits),
            'Using openssl to generate key')
        system_command(
            'openssl req  -key {} -out {} -newkey rsa:{} -x509 '
            '-days {} -subj {}'.format(
                self.conf['private_pem'], self.conf['public_pem'], bits,
                days, distinguished_name))

        # Set permissions on private cert
        os.chmod(self.conf['private_pem'], 0600)

        print('Successfully configured notebook.')


if __name__ == '__main__':
    nf = NotebookFrontend()
    nf()
