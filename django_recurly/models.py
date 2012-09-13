from django.db import models
from django.db.models import Q
from django.contrib.auth.models import User
from django_extensions.db.models import TimeStampedModel
from django.utils import timezone

from django_recurly import recurly, signals
from django_recurly.utils import dump

# Do these here to ensure the handlers get hooked up
import django_recurly.handlers

import logging
logger = logging.getLogger(__name__)

ACCOUNT_STATES = (
    ("active", "Active"),         # Active and everything is fine
    ("closed", "Closed"),         # Account has been closed
)

SUBSCRIPTION_STATES = (
    ("active", "Active"),         # Active and everything is fine
    ("canceled", "Canceled"),     # Still active, but will not be renewed
    ("expired", "Expired"),       # Did not renew, or was forcibly expired
)

__all__ = ("Account", "Subscription", "User", "Payment")


class ActiveAccountManager(models.Manager):
    def get_query_set(self):
        return super(ActiveAccountManager, self).get_query_set().filter(state="active")


class CurrentSubscriptionManager(models.Manager):
    def get_query_set(self):
        return super(CurrentSubscriptionManager, self).get_query_set().filter(Q(state__in=("active", "canceled")))  # But not 'expired'


class Account(TimeStampedModel):
    account_code = models.CharField(max_length=32, unique=True)
    user = models.ForeignKey(User, related_name="recurly_account", blank=True, null=True, on_delete=models.SET_NULL)
    email = models.CharField(max_length=100)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    company_name = models.CharField(max_length=100, blank=True, null=True)
    state = models.CharField(max_length=20, default="active", choices=ACCOUNT_STATES)
    hosted_login_token = models.CharField(max_length=32, blank=True, null=True)

    objects = models.Manager()
    active = ActiveAccountManager()

    class Meta:
        ordering = ["-id"]
        get_latest_by = "id"

    def get_all_subscriptions(self):
        """Get all subscriptions for this Account, including active and expired.
        """
        return self.subscription_set.all()

    def get_subscriptions(self, plan_code=None):
        """Get all current subscriptions for this Account

        An account may have multiple subscriptions of the same `plan_code`.
        """
        try:
            if plan_code is not None:
                return Subscription.current.filter(account=self, plan_code=plan_code)
            else:
                return Subscription.current.filter(account=self)
        except Subscription.DoesNotExist:
            return None

    def get_subscription(self, plan_code=None):
        """Get current subscription of type `plan_code` for this Account.

        An exception will be raised if the account has more than one
        subscription of this type.
        """
        if plan_code is not None:
            return Subscription.current.get(account=self, plan_code=plan_code)
        else:
            return Subscription.current.get(account=self)

    def is_active(self):
        return self.state == 'active'

    def get_account(self):
        # TODO: Cache/store account object
        return recurly.Account.get(self.account_code)

    def get_invoices(self):
        return self.get_recurly_account().invoices

    def get_transactions(self):
        return self.get_recurly_account().transactions

    @classmethod
    def get_active(class_, user):
        return class_.active.filter(user=user).latest()

    @classmethod
    def handle_notification(class_, **kwargs):
        """Update/create an account and its associated subscription using data from Recurly"""

        # First get the up-to-date account details directly from Recurly and
        # convert it to a model instance, which will load an existing account
        # for update (if one exists)
        recurly_account = recurly.Account.get(kwargs.get("account").account_code)
        account = modelify(recurly_account, class_)

        try:
            # Associate the account with the user who created it
            account.user = User.objects.get(username=recurly_account.username)
        except User.DoesNotExist:
            # It's possible that a user may not exist locally (closed account)
            account.user = None

        was_active = bool(class_.active.filter(pk=account.pk).count())
        now_active = account.is_active()

        account.save()

        # Now do the same with the subscription (if there is one)
        if not kwargs.get("subscription"):
            subscription = None
        else:
            recurly_subscription = recurly.Subscription.get(kwargs.get("subscription").uuid)
            subscription = modelify(recurly_subscription, Subscription)
            subscription.xml = kwargs.get('xml')

            if subscription.pk is None:
                was_current = False
            else:
                was_current = bool(Subscription.current.filter(pk=subscription.pk).count())
            now_current = subscription.state != 'expired'

            subscription.save()

            signals.subscription_updated.send(sender=account, account=account, subscription=subscription)

            # Send account closed/opened signals
            if was_current and not now_current:
                signals.subscription_expired.send(sender=account, account=account, subscription=subscription)
            elif not was_current and now_current:
                signals.subscription_current.send(sender=account, account=account, subscription=subscription)

        signals.account_updated.send(sender=account, account=account, subscription=subscription)

        # Send account closed/opened signals
        if was_active and not now_active:
            signals.account_closed.send(sender=account, account=account, subscription=subscription)
        elif not was_active and now_active:
            signals.account_opened.send(sender=account, account=account, subscription=subscription)

        return account, subscription


