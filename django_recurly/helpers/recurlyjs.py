"""Helpers for working with Recurly's recurly.js packge"""
from django.template.loader import render_to_string

from django_recurly.conf import SUBDOMAIN, DEFAULT_CURRENCY
from django_recurly.utils import dump, to_camel
from django_recurly import recurly


def get_signature(obj):
    return recurly.js.sign(obj)


def get_config(subdomain=SUBDOMAIN, currency=DEFAULT_CURRENCY):
    return render_to_string("django_recurly/config.js", {
        "subdomain": subdomain,
        "currency": currency,
    })


def get_subscription_form(plan_code, user, quantity=1, account=None, target_element='#recurly-container', success_handler=None):
    # Protected params
    data = {
        'plan_code': plan_code,
        'subscription': {
            'plan_code': plan_code,
            'quantity': quantity,
        },
        'account': {
            'username': user.username,
        },
        'addressRequirement': 'none',
        'enableCoupons': False,
    }

    data['signature'] = get_signature(data)

    # Unprotected params
    data['target'] = target_element

    if account is not None:
        data['account'] = account.to_dict()

    if success_handler is not None:
        data['success_handler'] = success_handler

    data['json'] = dump(to_camel(data))

    return render_to_string("django_recurly/build_subscription_form.js", data)


def get_billing_info_update_form(user, account, target_element='#recurly-container', success_handler=None):
    # Protected params
    data = {
        'account_code': account.account_code,
        'account': {
            'account_code': account.account_code,
            'username': account.username,
        },
        'addressRequirement': 'none',
    }

    data['signature'] = get_signature(data)

    # Unprotected params
    data['target'] = target_element
    data['account'] = account.to_dict()
    data['billing_info'] = account.billing_info.to_dict()

    if success_handler is not None:
        data['success_handler'] = success_handler

    data['json'] = dump(to_camel(data))

    return render_to_string("django_recurly/build_billing_info_update_form.js", data)
