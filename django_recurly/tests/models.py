import unittest
import datetime
import pytz

from django.test import TestCase

from django_recurly.tests.base import BaseTest
from django_recurly.models import *

class AccountModelTest(BaseTest):
    
    def test_handle_notification_creating(self):
        data = self.parse_xml(self.push_notifications["new_subscription_notification-ok"])
        account, subscription = Account.handle_notification(data)
        
        self.assertEqual(Account.objects.count(), 1)
        self.assertEqual(Subscription.objects.count(), 1)
        
        # Lets be through here
        self.assertEqual(account.user.username, "verena")
        self.assertEqual(account.first_name, "Verena")
        self.assertEqual(account.company_name, "Company, Inc.")
        self.assertEqual(account.email, "verena@test.com")
        self.assertEqual(account.account_code, "verena@test.com")
        
        subscription = account.get_current_subscription()
        self.assertEqual(subscription.plan_code, "bronze")
        self.assertEqual(subscription.plan_version, 2)
        self.assertEqual(subscription.state, "active")
        self.assertEqual(subscription.quantity, 2)
        self.assertEqual(subscription.total_amount_in_cents, 2000)
        self.assertEqual(subscription.activated_at, datetime.datetime(2009, 11, 22, 21, 10, 38)) # Phew, its in UTC now :)
        
        self.assertSignal("account_opened")
        self.assertNoSignal("account_closed")
    
    def test_handle_notification_updating_cancelled(self):
        data = self.parse_xml(self.push_notifications["new_subscription_notification-ok"])
        Account.handle_notification(data)
        
        self.resetSignals()
        
        data = self.parse_xml(self.push_notifications["canceled_subscription_notification-ok"])
        account, subscription = Account.handle_notification(data)
        
        # Lets be through here
        self.assertEqual(account.user.username, "verena")
        self.assertEqual(account.first_name, "Jane")
        self.assertEqual(account.last_name, "Doe")
        self.assertEqual(account.company_name, None)
        self.assertEqual(account.email, "janedoe@gmail.com")
        self.assertEqual(account.account_code, "verena@test.com")
        
        subscription = account.get_current_subscription()
        self.assertEqual(subscription.plan_code, "1dpt")
        self.assertEqual(subscription.plan_version, 2)
        self.assertEqual(subscription.state, "canceled")
        self.assertEqual(subscription.quantity, 1)
        self.assertEqual(subscription.total_amount_in_cents, 200)
        
        # Account was 'cancelled', but is still technically open until is expires
        self.assertNoSignal("account_opened")
        self.assertNoSignal("account_closed")
    
    def test_handle_notification_updating_expired(self):
        data = self.parse_xml(self.push_notifications["new_subscription_notification-ok"])
        Account.handle_notification(data)
        
        self.resetSignals()
        
        data = self.parse_xml(self.push_notifications["expired_subscription_notification-ok"])
        account, subscription = Account.handle_notification(data)
        
        # Lets be through here
        self.assertEqual(account.user.username, "verena")
        self.assertEqual(account.first_name, "Jane")
        self.assertEqual(account.last_name, "Doe")
        self.assertEqual(account.company_name, None)
        self.assertEqual(account.email, "janedoe@gmail.com")
        self.assertEqual(account.account_code, "verena@test.com")
        
        subscription = account.get_current_subscription()
        self.assertEqual(subscription, None)
        
        subscription = account.get_subscriptions().latest()
        self.assertEqual(subscription.plan_code, "1dpt")
        self.assertEqual(subscription.plan_version, 2)
        self.assertEqual(subscription.state, "expired")
        self.assertEqual(subscription.quantity, 1)
        self.assertEqual(subscription.total_amount_in_cents, 200)
        
        self.assertNoSignal("account_opened")
        self.assertSignal("account_closed")
    
    def test_handle_notification_updating_expired_real(self):
        # Straight in with no prior account
        data = self.parse_xml(self.push_notifications["expired_subscription_notification-real"])
        account, subscription = Account.handle_notification(data)
        
        # Lets be through here
        self.assertEqual(account.user.username, "verena")
        self.assertEqual(account.first_name, "Adam")
        self.assertEqual(account.last_name, "Charnock")
        self.assertEqual(account.company_name, None)
        self.assertEqual(account.email, "adam@continuous.io")
        self.assertEqual(account.account_code, "vKWanguTh5KcZniN0yZeFbjD8xmFfVGT")
        
        subscription = account.get_current_subscription()
        self.assertEqual(subscription, None)
        
        subscription = account.get_subscriptions().latest()
        self.assertEqual(subscription.plan_code, "micro")
        self.assertEqual(subscription.plan_version, 1)
        self.assertEqual(subscription.state, "expired")
        self.assertEqual(subscription.quantity, 1)
        self.assertEqual(subscription.total_amount_in_cents, 700)
        
        self.assertEqual(subscription.activated_at, datetime.datetime(2011, 9, 14, 19, 14, 14)) # Phew, its in UTC now :)
        
        # The subscription was created as 'expired' right away, so no signals
        self.assertNoSignal("account_opened")
        self.assertNoSignal("account_closed")
    
    def test_handle_notification_new_after_expired(self):
        data = self.parse_xml(self.push_notifications["new_subscription_notification-ok"])
        Account.handle_notification(data)
        
        data = self.parse_xml(self.push_notifications["expired_subscription_notification-ok"])
        Account.handle_notification(data)
        
        self.resetSignals()
        
        data = self.parse_xml(self.push_notifications["new_subscription_notification-ok"])
        Account.handle_notification(data)
        
        self.assertEqual(Account.objects.count(), 1)
        # We should now have the old expired subscription, plus the fresh new one
        self.assertEqual(Subscription.objects.count(), 2)
        self.assertEqual(Subscription.objects.latest().state, "active")
        
        self.assertSignal("account_opened")
        self.assertNoSignal("account_closed")
    
    def test_get_current(self):
        data = self.parse_xml(self.push_notifications["new_subscription_notification-ok"])
        account, subscription = Account.handle_notification(data)
        
        account = Account.get_current(self.user)
        self.assertEqual(account.user.username, "verena")

