from django.http import HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

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
