"""Template tags for working with Recurly's API"""

from django import template

from django_recurly.helpers.api import get_change_plan_form

register = template.Library()

@register.simple_tag
def change_plan_form(plan_code, subscription_id):
    return get_change_plan_form(plan_code, subscription_id)
