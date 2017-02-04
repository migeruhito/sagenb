#!/usr/bin/env python

##########################################################
# The setup.py for the Sage Notebook
##########################################################

import os
from setuptools import setup


def lremove(string, prefix):
    while string.startswith(prefix):
        string = string[len(prefix):]
    return string


def all_files(dir, prefix):
    """
    Return list of all filenames in the given directory, with prefix
    stripped from the left of the filenames.
    """

    X = []
    for F in os.listdir(dir):
        ab = dir+'/'+F
        if os.path.isfile(ab):
            X.append(lremove(ab, prefix))
        elif os.path.isdir(ab):
            X.extend(all_files(ab, prefix))
    return X


install_requires = [
    'twisted>=11.0.0',
    'flask>=0.10.1',
    'flask-openid',
    'flask-autoindex',
    'flask-babel'
    'flask-themes2',
    'future',
    'smtpsend',
    'pexpect',
    'docutils',
    'jsmin',
    'pyopenssl',
    'service_identity',
    'appdirs',
    'tornado',  # this is optional
    ]


setup(
    name='sagenb',
    version='0.13',
    description='The Sage Notebook',
    license='GNU General Public License (GPL) v3+',
    author='William Stein et al.',
    author_email='sage-notebook@googlegroups.com',
    url='http://github.com/sagemath/sagenb',
    install_requires=install_requires,
    dependency_links=[],
    test_suite='sagenb.testing.run_tests.all_tests',
    packages=[
        'sagewui',
        'sagewui.blueprints',
        'sagewui.gui',
        'sagewui.sage_server',
        'sagewui.storage',
        'sagewui.util',
        'sagewui.compress',
        'sagenb',
        'sagenb.notebook',
        'sagenb.testing',
        'sagenb.testing.tests',
        'sagenb.testing.selenium',
        ],
    scripts=['sagewui/static/sage3d/sage3d'],
    package_data={
        'sagewui': (all_files('sagewui/static', 'sagewui/') +
                    all_files('sagewui/translations', 'sagewui/') +
                    all_files('sagewui/themes', 'sagewui/'))
        },
    zip_safe=False,
)
