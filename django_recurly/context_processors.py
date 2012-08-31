from django.utils.functional import lazy
from django.utils import timezone
from decorator import decorator
import re

import django_recurly.helpers.recurlyjs

def recurly(request):
    """
    Context processor that provides useful info about recurly to be used with
    Recurly.js for client-side processing.
    See: https://docs.recurly.com/recurlyjs
    """
    from django_recurly import conf, recurly

    return {
        'recurly_subdomain': conf.SUBDOMAIN,
        'recurly_currency': conf.DEFAULT_CURRENCY
    }