class SubscriptionModelTest(BaseTest):
    
    def test_is_current(self):
        data = self.parse_xml(self.push_notifications["new_subscription_notification-ok"])
        account, subscription = Account.handle_notification(data)
        
        self.assertTrue(Subscription.objects.latest().is_current())
        
        data = self.parse_xml(self.push_notifications["expired_subscription_notification-ok"])
        account, subscription = Account.handle_notification(data)
        
        self.assertFalse(Subscription.objects.latest().is_current())
        
        subscription.super_subscription = True
        subscription.save()
        
        self.assertTrue(Subscription.objects.latest().is_current())
    
    def test_is_trial(self):
        data = self.parse_xml(self.push_notifications["new_subscription_notification-ok"])
        account, subscription = Account.handle_notification(data)
        
        self.assertFalse(subscription.is_trial())
        
        subscription.trial_ends_at = datetime.datetime.now(tz=pytz.utc) + datetime.timedelta(days=1)
        subscription.save()
        
        self.assertTrue(subscription.is_trial())
    

class PaymentModelTest(BaseTest):
    
    def test_handle_payment_successful(self):
        data = self.parse_xml(self.push_notifications["new_subscription_notification-ok"])
        account, subscription = Account.handle_notification(data)
        
        data = self.parse_xml(self.push_notifications["successful_payment_notification-ok"])
        payment = Payment.handle_notification(data)
        
        self.assertEqual(Payment.objects.count(), 1)
        
        payment = Payment.objects.all().latest()
        self.assertEqual(payment.transaction_id, "a5143c1d3a6f4a8287d0e2cc1d4c0427")
        self.assertEqual(payment.invoice_id, "ffc64d71d4b5404e93f13aac9c63bxxx")
        self.assertEqual(payment.action, "purchase")
        
        self.assertEqual(payment.date, datetime.datetime(2009, 11, 22, 21, 10, 38)) # Phew, its in UTC now :)
        self.assertEqual(payment.amount_in_cents, 1000)
        self.assertEqual(payment.status, "success")
        self.assertEqual(payment.message, "Bogus Gateway: Forced success")
    
    def test_handle_refund(self):
        data = self.parse_xml(self.push_notifications["new_subscription_notification-ok"])
        account, subscription = Account.handle_notification(data)
        
        data = self.parse_xml(self.push_notifications["successful_refund_notification-ok"])
        payment = Payment.handle_notification(data)
        
        self.assertEqual(Payment.objects.count(), 1)
        
        payment = Payment.objects.all().latest()
        self.assertEqual(payment.transaction_id, "2c7a2e30547e49869efd4e8a44b2be34")
        self.assertEqual(payment.invoice_id, "ffc64d71d4b5404e93f13aac9c63b007")
        self.assertEqual(payment.action, "credit")
        
        self.assertEqual(payment.amount_in_cents, 235)
        self.assertEqual(payment.status, "success")
        self.assertEqual(payment.message, "Bogus Gateway: Forced success")
    
    def test_handle_void(self):
        data = self.parse_xml(self.push_notifications["new_subscription_notification-ok"])
        account, subscription = Account.handle_notification(data)
        
        data = self.parse_xml(self.push_notifications["void_payment_notification-ok"])
        payment = Payment.handle_notification(data)
        
        self.assertEqual(Payment.objects.count(), 1)
        
        payment = Payment.objects.all().latest()
        self.assertEqual(payment.transaction_id, "4997ace0f57341adb3e857f9f7d15de8")
        self.assertEqual(payment.invoice_id, "ffc64d71d4b5404e93f13aac9c63b007")
        self.assertEqual(payment.action, "purchase")
        
        self.assertEqual(payment.amount_in_cents, 235)
        self.assertEqual(payment.status, "void")
        self.assertEqual(payment.message, "Test Gateway: Successful test transaction")
    
    def test_handle_failed(self):
        data = self.parse_xml(self.push_notifications["new_subscription_notification-ok"])
        account, subscription = Account.handle_notification(data)
        
        data = self.parse_xml(self.push_notifications["failed_payment_notification-ok"])
        payment = Payment.handle_notification(data)
        
        self.assertEqual(Payment.objects.count(), 1)
        
        payment = Payment.objects.all().latest()
        self.assertEqual(payment.transaction_id, "a5143c1d3a6f4a8287d0e2cc1d4c0427")
        self.assertEqual(payment.invoice_id, None)
        self.assertEqual(payment.action, "purchase")
        
        self.assertEqual(payment.amount_in_cents, 1000)
        self.assertEqual(payment.status, "declined")
        self.assertEqual(payment.message, "This transaction has been declined")
    









