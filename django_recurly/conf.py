# -*- coding: utf-8 -*-

from django.conf import settings
import recurly


### Recurly API Settings ###

API_KEY = getattr(settings, 'RECURLY_API_KEY', None)
SUBDOMAIN = getattr(settings, 'RECURLY_SUBDOMAIN', None)

JS_PRIVATE_KEY = getattr(settings, 'RECURLY_JS_PRIVATE_KEY', None)
CA_CERTS_FILE = getattr(settings, 'RECURLY_CA_CERTS_FILE', None)

DEFAULT_CURRENCY = getattr(settings, 'RECURLY_DEFAULT_CURRENCY', 'USD')

# The username & password used to authorise Recurly's
# postback notifications. In the format "username:password"
HTTP_AUTHENTICATION = getattr(settings, 'RECURLY_HTTP_AUTHENTICATION', None)

# You probably don't need to mess with these, but just in case.
BASE_URI = getattr(settings, 'RECURLY_BASE_URI', None)


### Django settings ###

# For the love of all things holy, please keep this set to a sensible
# (i.e. unchanging / non daylight saving) timezone. This determines the
# timezone  in which django_recurly stores dates in the DB, so if you
# change this down the road then all your subscription dates will skew.
# The sane thing to do here is to keep this as UTC and handle the
# timezone conversion in your display logic.
TIME_ZONE = getattr(settings, 'TIME_ZONE', 'UTC')

### Django-Recurly settings ###

RECURLY_ACCOUNT_CODE_TO_USER = getattr(settings, 'RECURLY_ACCOUNT_CODE_TO_USER',
    None)


# Configure the Recurly client
recurly.API_KEY = API_KEY

if JS_PRIVATE_KEY is not None:
    recurly.js.PRIVATE_KEY = JS_PRIVATE_KEY

if CA_CERTS_FILE is not None:
    recurly.CA_CERTS_FILE = CA_CERTS_FILE

if DEFAULT_CURRENCY is not None:
    recurly.DEFAULT_CURRENCY = DEFAULT_CURRENCY

if BASE_URI is not None:
    recurly.BASE_URI = BASE_URI
