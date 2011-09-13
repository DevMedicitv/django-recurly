# -*- coding: utf-8 -*-

import os.path

# These should NOT be valid credentials
RECURLY_USERNAME = "dummy_username"
RECURLY_PASSWORD = "dummy_password"
RECURLY_SUBDOMAIN = "dummy_subdomain"

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

SECRET_KEY = "r0eCEzRzC8s2u8h3L!*tr9v,kz!gm:"

# local_settings.py can be used to override environment-specific settings
# like database and email that differ between development and production.
try:
    from local_settings import *
except ImportError:
    pass