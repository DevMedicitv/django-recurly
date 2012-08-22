import base64

from django.shortcuts import render_to_response
from django.template import RequestContext
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.conf import settings
from django.utils.crypto import constant_time_compare

import logging

import recurly
from recurly import objects_for_push_notification

from .decorators import recurly_basic_authentication
from . import signals

logger = logging.getLogger(__name__)


@csrf_exempt
@recurly_basic_authentication
@require_POST
def push_notifications(request):

    logger.debug(request.raw_post_data)

    xml = request.raw_post_data
    objects = objects_for_push_notification(xml)

    try:
        signal = getattr(signals, objects['type'])
    except AttributeError:
        return HttpResponseBadRequest("Invalid notification name.")

    # data is being passed for backwards capability.
    signal.send(sender=recurly, xml=xml, **objects)
    return HttpResponse()

@require_POST
def change_plan(request):
    new_plan = request.POST.get("plan_code")

    subscription = Account.get_current(request.user).get_current_subscription()
    subscription.change_plan(new_plan)

    redirect_to = request.POST.get("redirect_to", None)

    return safe_redirect(redirect_to)

def account(request):
    account = Account.get_current(request.user)
    subscription = account.get_current_subscription()

    c = {
        "account": account,
        "subscription": subscription,
        "plans": settings.RECURLY_PLANS
    }

    return render_to_response("django_recurly/account.html", c, RequestContext(request))
