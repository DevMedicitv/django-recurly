import base64

from django.shortcuts import render_to_response
from django.template import RequestContext
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.conf import settings
from django.utils.crypto import constant_time_compare

from django_recurly.client import get_client
from django_recurly.utils import safe_redirect
from django_recurly.models import Account, Subscription
from django_recurly.decorators import recurly_basic_authentication

from django_recurly import signals

@csrf_exempt
@recurly_basic_authentication
@require_POST
def push_notifications(request):
    
    client = get_client()
    
    name = client.parse_notification(request.raw_post_data)
    
    try:
        signal = getattr(signals, name)
    except AttributeError:
        return HttpResponseBadRequest("Invalid notification name.")
    
    signal.send(sender=client, data=client.response)
    
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
