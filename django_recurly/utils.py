import urllib
import urlparse

from django.shortcuts import redirect

from django.conf import settings

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