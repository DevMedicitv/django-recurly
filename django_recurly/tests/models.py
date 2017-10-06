import unittest
import time
import datetime

from django.test import TestCase

from django_recurly.tests.base import BaseTest
from django_recurly.models import *

from mock import patch, Mock


class AccountModelTest(BaseTest):

    def _get_billing_info_creation_params(self):
        return dict(
            first_name = "jane_billing",
            last_name = "doe_billing",

            company = "my_billed_company",

            address1 = "My first billing address",
            address2 = "My second billing address",

            city = "my_billing_city",

            state = "California",

            zip = "68998",
            country = "USA",
            phone = "0123456789",

            vat_number = "US118822",
            ip_address = "99.77.22.33",
            #ip_address_country = "France", -> only set by Recurly

            # If billing_type credit_card
            #card_type = "Visa",  -> only set by Recurly
            month = 5,
            year = 2019,
            number = "4111-1111-1111-1111",  # SPECIAL, only in INPUT of webservice

            # If billing_type paypal
            ###paypal_billing_agreement_id = "2836375363",
        )

    def _get_account_creation_params(self):
        return dict(
            account_code="mytest_%s" % int(time.time()),
            state = "closed",
            username = "jane_username",
            email = "jane@doe.fr",
            cc_emails = "jane1@doe.fr,jane2@doe.fr",
            first_name = "jane",
            last_name = "doe",
            company_name = "my_company",
            vat_number = "182672725",
            tax_exempt = True,

            accept_language = "fr-FR",
            hosted_login_token = "888666555",
        )

    def test_modelify_account(self):

        account_input_params = self._get_account_creation_params()

        all_input_params = account_input_params.copy()
        all_input_params["billing_info"] = self._get_billing_info_creation_params()

        account = Account.create(
            **all_input_params
        )
        print(account)

        account_model_fields = dict((key, getattr(account, key))
                                    for (key, input_value) in account_input_params.items())
        print("FINAL MODEL FIELDS", account_model_fields)


        # Check that local Account model has been properly updated by WS output
        for (key, input_value) in sorted(account_input_params.items()):
            if key in ["tax_exempt"]:
                continue  # these params are NOT sent back, for whatever reason???
            model_value = getattr(account, key)
            assert model_value == input_value
        for key in ("created_at", "updated_at"):
            value = getattr(account, key)
        assert account.closed_at is None

        




    def test_handle_notification_creating(self):
        data = self.parse_xml(self.push_notifications["new_subscription_notification-ok"])
        account, subscription = Account.handle_notification(**data)

        account, subscription = Account.handle_notification(**data)

        self.assertEqual(Account.objects.count(), 1)
        self.assertEqual(Subscription.objects.count(), 1)

        # Lets be thorough here
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
        self.assertEqual(subscription.activated_at, datetime.datetime(2009, 11, 22, 21, 10, 38))  # Phew, its in UTC now :)

        self.assertSignal("account_opened")
        self.assertNoSignal("account_closed")

    def test_handle_notification_updating_canceled(self):
        data = self.parse_xml(self.push_notifications["new_subscription_notification-ok"])
        Account.handle_notification(**data)

        self.resetSignals()

        data = self.parse_xml(self.push_notifications["canceled_subscription_notification-ok"])
        account, subscription = Account.handle_notification(**data)

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

        # Account was 'canceled', but is still technically open until is expires
        self.assertNoSignal("account_opened")
        self.assertNoSignal("account_closed")

    def test_handle_notification_updating_expired(self):
        data = self.parse_xml(self.push_notifications["new_subscription_notification-ok"])
        Account.handle_notification(**data)

        self.resetSignals()

        data = self.parse_xml(self.push_notifications["expired_subscription_notification-ok"])
        account, subscription = Account.handle_notification(**data)

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
        account, subscription = Account.handle_notification(**data)

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

        self.assertEqual(subscription.activated_at, datetime.datetime(2011, 9, 14, 19, 14, 14))

        # The subscription was created as 'expired' right away, so no signals
        self.assertNoSignal("account_opened")
        self.assertNoSignal("account_closed")

    def test_handle_notification_new_after_expired(self):
        data = self.parse_xml(self.push_notifications["new_subscription_notification-ok"])
        Account.handle_notification(**data)

        data = self.parse_xml(self.push_notifications["expired_subscription_notification-ok"])
        Account.handle_notification(**data)

        self.resetSignals()

        data = self.parse_xml(self.push_notifications["new_subscription_notification-ok"])
        Account.handle_notification(**data)

        self.assertEqual(Account.objects.count(), 1)
        # We should now have the old expired subscription, plus the fresh new one
        self.assertEqual(Subscription.objects.count(), 2)
        self.assertEqual(Subscription.objects.latest().state, "active")

        self.assertSignal("account_opened")
        self.assertNoSignal("account_closed")

    def test_get_current(self):
        from django_recurly.utils import recurly
        recurly.Account.get = Mock(return_value=recurly.Account.from_element(self.resources["account-ok"]))
        recurly.Subscription.get = Mock(return_value=recurly.Subscription.from_element(self.resources["subscription-ok"]))

        data = self.parse_xml(self.push_notifications["new_subscription_notification-ok"])
        account, subscription = Account.handle_notification(**data)
        print(account, subscription)

        self.assertEqual(account.user.username, "verena")


