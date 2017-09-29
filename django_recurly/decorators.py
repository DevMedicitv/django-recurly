import functools
import base64

from django_recurly.conf import HTTP_AUTHENTICATION
from django.http import HttpResponse, HttpResponseBadRequest, \
    HttpResponseForbidden
from django.utils.crypto import constant_time_compare

def recurly_basic_authentication(fn):
    @functools.wraps(fn)
    def wrapper(request, *args, **kwargs):
        wanted_authentication = HTTP_AUTHENTICATION

        # If the user has not setup settings.RECURLY_HTTP_AUTHENTICATION then
        # we trust they are doing it at the web server level.
        if wanted_authentication is None:
            return fn(request, *args, **kwargs)

        try:
            method, auth = request.META['HTTP_AUTHORIZATION'].split(' ', 1)
        except KeyError:
            response = HttpResponse()
            response.status_code = 401
            response['WWW-Authenticate'] = 'Basic realm="Restricted"'
            return response

        try:
            if method.lower() != 'basic':
                raise ValueError()

            token = base64.b64decode(auth.strip())
            if not constant_time_compare(token, wanted_authentication):
                return HttpResponseForbidden("Access to notification API forbidden")
        except Exception as e:
            return HttpResponseBadRequest("Abnormal exception in notification API: %r" % e)

        return fn(request, *args, **kwargs)
    return wrapper
