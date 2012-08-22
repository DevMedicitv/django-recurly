"""Template tags for working work Recurly's API"""

from django import template
from django.template import Library, Node, Variable, loader
from django.template.context import Context

from django_recurly.helpers.api import get_change_plan_form

register = template.Library()

@register.simple_tag
def change_plan_form(plan_code):
    return get_change_plan_form(plan_code)

