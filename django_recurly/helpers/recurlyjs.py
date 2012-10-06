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


def get_subscription_form(plan_code, user, target_element='#recurly-container', protected_params={}, unprotected_params={}):
    from django_recurly.utils import dict_merge

    # Protected params
    data = {
        'plan_code': plan_code,
        'subscription': {
            'plan_code': plan_code,
        },
        'account': {
            'username': user.username,
        },
    }
    dict_merge(data, protected_params)
    data['signature'] = get_signature(data)

    # Unprotected params
    unprotected_data = {
        'target': target_element
    }
    data = dict_merge({}, unprotected_data, unprotected_params, data)
    data['json'] = dump(data, js=True)

    return render_to_string("django_recurly/build_subscription_form.js", data)


def get_billing_info_update_form(user, account, target_element='#recurly-container', protected_params={}, unprotected_params={}):
    from django_recurly.utils import dict_merge

    # Protected params
    data = {
        'account_code': account.account_code,
        'account': {
            'account_code': account.account_code,
            'username': account.username,
        },
        'addressRequirement': 'none',
    }
    dict_merge(data, protected_params)
    data['signature'] = get_signature(data)

    # Unprotected params
    unprotected_data = {
        'target': target_element,
        'distinguish_contact_from_billing_info': False,
        'account': account.to_dict(js=True),
        'billing_info': account.billing_info.to_dict(js=True)
    }
    data = dict_merge({}, unprotected_data, unprotected_params, data)
    data['json'] = dump(data, js=True)

    return render_to_string("django_recurly/build_billing_info_update_form.js", data)
