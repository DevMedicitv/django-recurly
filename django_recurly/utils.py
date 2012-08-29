import urllib
import urlparse
import random
import string
import iso8601
import json
from datetime import datetime

from django.shortcuts import redirect
from django_recurly.conf import SUBDOMAIN
from django_recurly import recurly

import logging
logger = logging.getLogger(__name__)


class JsonEncoder(json.JSONEncoder):
    def default(self, obj):

        if isinstance(obj, datetime) or \
                isinstance(obj, recurly.resource.Money):
            return str(obj)

        # Resolve 'relatiator' attributes
        if callable(obj):
            return obj().to_dict()

        if isinstance(obj, recurly.SubscriptionAddOn):
            return obj.to_dict()

        try:
            if issubclass(obj, dict) or issubclass(obj, list):
                return list(obj)
        except:
            pass

        return json.JSONEncoder.default(self, obj)


def dump(obj):
    data = obj
    try:
        data = data.to_dict()
    except AttributeError:
        pass

    return json.dumps(
        data,
        sort_keys=True,
        indent=4,
        cls=JsonEncoder)


def hosted_login_url(hosted_login_token):
    return 'https://%s.recurly.com/account/%s' % (
        SUBDOMAIN,
        hosted_login_token,
    )


def hosted_payment_page_url(plan_code, account_code, data=None):
    if data is None:
        data = {}

    return 'https://%s.recurly.com/subscribe/%s/%d?%s' % (
        SUBDOMAIN,
        plan_code,
        account_code,
        urllib.urlencode(data),
    )


def safe_redirect(url, fallback="/"):
    netloc = urlparse.urlparse(url or "")[1]

    if not url:
        safe_url = fallback
    # Don't redirect the user to a different host
    elif netloc and netloc != request.get_host():
        safe_url = fallback
    else:
        safe_url = url

    return redirect(safe_url)


def random_string(length=32):
    return ''.join(random.choice(string.letters + string.digits) for i in xrange(length))
