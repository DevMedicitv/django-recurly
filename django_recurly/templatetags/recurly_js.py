"""Template tags for working with Recurly.js"""

from django import template
from django.template import Library, Node, Variable, loader
from django.template.context import Context

from django_recurly.helpers.recurlyjs import get_config, get_subscription_form

register = template.Library()

@register.inclusion_tag('django_recurly/base_script.html', takes_context=True)
def recurly_script_block(context, plan_code):
    return {
        'user': context['user'],
        'plan_code': plan_code
    }

@register.simple_tag
def recurly_config():
    return get_config()

@register.simple_tag(takes_context=True)
def subscription_form(context, plan_code):
    # TODO: Change context['user'] to the user's recurly account info
    return get_subscription_form(plan_code=plan_code, account=context['user'])