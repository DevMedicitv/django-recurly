from django.template.loader import render_to_string

def get_change_plan_form(plan_code, subscription_id):
    return render_to_string("django_recurly/change_plan_form.html", {
        "plan_code": plan_code,
        "subscription_id": subscription_id,
    })