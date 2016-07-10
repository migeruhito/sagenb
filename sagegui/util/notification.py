# -*- coding: utf-8 -*
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging

from getpass import getuser
from socket import getfqdn
from socket import gethostname

from smtpsend import send_mail

logger = logging.getLogger('notification')


class TwistedEmailHandler(logging.Handler):
    """Sends log messages via SMTP using a running twisted reactor."""

    def __init__(self, conf, level=logging.NOTSET):
        logging.Handler.__init__(self, level)
        self.conf = conf
        self.setFormatter(
            logging.Formatter('''
Host:               %(fqdn)s
Message type:       %(levelname)s
Location:           %(pathname)s:%(lineno)d
Module:             %(module)s
Function:           %(funcName)s
Time:               %(asctime)s

Message:

%(message)s

'''))

    def emit(self, record):
        fqdn = getfqdn()
        from_address = '{}@{}'.format(getuser(), gethostname())
        subject = '[sage-notebook] %s' % fqdn
        record.fqdn = fqdn
        message = self.format(record)

        recipients = self.conf['notification_recipients']
        if recipients is None:
            recipients = []
        for rcpt in recipients:
            to = rcpt.strip()
            send_mail(from_address, to, subject, message)
