import urllib
import urlparse
import random
import string
import iso8601
import pytz

from django.conf import settings
from django.shortcuts import redirect
from django.contrib.auth.models import User

def hosted_login_url(hosted_login_token):
    return 'https://%s.recurly.com/account/%s' % (
        settings.RECURLY_SUBDOMAIN,
        hosted_login_token,
    )

def hosted_payment_page_url(plan_code, account_code, data=None):
    if data is None:
        data = {}

    return 'https://%s.recurly.com/subscribe/%s/%d?%s' % (
        settings.RECURLY_SUBDOMAIN,
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

def modelify(data, model, key_prefix="", remove_empty=False, date_fields=[]):
    fields = set(field.name for field in model._meta.fields)
    fields_by_name = dict((field.name, field) for field in model._meta.fields)
    fields.discard("id")

    if "user" in fields and data.get("username", None):
        try:
            data["user"] = User.objects.get(username=data["username"])
        except User.DoesNotExist:
            # A user may not exist if there account has been deleted
            data["user"] = None

    for k, v in data.items():
        if isinstance(v, dict):
            data.update(modelify(v, model, key_prefix=k+"_"))

    out = {}
    for k, v in data.items():
        if not k.startswith(key_prefix):
            k = key_prefix + k

        if k in fields:
            if k.endswith("_at") or k in date_fields:
                v = iso8601.parse_date(v).astimezone(tz=pytz.utc) if v else None

            # Always assume fields with limited choices shoudl be lower case
            if v and fields_by_name[k].choices:
                v = v.lower()

            if v or not remove_empty:
                out[str(k)] = v

    return out