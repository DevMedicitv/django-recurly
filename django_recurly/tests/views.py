import unittest
import datetime

from django.test import TestCase

from django_recurly import views
from django_recurly.tests.base import BaseTest, RequestFactory
from django_recurly.models import *

rf = RequestFactory()

class PushNotificationViewTest(BaseTest):
    
    def test_all(self):
        
        for name, xml in self.push_notifications.items():
            if "_refund_" in name or "_payment_" in name:
                # This is a payment notification, for which we need an account to exist
                request = rf.post("/junk", self.push_notifications["new_subscription_notification-ok"], content_type="text/xml")
                response = views.push_notifications(request)
            
            signal, t = name.split("-")
            request = rf.post("/junk", xml, content_type="text/xml")
            
            self.resetSignals()
            response = views.push_notifications(request)
            self.assertEqual(response.status_code, 200)
            self.assertSignal(signal)
        
    
    def test_new_subscription(self):
        request = rf.post("/junk", self.push_notifications["new_subscription_notification-ok"], content_type="text/xml")
        response = views.push_notifications(request)
        self.assertEqual(response.status_code, 200)
        
        account = Account.objects.latest()
        
        self.assertEqual(Account.objects.count(), 1)
        self.assertEqual(account.user.username, "verena")
        self.assertEqual(account.first_name, "Verena")
        self.assertEqual(account.company_name, "Company, Inc.")
        self.assertEqual(account.email, "verena@test.com")
        self.assertEqual(account.account_code, "verena@test.com")
        
        subscription = account.get_current_subscription()
        self.assertEqual(Subscription.objects.count(), 1)
        self.assertEqual(subscription.plan_code, "bronze")
        self.assertEqual(subscription.plan_version, 2)
        self.assertEqual(subscription.state, "active")
        self.assertEqual(subscription.quantity, 2)
        self.assertEqual(subscription.total_amount_in_cents, 2000)
        self.assertEqual(subscription.activated_at, datetime.datetime(2009, 11, 22, 21, 10, 38)) # Phew, its in UTC now :)
        
        
        
        
    
