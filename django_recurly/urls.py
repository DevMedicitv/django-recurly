from django.conf.urls.defaults import *
from django.views.generic.simple import direct_to_template

from django_recurly.views import push_notifications, change_plan, account

urlpatterns = patterns("",
    url(r"^recurly-notification/$", push_notifications, name="recurly_notification"),
    url(r"^change-plan/$", change_plan, name="change_plan"),
    url(r"^account/$", account, name="account"),
)
