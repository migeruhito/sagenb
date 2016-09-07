# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

# py3: twisted.mail is not ported to py3 (20160712)
try:
    from smtpsend import send_mail
except ImportError:
    def send_mail(*args, **kwargs):
        print("send mail disabled.")
