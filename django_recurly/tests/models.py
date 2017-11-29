import unittest
import time
import datetime
import sys

import pytest
from django.test import TestCase
from mock import patch, Mock
import recurly

from django_recurly.provisioning import update_local_account_data_from_recurly_resource, \
    update_local_subscription_data_from_recurly_resource, update_full_local_data_for_account_code, \
    create_and_sync_recurly_account, create_and_sync_recurly_subscription, update_and_sync_recurly_billing_info, update_and_sync_recurly_subscription
from django_recurly.tests.base import BaseTest
from django_recurly.models import *




class AccountModelTest(BaseTest):

    def _get_billing_info_creation_params(self, **kwargs):
        res = dict(
            first_name = "jane_billing",
            last_name = "doe_billing",

            company = "my_billed_company",

            address1 = "My first billing address",
            address2 = "My second billing address",

            city = "my_billing_city",

            state = "Mississipi",

            zip = "68998",
            country = "FR",
            phone = "0123456789",

            vat_number = "FR118822",  # gets prepended country, if not identical
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
        res.update(kwargs)
        return res

    def _get_account_creation_params(self):
        return dict(
            account_code="mytest_%s" % int(time.time()),
            ## IGNORED state = "closed",
            username = "jane_username",
            email = "jane@doe.fr",
            cc_emails = "jane1@doe.fr,jane2@doe.fr",
            first_name = "jane",
            last_name = "doe",
            company_name = "my_company",
            vat_number = "182672725",
            tax_exempt = True,

            accept_language = "fr-FR",
            ## IGNORED hosted_login_token = "888666555",
        )

    def _get_subscription_creation_params(self, plan_code="premium-monthly"):

        subscription_params = dict(

            currency = "EUR",

            plan_code = plan_code,

            unit_amount_in_cents = 1100,

            quantity = 2,

            # here gift card, coupon code, addresse etc. can be added

        )
        return subscription_params


    def _get_full_subscription_creation_params(self, **kwargs):
        """
        Returns a params dict with nested account/billing/subscription parameters.
        """
        return dict(
            account_params=self._get_account_creation_params(),
            billing_info_params=self._get_billing_info_creation_params(),
            subscription_params = self._get_subscription_creation_params(**kwargs),
        )



    def _create_recurly_test_account(self, plan_codes=None):

        plan_codes = plan_codes or []

        account_input_params = self._get_account_creation_params()
        billing_info_input_params = self._get_billing_info_creation_params()
        account = create_and_sync_recurly_account(
            account_params=account_input_params,
            billing_info_params=billing_info_input_params
        )

        for plan_code in plan_codes:
            recurly_account = account.get_recurly_account()
            subscription_params = self._get_subscription_creation_params(
                plan_code=plan_code,
            )
            subscription = create_and_sync_recurly_subscription(
                subscription_params=subscription_params,
                account_params=recurly_account,
            )
            assert not subscription.account  # no auto-linking
            account.subscriptions.add(subscription)

        assert account.subscriptions.count() == len(plan_codes)
        return account


    def test_update_and_sync_recurly_billing_info(self):
        account_input_params = self._get_account_creation_params()
        account = create_and_sync_recurly_account(
            account_params=account_input_params,
            billing_info_params=None
        )
        assert not hasattr(account, "billing_info"), account.billing_info

        billing_info_input_params = self._get_billing_info_creation_params()
        account2 =update_and_sync_recurly_billing_info(account, billing_info_params=billing_info_input_params)

        assert account.pk == account2.pk

        assert not hasattr(account, "billing_info"), account.billing_info  # not sync'ed
        assert account2.billing_info.country == "FR"  # well sync'ed


    def test_update_local_account_data_from_recurly_resource(self):

        account_input_params = self._get_account_creation_params()
        billing_info_input_params = self._get_billing_info_creation_params()
        account = create_and_sync_recurly_account(
            account_params=account_input_params,
            billing_info_params=billing_info_input_params
        )
        print(account)

        account_model_fields = dict((key, getattr(account, key))
                                    for (key, input_value) in account_input_params.items())
        print("FINAL MODEL FIELDS", account_model_fields)

        # missing when not configured in recurly console
        assert not hasattr(account.get_recurly_account(), "tax_exempt")

        # Check that local Account model has been properly updated by WS output
        for (key, input_value) in sorted(account_input_params.items()):
            if key in ["tax_exempt"]:
                continue  # FIXE these params are NOT sent back if taxes are disabled in recurly console
            model_value = getattr(account, key)
            assert model_value == input_value
        for key in ("created_at", "updated_at"):
            value = getattr(account, key)
            assert isinstance(value, datetime.datetime)
        assert account.closed_at is None

        # Check that local BillingInfo model has been properly updated by WS output
        billing_info = account.billing_info
        for (key, input_value) in sorted(billing_info_input_params.items()):
            if key in ["number"]:
                continue  # of course card number isn't directly reflected
            model_value = getattr(billing_info, key)
            assert model_value == input_value
        assert not hasattr(billing_info, "first_six")  # not stored anymore
        assert billing_info.last_four == "1111"

        #print("SUBSCRIPTIONS", account.subscriptions)
        #print("TRANSACTIONS", account.transactions)

        # modifications of account and billing info must work fine
        remote_account = account.get_recurly_account()

        #print("\n\n\n\n/////////////////////////\n", file=sys.stderr)

        assert remote_account.first_name == "jane"
        remote_account.first_name = "newname"
        remote_account.save()

        assert remote_account.billing_info.company == "my_billed_company"
        assert remote_account.billing_info.first_name == "jane_billing"

        remote_billing_info = remote_account.billing_info
        remote_billing_info.company = "newcompany_billing"
        remote_billing_info.first_name = "newfirstname_billing"

        ##print("\n\n\n\n/////////////////////////\n", remote_billing_info.__dict__, file=sys.stderr)

        remote_billing_info.save()  # alwo works: remote_account.update_billing_info(remote_billing_info)

        ##account.update_local_data_from_recurly_resource()

        # we ensure that both current and new billing-info resources contain proper values
        for idx, acc in enumerate((account.get_recurly_account(), remote_account)):
            assert acc.first_name == "newname"
            assert acc.billing_info.company == "newcompany_billing"  # badly documented parameter
            assert acc.billing_info.first_name == "newfirstname_billing"

        # local DB not updated yet
        assert account.first_name == "jane"
        assert account.billing_info.company == "my_billed_company"
        assert account.billing_info.first_name == "jane_billing"

        update_local_account_data_from_recurly_resource(remote_account)
        account.refresh_from_db()  # important
        account.billing_info.refresh_from_db()  # important

        assert account.first_name == "newname"
        assert account.billing_info.company == "newcompany_billing"
        assert account.billing_info.first_name == "newfirstname_billing"

        remote_billing_info.delete()
        update_local_account_data_from_recurly_resource(remote_account)

        assert account.billing_info  # ghost object
        with pytest.raises(account.billing_info.DoesNotExist):
            account.billing_info.refresh_from_db()  # well deleted in DB



    def test_update_local_subscription_data_from_recurly_resource(self):

        meta_params = self._get_full_subscription_creation_params()
        subscription = create_and_sync_recurly_subscription(
            **meta_params
        )

        assert subscription.is_live
        assert not subscription.is_canceled
        assert subscription.is_cancellable
        assert subscription.plan_code == "premium-monthly"
        assert subscription.plan_name == "PREMIUM Monthly"

        for (key, input_value) in sorted(meta_params["subscription_params"].items()):
            model_value = getattr(subscription, key)
            assert model_value == input_value

        assert isinstance(subscription.updated_at, datetime.datetime)
        assert isinstance(subscription.current_period_ends_at, datetime.datetime)
        assert not subscription.account  # NO AUTOLINKING here

        subscription2 = update_and_sync_recurly_subscription(subscription, dict(quantity=3))

        assert subscription2.pk == subscription.pk  # "subscription" is outdated though
        assert subscription2.quantity == 3
        assert not subscription.account

        remote_subscription = subscription2.get_recurly_subscription()
        remote_subscription.cancel()  # uses "actionator" urls from XML payload

        subscription3 = update_local_subscription_data_from_recurly_resource(remote_subscription)
        assert subscription3.pk == subscription2.pk  # "subscription2" is outdated though
        assert subscription3.state == "canceled"

        assert subscription3.is_live
        assert subscription3.is_canceled
        assert not subscription3.is_cancellable

        remote_subscription = subscription3.get_recurly_subscription()
        remote_subscription.terminate(refund='none')  # uses "actionator" urls from XML payload

        subscription4 = update_local_subscription_data_from_recurly_resource(remote_subscription)
        assert subscription4.pk == subscription3.pk  # "subscription3" is outdated though
        assert subscription4.state == "expired"

        assert not subscription4.is_live
        assert not subscription4.is_canceled
        assert not subscription4.is_cancellable


    def test_update_full_local_data_for_account_code(self):

        _account = self._create_recurly_test_account(plan_codes=["premium-annual", "premium-monthly"])
        assert _account.subscriptions.count() == 2  # untouched
        _subscription = _account.subscriptions.first()
        subscription_uuids = [x.uuid for x in _account.subscriptions.all()]

        # full refresh
        account = update_full_local_data_for_account_code(account_code=_account.account_code)
        assert account.subscriptions.count() == 2  # untouched
        assert account.pk == _account.pk

        # we modify remote recurly state

        meta_params = self._get_full_subscription_creation_params()
        rogue_subscription = create_and_sync_recurly_subscription(**meta_params)  # has different Account
        rogue_subscription.account = account  # we introduce incoherence
        rogue_subscription.save()

        assert account.subscriptions.count() == 3

        subscription_params = self._get_subscription_creation_params(plan_code="gift-3-months")

        billing_info_params = self._get_billing_info_creation_params(last_name="NewDoeBilling")
        new_subscription = create_and_sync_recurly_subscription(
            account_params=account.get_recurly_account(), # linked to same Account as others
            billing_info_params=billing_info_params,  # OVERRIDE
            subscription_params=subscription_params
        )

        _subscription.get_recurly_subscription().terminate(refund='partial')

        assert account.subscriptions.count() == 3  # not yet refreshed

        __account = update_full_local_data_for_account_code(account_code=_account.account_code)
        assert __account.pk == account.pk
        assert __account.billing_info.last_name == "NewDoeBilling"

        subscription_uuids2 = [x.uuid for x in account.subscriptions.all()]
        assert account.subscriptions.count() == 3

        # rogue_subscription has been removed, new_subscription has been attached
        assert set(subscription_uuids2) == set(subscription_uuids) | {new_subscription.uuid}


    def test_get_pending_subscription_or_none(self):

        account = self._create_recurly_test_account(plan_codes=["premium-annual"])
        subscription = account.get_live_subscription_or_none()
        assert subscription
        assert subscription.plan_code == "premium-annual"

        pending = subscription.get_pending_subscription_or_none()
        assert pending is None

        subscription_params = dict(
            timeframe="renewal",
            plan_code="premium-monthly",
            quantity=1,
        )
        subscription = update_and_sync_recurly_subscription(subscription, subscription_params)
        assert subscription
        assert subscription.plan_code == "premium-annual"  # unchanged yet

        pending = subscription.get_pending_subscription_or_none()
        assert pending
        assert pending.plan_code == "premium-monthly"
        assert pending.quantity == 1
        assert pending.current_period_ends_at is None
        assert pending.state == "active"  # weird but not "future"


    def ___test_plan_currencies(self):
        plan = recurly.Plan.get("test-plan")
        print(">>>>>>", plan.unit_amount_in_cents.currencies)
        #addbreakage

'''
    # ------------------------------------- BROKEN STUFFS BELOW




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

'''
