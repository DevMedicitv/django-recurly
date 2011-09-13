#!/usr/bin/env python

# Based largely on:
# http://ericholscher.com/blog/2009/jun/29/enable-setuppy-test-your-django-apps/

import os, sys
os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'

test_dir = os.path.dirname(__file__)
sys.path.insert(0, test_dir)

from django.test.utils import get_runner
from django.conf import settings

def runtests():
    test_runner_class = get_runner(settings)
    test_runner = test_runner_class(verbosity=1, interactive=True)
    failures = test_runner.run_tests(["django_recurly"])
    sys.exit(failures)

if __name__ == '__main__':
    runtests()
