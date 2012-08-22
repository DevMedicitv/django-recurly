"""Template tags for working work Recurly's hosted payment pages"""

from django import template
from django.template import Library, Node, Variable, loader
from django.template.context import Context

from django_recurly.helpers.hosted import get_subscribe_url

register = template.Library()

@register.simple_tag
def subscribe_url(user, plan_code, quantity=1):
    return get_subscribe_url(user, plan_code, quantity)

