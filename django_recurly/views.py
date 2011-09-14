import base64

from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.conf import settings
from django.utils.crypto import constant_time_compare

from django_recurly.client import get_client
from django_recurly.decorators import recurly_basic_authentication

from django_recurly import signals

@csrf_exempt
@recurly_basic_authentication
@require_POST
def push_notifications(request):
    if 'HTTP_AUTHORIZATION' not in request.META:
        return HttpResponseForbidden("No HTTP_AUTHORIZATION information found")
    
    auth = request.META['HTTP_AUTHORIZATION'].split()
    if len(auth) != 2:
        return HttpResponseForbidden("Invalid auth data")
    
    if auth[0].lower() != "basic":
        return HttpResponseForbidden("Only basic auth is supported")
    
    uname, passwd = base64.b64decode(auth[1]).split(':')
    if not constant_time_compare(uname, settings.RECURLY_NOTIFICATION_USERNAME) or not constant_time_compare(passwd, settings.RECURLY_NOTIFICATION_PASSWORD):
        return HttpResponseForbidden("Invalid username/password")
    
    client = get_client()
    
    name = client.parse_notification(request.raw_post_data)
    
    try:
        signal = getattr(signals, name)
    except AttributeError:
        return HttpResponseBadRequest("Invalid notification name.")
    
    signal.send(sender=client, data=client.response)
    
    return HttpResponse()
