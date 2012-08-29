from django.db import models
from django.db.models import Q
from django.contrib.auth.models import User
from django_extensions.db.models import TimeStampedModel
from datetime import datetime

from django_recurly.utils import random_string, dump
from django_recurly import recurly, signals

# Do these here to ensure the handlers get hooked up
import django_recurly.handlers

import logging
logger = logging.getLogger(__name__)

SUBSCRIPTION_STATES = (
    ("active", "Active"),         # Active and everything is fine
    ("canceled", "Canceled"),   # Still active, but will not be renewed
    ("expired", "Expired"),       # Did not renews, or was forcibly expired early
)

__all__ = ("Account", "Subscription", "User", "Payment")


class CurrentAccountManager(models.Manager):
    def get_query_set(self):
        return super(CurrentAccountManager, self).get_query_set().filter(canceled=False)


class CurrentSubscriptionManager(models.Manager):
    def get_query_set(self):
        return super(CurrentSubscriptionManager, self).get_query_set().filter(Q(super_subscription=True) | Q(state__in=("active", "canceled")))


class Account(TimeStampedModel):
    account_code = models.CharField(max_length=32, unique=True)
    user = models.ForeignKey(User, related_name="recurly_account", blank=True, null=True, on_delete=models.SET_NULL)
    email = models.CharField(max_length=100)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    company_name = models.CharField(max_length=100, blank=True, null=True)
    canceled = models.BooleanField(default=False)
    hosted_login_token = models.CharField(max_length=32, blank=True, null=True)

    objects = models.Manager()
    current = CurrentAccountManager()

    class Meta:
        ordering = ["-id"]
        get_latest_by = "id"

    def get_subscriptions(self):
        """Get all subscriptions for this Account

        An account may have multiple subscriptions in cases
        where old subscriptions expired.

        If you need the current subscription, consider
        using get_current_subscription()
        """
        return self.subscription_set.all()

    def get_current_subscription(self):
        try:
            return Subscription.current.filter(account=self).latest()
        except Subscription.DoesNotExist:
            return None

    def fetch_hosted_login_token(self):
        raise NotImplemented("Well, it's not. Sorry.")

    @classmethod
    def get_current(class_, user):
        return class_.current.filter(user=user).latest()

    @classmethod
    def handle_notification(class_, **kwargs):
        """Update/create an account and it's associated subscription using data from Recurly"""
        # First get/create the account
        recurly_account = recurly.Account().get(kwargs.get("account").account_code)
        account = modelify(recurly_account, class_)

        try:
            account.user = User.objects.get(username=recurly_account.username)
        except User.DoesNotExist:
            # It's possible that a user may not exist locally (e.g. deleted auth.models.User)
            account.user = None

        account.save()

        # Now get/create the subscription
        if not kwargs.get("subscription"):
            return account, None

        recurly_subscription = recurly.Subscription().get(kwargs.get("subscription").uuid)
        subscription = modelify(recurly_subscription, Subscription)

        subscription.save()

        # if not subscription:
        #     # Not found, create it
        #     # subscription = Subscription.objects.create(account=account, **subscription_data)
        #     subscription = Subscription.objects.create(**subscription_data)

        #     was_current = False
        #     now_current = subscription.is_current()
        # else:
        #     was_current = subscription.is_current()

        #     # Found, update it
        #     for k, v in subscription_data.items():
        #         setattr(subscription, k, v)
        #     subscription.save()

        #     now_current = subscription.is_current()

        # # Send account closed/opened signals
        # if was_current and not now_current:
        #     signals.account_closed.send(sender=account, account=account, subscription=subscription)
        # elif not was_current and now_current:
        #     signals.account_opened.send(sender=account, account=account, subscription=subscription)

        return account, subscription

    @classmethod
    def create_fake(class_, user, plan_code):
        """Create a fake account for a user

        Creates an account which exists in Django, but not in Recurly. This can be
        handy for testing, or the occasional time when you just want to give someone
        a paid subscription without any fuss.
        """

        account = class_.objects.create(
            account_code="fake_%s" % random_string(32 - 5),
            user=user,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            canceled=False
        )

        subscription = Subscription.objects.create(
            account=account,
            plan_code=plan_code
        )

        signals.account_opened.send(sender=account, account=account, subscription=subscription)

        return account, subscription

    def get_transactions(self):
        response = recurly.accounts.transactions(account_code=self.account_code)
        return response["transaction"]


