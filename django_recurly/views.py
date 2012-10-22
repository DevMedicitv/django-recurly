from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext
from django.http import HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required

from .decorators import recurly_basic_authentication
from .utils import safe_redirect, recurly
from . import models, signals

import logging

logger = logging.getLogger(__name__)


@csrf_exempt
@recurly_basic_authentication
@require_POST
def push_notifications(request):

    xml = request.raw_post_data
    objects = recurly.objects_for_push_notification(xml.strip())

    try:
        signal = getattr(signals, objects['type'])
    except AttributeError:
        return HttpResponseBadRequest("Invalid notification type.")

    signal.send(sender=recurly, xml=xml, **objects)
    return HttpResponse()


@login_required
@require_POST
def success_token(request):
    recurly_token = request.POST.get("recurly_token")
    token = models.Token(token=recurly_token)

    try:
        result = recurly.js.fetch(recurly_token)
    except Exception as e:
        logger.warning("Failed to fetch details for success token '%s': %s", recurly_token, e)
        token.account = get_object_or_404(models.Account.active, user=request.user)
        token.save()
        return HttpResponse()

    # Update the associated Account
    account = models.Account.sync(recurly_account=result.account())
    account.save()

    token.account = account
    token.cls = result.nodename

    if result.nodename == 'billing_info':
        token.identifier = token.account.account_code
        signal = signals.billing_info_token_created
    elif result.nodename == 'subscription':
        token.identifier = result.uuid
        signal = signals.subscription_token_created

        models.Subscription.sync(uuid=token.identifier)
    elif result.nodename == 'invoice':
        token.identifier = result.uuid
        signal = signals.invoice_token_created

        models.Payment.sync(uuid=token.identifier)

    token.xml = result.as_log_output(full=True)
    token.save()

    signal.send(sender=recurly, token=token, account=account)

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
