"""Helpers for working with Recurly's recurly.js packge"""
from django.template.loader import render_to_string

from django_recurly.conf import SUBDOMAIN, DEFAULT_CURRENCY
from django_recurly.models import Account, Subscription
from django_recurly import recurly

def get_signature(obj):
    return recurly.js.sign(obj)

def get_config(subdomain=SUBDOMAIN, currency=DEFAULT_CURRENCY):
    return render_to_string("django_recurly/config.js", {
        "subdomain": subdomain,
        "currency": currency,
    })

def get_subscription_form(plan_code, account=None):
    data = {
        'subscription': recurly.Subscription(plan_code=plan_code).to_dict()
    }

    data['signature'] = get_signature(data)

    if account is not None:
        data['account'] = recurly.Account(username=account.username, first_name=account.first_name, last_name=account.last_name, email=account.email).to_dict();

    return render_to_string("django_recurly/build_subscription_form.js", data)