from django.template.loader import render_to_string

from django_recurly.models import Account, Subscription

def get_change_plan_form(plan_code):
    return render_to_string("django_recurly/change_plan_form.html", {
        "plan_code": plan_code,
    })