class SubscriptionModelTest(BaseTest):

    def test_is_current(self):
        data = self.parse_xml(self.push_notifications["new_subscription_notification-ok"])
        account, subscription = Account.handle_notification(**data)

        self.assertTrue(Subscription.objects.latest().is_current())

        data = self.parse_xml(self.push_notifications["expired_subscription_notification-ok"])
        account, subscription = Account.handle_notification(**data)

        self.assertFalse(Subscription.objects.latest().is_current())

    def test_is_trial(self):
        data = self.parse_xml(self.push_notifications["new_subscription_notification-ok"])
        account, subscription = Account.handle_notification(**data)

        self.assertFalse(subscription.is_trial())

        subscription.trial_ends_at = datetime.datetime.now() + datetime.timedelta(days=1)
        subscription.save()

        self.assertTrue(subscription.is_trial())


class PaymentModelTest(BaseTest):

    def test_handle_payment_successful(self):
        data = self.parse_xml(self.push_notifications["new_subscription_notification-ok"])
        account, subscription = Account.handle_notification(**data)

        data = self.parse_xml(self.push_notifications["successful_payment_notification-ok"])
        payment = Payment.handle_notification(**data)

        self.assertEqual(Payment.objects.count(), 1)

        payment = Payment.objects.all().latest()
        self.assertEqual(payment.transaction_id, "a5143c1d3a6f4a8287d0e2cc1d4c0427")
        self.assertEqual(payment.invoice_id, "ffc64d71d4b5404e93f13aac9c63bxxx")
        self.assertEqual(payment.action, "purchase")

        self.assertEqual(payment.date, datetime.datetime(2009, 11, 22, 21, 10, 38))
        self.assertEqual(payment.amount_in_cents, 1000)
        self.assertEqual(payment.status, "success")
        self.assertEqual(payment.message, "Bogus Gateway: Forced success")

    def test_handle_refund(self):
        data = self.parse_xml(self.push_notifications["new_subscription_notification-ok"])
        account, subscription = Account.handle_notification(**data)

        data = self.parse_xml(self.push_notifications["successful_refund_notification-ok"])
        payment = Payment.handle_notification(**data)

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
        account, subscription = Account.handle_notification(**data)

        data = self.parse_xml(self.push_notifications["void_payment_notification-ok"])
        payment = Payment.handle_notification(**data)

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
        account, subscription = Account.handle_notification(**data)

        data = self.parse_xml(self.push_notifications["failed_payment_notification-ok"])
        payment = Payment.handle_notification(**data)

        self.assertEqual(Payment.objects.count(), 1)

        payment = Payment.objects.all().latest()
        self.assertEqual(payment.transaction_id, "a5143c1d3a6f4a8287d0e2cc1d4c0427")
        self.assertEqual(payment.invoice_id, None)
        self.assertEqual(payment.action, "purchase")

        self.assertEqual(payment.amount_in_cents, 1000)
        self.assertEqual(payment.status, "declined")
        self.assertEqual(payment.message, "This transaction has been declined")