class Subscription(models.Model):
    account = models.ForeignKey(Account)
    uuid = models.CharField(max_length=40, unique=True)
    plan_code = models.CharField(max_length=100)
    plan_version = models.IntegerField(default=1)
    state = models.CharField(max_length=20, default="active", choices=SUBSCRIPTION_STATES)
    quantity = models.IntegerField(default=1)
    unit_amount_in_cents = models.IntegerField(blank=True, null=True) # Not always in cents!
    activated_at = models.DateTimeField(blank=True, null=True)
    canceled_at = models.DateTimeField(blank=True, null=True)
    expires_at = models.DateTimeField(blank=True, null=True)
    current_period_started_at = models.DateTimeField(blank=True, null=True)
    current_period_ends_at = models.DateTimeField(blank=True, null=True)
    trial_started_at = models.DateTimeField(blank=True, null=True)
    trial_ends_at = models.DateTimeField(blank=True, null=True)

    super_subscription = models.BooleanField(default=False)

    objects = models.Manager()
    current = CurrentSubscriptionManager()

    class Meta:
        ordering = ["-id"]
        get_latest_by = "id"

    def is_current(self):
        """Is this subscription current (i.e. not expired and good to be used)

        Note that 'canceled' accounts are actually still 'current', as
        'canceled' just indicates they they will not renew after the
        current billing period (at which point Recurly will tell us that
        they are 'expired')
        """

        return bool(Subscription.current.filter(pk=self.pk).count())

    def is_trial(self):
        if self.super_subscription:
            return False

        if not self.trial_started_at or not self.trial_ends_at:
            return False # No trial dates, so not a trial

        now = datetime.now()
        if self.trial_started_at <= now and self.trial_ends_at > now:
            return True
        else:
            return False

    def change_plan(self, plan_code):
        """Change this subscription to the specified plan_code.

        This will call the Recurly API.
        """

        update_data = {
            "timeframe": "now",
            "plan_code": plan_code
        }

        recurly.accounts.subscription.update(account_code=self.account.account_code, data=update_data)
        self.plan_code = plan_code
        self.save()

    def terminate(self, refund="none"):
        """Terminate the subscription

        refund may be one of:
            - "none" : No refund, subscription is just expired
            - "partial" : Give a prorated refund
            - "full" : Provide a full refund of the most recent charge
        """

        recurly.accounts.subscription.delete(account_code=self.account.account_code, refund=refund)

    def cancel(self):
        """Cancel the subscription, it will expire at the end of the current billing cycle"""

        recurly.accounts.subscription.delete(account_code=self.account.account_code)


class Payment(models.Model):

    ACTION_CHOICES = (
        ("purchase", "Purchase"),
        ("credit", "Credit"),
    )

    STATUS_CHOICES = (
        ("success", "Success"),
        ("declined", "Declined"),
        ("void", "Void"),
    )

    account = models.ForeignKey(Account, blank=True, null=True)
    transaction_id = models.CharField(max_length=40)
    invoice_id = models.CharField(max_length=40, blank=True, null=True)
    action = models.CharField(max_length=10, choices=ACTION_CHOICES)
    date = models.DateTimeField(blank=True, null=True)
    amount_in_cents = models.IntegerField(blank=True, null=True) # Not always in cents!
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    message = models.CharField(max_length=250)

    class Meta:
        ordering = ["-id"]
        get_latest_by = "id"

    @classmethod
    def handle_notification(class_, **kwargs):
        recurly_transaction = recurly.Transaction().get(kwargs.get("transaction").id)
        recurly_account = recurly.Account().get(kwargs.get("account").account_code)

        payment = modelify(transaction, class_, remove_empty=True)

        payment.transaction_id = recurly_transaction.id
        payment.account = modelify(recurly_account, Account)

        print "Transaction Data:"
        print transaction_data

        payment, created = class_.objects.get_or_create(
            transaction_id=transaction_data["transaction_id"],
            defaults=transaction_data
        )

        return payment

# TODO: Make this smarter, not necessary
MODEL_MAP = {
    'user': User,
    'account': Account,
    'subscription': Subscription,
    'transaction': Payment,
}


def modelify(resource, model, remove_empty=False):
    fields = set(field.name for field in model._meta.fields)
    fields_by_name = dict((field.name, field) for field in model._meta.fields)
    fields.discard("id")

    data = resource
    try:
        data = resource.to_dict()
    except AttributeError:
        logger.debug("Nope, not a resource")
        pass

    for k, v in data.items():
        # Recursively replace known keys with actual models
        if k in MODEL_MAP:
            logger.debug("Modelifying a '%s'" % k)
            if callable(v):
                v = v()

            data[k] = modelify(v, MODEL_MAP[k], remove_empty=remove_empty)

    update = {}
    unique_fields = dict()
    for k, v in data.items():
        if k in fields:
            # Check for uniqueness so we can update existing objects
            if v and fields_by_name[k].unique:
                unique_fields[k] = v

            if k == "date" or k.endswith("_at"):
                print "%s: %s" % (k, v)
                #v = iso8601.parse_date(v) if v else None

            # Always assume fields with limited choices should be lower case
            if v and fields_by_name[k].choices:
                v = v.lower()

            if v or not remove_empty:
                update[str(k)] = v

    # Check for existing object
    try:
        obj = model.objects.get(**unique_fields)
        logger.debug("Updating %s" % obj)

        for k, v in update.items():
            setattr(obj, k, v)

        return obj
    except model.DoesNotExist:
        logger.debug("Returning new %s object" % model)
        return model(**update)