class Subscription(models.Model):
    account = models.ForeignKey(Account)
    uuid = models.CharField(max_length=40, unique=True)
    plan_code = models.CharField(max_length=100)
    plan_version = models.IntegerField(default=1)
    state = models.CharField(max_length=20, default="active", choices=SUBSCRIPTION_STATES)
    quantity = models.IntegerField(default=1)
    unit_amount_in_cents = models.IntegerField(blank=True, null=True) # Not always in cents!
    currency = models.CharField(max_length=3, default="USD")
    activated_at = models.DateTimeField(blank=True, null=True)
    canceled_at = models.DateTimeField(blank=True, null=True)
    expires_at = models.DateTimeField(blank=True, null=True)
    current_period_started_at = models.DateTimeField(blank=True, null=True)
    current_period_ends_at = models.DateTimeField(blank=True, null=True)
    trial_started_at = models.DateTimeField(blank=True, null=True)
    trial_ends_at = models.DateTimeField(blank=True, null=True)
    xml = models.TextField(blank=True, null=True)

    objects = models.Manager()
    current = CurrentSubscriptionManager()

    class Meta:
        ordering = ["-id"]
        get_latest_by = "id"

    def is_current(self):
        """Is this subscription current (i.e. not 'expired')

        Note that 'canceled' subscriptions are actually still considered
        current, as 'canceled' just indicates they they will not renew after
        the current billing period (at which point Recurly will tell us that
        they are 'expired')
        """
        return self.state != 'expired'

    def is_trial(self):
        if not self.trial_started_at or not self.trial_ends_at:
            return False # No trial dates, so not a trial

        now = timezone.now()
        if self.trial_started_at <= now and self.trial_ends_at > now:
            return True
        else:
            return False

    def get_pending_changes(self):
        try:
            return recurly.objects_for_push_notification(self.xml).subscription.pending_subscription
        except Exception:
            logger.debug("Failed to get pending changes")
            logger.debug(dump(recurly.objects_for_push_notification(self.xml)))
            return None

    def get_plan(self):
        return recurly.Plan.get(self.plan_code)

    def change_plan(self, plan_code, timeframe='now'):
        """Change this subscription to the specified plan_code.

        This will call the Recurly API and update the subscription.
        """
        self.change(timeframe, plan_code=plan_code)

    def change_quantity(self, quantity, incremental=False, timeframe='now'):
        """Change this subscription quantity. The quantity will be changed to
        `quantity` if `incremental` is `False`, and increment the quantity by
        `quantity` if `incremental` is `True`.

        This will call the Recurly API and update the subscription.
        """

        new_quantity = quantity if not incremental else (self.quantity + quantity)

        self.change(timeframe, quantity=new_quantity)

    def change(self, timeframe='now', **kwargs):
        """Change this subscription to the values supplied in the arguments

        `timeframe` may be one of:
            - 'now' : A prorated charge or credit is calculated and the
                      subscription is updated immediately.
            - 'renewal': Invoicing is delayed until next billing cycle. Use
                         the pending updates to provision

        `plan_code`
        `quantity`
        `unit_amount_in_cents`

        This will call the Recurly API and update the subscription.
        """
        recurly_subscription = recurly.Subscription.get(self.uuid)

        for k, v in kwargs:
            setattr(recurly_subscription, k, v)
        recurly_subscription.timeframe = timeframe

        recurly_subscription.save()

    def cancel(self):
        """Cancel the subscription, it will expire at the end of the current billing cycle"""
        recurly_subscription = recurly.Subscription.get(self.uuid)
        recurly_subscription.cancel()

    def reactivate(self):
        """Reactivate the cancelled subscription so it renews at the end of the current billing cycle"""
        recurly_subscription = recurly.Subscription.get(self.uuid)
        recurly_subscription.reactivate()

    def terminate(self, refund="none"):
        """Terminate the subscription

        `refund` may be one of:
            - "none" : No refund, subscription is just expired
            - "partial" : Give a prorated refund
            - "full" : Provide a full refund of the most recent charge
        """
        recurly_subscription = recurly.Subscription.get(self.uuid)
        recurly_subscription.terminate(refund=refund)

    @classmethod
    def get_plans():
        return [plan.name for plan in recurly.Plan.all()]

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
    created_at = models.DateTimeField(blank=True, null=True)
    amount_in_cents = models.IntegerField(blank=True, null=True) # Not always in cents!
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    message = models.CharField(max_length=250)
    xml = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ["-id"]
        get_latest_by = "id"

    def get_transaction(self):
        return recurly.Transaction.get(self.transaction_id)

    def get_invoice(self):
        return recurly.Invoice.get(self.invoice_id)

    @classmethod
    def handle_notification(class_, **kwargs):
        recurly_transaction = recurly.Transaction().get(kwargs.get("transaction").id)
        recurly_account = recurly.Account().get(kwargs.get("account").account_code)

        payment = modelify(recurly_transaction, class_, remove_empty=True)
        new_payment = bool(payment.pk is None)

        payment.transaction_id = recurly_transaction.uuid
        payment.invoice_id = recurly_transaction.invoice().uuid
        payment.account = modelify(recurly_account, Account)
        payment.xml = kwargs.get('xml')

        payment.save()

        if new_payment:
            signals.payment_created.send(sender=payment, payment=payment, account=payment.account)
        else:
            signals.payment_updated.send(sender=payment, payment=payment, account=payment.account)

        return payment


# TODO: Make this smarter, not necessary
MODEL_MAP = {
    'user': User,
    'account': Account,
    'subscription': Subscription,
    'transaction': Payment,
}

def modelify(resource, model, remove_empty=False, context={}):
    fields = set(field.name for field in model._meta.fields)
    fields_by_name = dict((field.name, field) for field in model._meta.fields)
    fields.discard("id")

    logger.debug("Modelify: %s" % resource)

    data = resource
    try:
        data = resource.to_dict()
    except AttributeError:
        logger.debug("Nope, not a resource")
        pass

    for k, v in data.items():
        # Recursively replace known keys with actual models
        if k in MODEL_MAP:
            logger.debug("Modelifying a nested '%s'" % k)

            if isinstance(v, basestring):
                try:
                    v = resource.link(k)
                except AttributeError:
                    pass

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
                pass
                # TODO: Make sure dates are always in UTC and are aware
                #print "%s: %s" % (k, v)
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
