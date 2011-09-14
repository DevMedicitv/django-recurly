from django.http import HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from django_recurly.client import get_client
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
