import urllib
import urlparse
import random
import string
import iso8601
import json
import re
from datetime import datetime

from django.shortcuts import redirect
from django_recurly.conf import SUBDOMAIN
from django_recurly import recurly

import logging
logger = logging.getLogger(__name__)


class RecurlyJsonEncoder(json.JSONEncoder):
    def __init__(self, js=False, *args, **kwargs):
        super(RecurlyJsonEncoder, self).__init__(*args, **kwargs)
        self.js = js

    def default(self, obj):
        if isinstance(obj, datetime) or \
                isinstance(obj, recurly.resource.Money):
            return str(obj)

        # Resolve 'relatiator' attributes
        if callable(obj):
            result = obj()
            try:
                logger.debug(self.js)
                return result.to_dict(js=self.js)
            except:
                return result

        if isinstance(obj, recurly.Resource):
            logger.debug(self.js)
            return obj.to_dict(js=self.js)

        try:
            if issubclass(obj, dict) or issubclass(obj, list):
                return list(obj)
        except:
            pass

        return json.JSONEncoder.default(self, obj)


def dump(obj, encoder=RecurlyJsonEncoder, js=False):
    data = obj
    try:
        data = data.to_dict(js=js)
    except AttributeError:
        pass

    data = to_camel(data, js=js)
    logger.debug(data)

    return json.dumps(
        data,
        sort_keys=True,
        indent=2,
        cls=encoder,
        js=js)



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


def safe_redirect(request, url, fallback="/"):
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


def to_camel(data, js=False):
    def underscore_to_camel(match):
        return match.group()[0] + match.group()[2].upper()

    def camelize(data):
        try:
            data = data.to_dict(js=js)
        except:
            data = data

        if type(data) == type({}):
            new_dict = {}
            for key, value in data.items():
                new_key = re.sub(r"[a-z]_[a-z]", underscore_to_camel, key)
                new_dict[new_key] = camelize(value)
            return new_dict
        if type(data) in (type([]), type(())):
            for i in range(len(data)):
                data[i] = camelize(data[i])
            return data
        return data

    return camelize(data)

def from_camel(content):
    # Changes camelCase json names to object containing underscore_separated names
    data = json.loads(content)

    def camel_to_underscore(match):
        return match.group()[0] + "_" + match.group()[1].lower()

    def underscorize(data):
        if type(data) == type({}):
            new_dict = {}
            for key, value in data.items():
                new_key = re.sub(r"[a-z][A-Z]", camel_to_underscore, key)
                new_dict[new_key] = underscorize(value)
            return new_dict
        if type(data) in (type([]), type(())):
            for i in range(len(data)):
                data[i] = underscorize(data[i])
            return data
        return data

    underscored_data = underscorize(data)

    return underscored_data