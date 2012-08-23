# -*- coding: utf-8 -*-

import os.path

# These should NOT be valid credentials
API_KEY = 'dummy_api_key'
JS_PRIVATE_KEY = "dummy_js_private_key"
CA_CERTS_FILE = ''
DEFAULT_CURRENCY = 'USD'

RECURLY_SUBDOMAIN = 'example'

RECURLY_PLANS = ("micro", "small", "medium", "large")

# The username & password used to authorise Recurly's
# postback notifications. In the format "username:password"
RECURLY_HTTP_AUTHENTICATION = "1234567890abcdefghijklmnop:abcdefghijklmnop0987654321"

# For the love of all things holy, please keep this set to a sensible
# (i.e. unchanging / non daylight saving) timezone. This determines the
# timezone  in which django_recurly stores dates in the DB, so if you
# change this down the road then all your subscription dates will skew.
# The sane thing to do here is to keep this as UTC and handle the
# timezone conversion in your display logic.
TIME_ZONE = "UTC"

PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": "%s/dev.db" % PROJECT_ROOT,
        "USER": "",
        "PASSWORD": "",
        "HOST": "",
        "PORT": "",
    }
}

INSTALLED_APPS = (
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django_recurly",
)

SITE_ID = 1

ROOT_URLCONF = "django_recurly.urls"

# local_settings.py can be used to override environment-specific settings
# like database and email that differ between development and production.
try:
    from local_settings import *
except ImportError:
    pass