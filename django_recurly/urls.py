from django.conf.urls.defaults import *
from django.views.generic.simple import direct_to_template

from django_recurly.views import push_notifications

urlpatterns = patterns("",
    url(r"^recurly-notification/$", push_notifications, name="recurly_notification"),
)
