"""Helpers for working with Recurly's Hosted Payment Pages"""

import urllib

from django.conf import settings
from django.core.urlresolvers import reverse
from django.utils.http import urlquote_plus
from django.utils.encoding import iri_to_uri
from django.http import HttpResponseRedirect

from django_recurly.client import get_client
from django_recurly.utilities import random_string

SUBSCRIBE_URL = "https://%(subdomain)s.recurly.com/subscribe/%(plan_code)s/%(account_code)s/%(username)s?quantity=%(quantity)s&first_name=%(first_name)s&last_name=%(last_name)s&email=%(email)s"

def get_subscribe_url(user, plan_code, quantity=1, account_code=None):
    """Generate the URL for the hosted payment page
    
    Redirect the user to this URL to send them off to Recurly.
    
    You should not normally need to specify 'account_code'
    """
    
    params = {
        "subdomain": get_client().subdomain,
        "plan_code": urlquote_plus(plan_code),
        "account_code": urlquote_plus(account_code) if account_code else random_string(length=32),
        "username": urlquote_plus(user.username),
        
        "quantity": quantity,
        "first_name": getattr(user, "first_name", ""),
        "last_name": getattr(user, "last_name", ""),
        "email": getattr(user, "email", ""),
    }
    
    subscribe_url = iri_to_uri(SUBSCRIBE_URL % params)
    
    return subscribe_url

class SubscribeRedirect(HttpResponseRedirect):
    """A simple HTTP response class which can be returned 
    from views in order to send users to the hosted payment page"""
    
    status_code = 302

    def __init__(self, plan_code, user, quantity=1, account_code=None):
        super(HttpResponseRedirect, self).__init__()
        
        self['Location'] = get_subscribe_url(plan_code, user, quantity, account_code)
    



