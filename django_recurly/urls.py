from django.conf.urls.defaults import *
from django_recurly.views import push_notifications, success_token, \
    change_plan, account, invoice

urlpatterns = patterns("",
    url(r"^notification/$", push_notifications, name="notification"),
    url(r"^success/$", success_token, name="success_url"),
    url(r"^change-plan/$", change_plan, name="change_plan"),
    url(r"^account/$", account, name="account"),
    url(r"^invoice/(?P<uuid>[a-z0-9]+)\.pdf$", invoice, name="invoice"),
)
