from django.shortcuts import render_to_response
from django.template import RequestContext
from django.http import HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required

import logging

from .decorators import recurly_basic_authentication
from .utils import dump, safe_redirect
from . import recurly, models, signals

logger = logging.getLogger(__name__)

@csrf_exempt
@recurly_basic_authentication
@require_POST
def push_notifications(request):

    logger.debug(request.raw_post_data)

    xml = request.raw_post_data
    objects = recurly.objects_for_push_notification(xml.strip())

    logger.debug("Notification objects: ")
    logger.debug(dump(objects))

    try:
        signal = getattr(signals, objects['type'])
    except AttributeError:
        return HttpResponseBadRequest("Invalid notification name.")

    # data is being passed for backwards capability.
    signal.send(sender=recurly, xml=xml, **objects)
    return HttpResponse()

@login_required
@require_POST
def change_plan(request):
    old_plan = request.POST.get("ref_plan_code")
    new_plan = request.POST.get("plan_code")

    subscription = models.Account.get_current(request.user).get_subscription(plan_code=old_plan)
    subscription.change_plan(new_plan)

    redirect_to = request.POST.get("redirect_to", None)

    return safe_redirect(request, redirect_to)

@login_required
def account(request):
    account = models.Account.get_current(request.user)
    subscriptions = account.get_current_subscriptions()
    plans = models.Subscription.getPlans()

    c = {
        "account": account,
        "subscriptions": subscriptions,
        "plans": plans
    }

    return render_to_response("django_recurly/account.html", c, RequestContext(request))
