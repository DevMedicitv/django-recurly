from django.db import models
from django.db.models import Q
from django.contrib.auth.models import User
from django_extensions.db.models import TimeStampedModel
from django.utils import timezone

from django_recurly import recurly

# Do these here to ensure the handlers get hooked up
from django_recurly import handlers
from django.db.models.signals import post_save

import logging
logger = logging.getLogger(__name__)


__all__ = ("Account", "Subscription", "User", "Payment")


class ActiveAccountManager(models.Manager):
    def get_query_set(self):
        return super(ActiveAccountManager, self).get_query_set().filter(state="active")


class CurrentSubscriptionManager(models.Manager):
    def get_query_set(self):
        return super(CurrentSubscriptionManager, self).get_query_set().filter(Q(state__in=("active", "canceled")))  # But not 'expired'


class SaveDirtyModel(models.Model):
    """ Only allows new and modified models to be saved. """

    SMART_SAVE_FORCE = False
    SMART_SAVE_IGNORE_FIELDS = ()

    class Meta:
        abstract = True

    def __init__(self, *args, **kwargs):
        super(SaveDirtyModel, self).__init__(*args, **kwargs)
        self._original_state = self._as_dict()
        self._previous_state = self._original_state

    def _iter_fields(self):
        for field in self._meta.fields: # m2m changes do not require a save
            if field.name in self.SMART_SAVE_IGNORE_FIELDS:
                continue
            field_name = '%s_id' % field.name if field.rel else field.name
            yield (field.name, getattr(self, field_name))

    def _as_dict(self):
        return dict(self._iter_fields())

    def is_dirty(self):
        if not self.pk:
            return True
        for field, value in self._iter_fields():
            if value != self._original_state[field]:
                return True
        return False

    def dirty_fields(self, names_only=False):
        diff = [] if names_only else {}
        for field, value in self._iter_fields():
            if value != self._original_state[field]:
                if names_only:
                    diff.append(field)
                else:
                    diff[field] = {
                        'new': value,
                        'old': self._original_state[field],
                    }
        return diff

    def save(self, *args, **kwargs):
        self._force_save = kwargs.pop('force', self.SMART_SAVE_FORCE)
        if self._force_save or self.is_dirty():
            super(SaveDirtyModel, self).save(*args, **kwargs)
            self._previous_state = self._original_state
            self._original_state = self._as_dict()


class Account(SaveDirtyModel, TimeStampedModel):
    ACCOUNT_STATES = (
        ("active", "Active"),         # Active and everything is fine
        ("closed", "Closed"),         # Account has been closed
    )

    user = models.ForeignKey(User, related_name="recurly_account", blank=True, null=True, on_delete=models.SET_NULL)
    account_code = models.CharField(max_length=32, unique=True)
    username = models.CharField(max_length=200)
    email = models.CharField(max_length=100)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    company_name = models.CharField(max_length=100, blank=True, null=True)
    state = models.CharField(max_length=20, default="active", choices=ACCOUNT_STATES)
    hosted_login_token = models.CharField(max_length=32, blank=True, null=True)
    created_at = models.DateTimeField(blank=True, null=True)

    objects = models.Manager()
    active = ActiveAccountManager()

    class Meta:
        ordering = ["-id"]
        get_latest_by = "id"

    def save(self, *args, **kwargs):
        if self.user is None:
            try:
                # Associate the account with a user
                self.user = User.objects.get(username=self.username)
            except User.DoesNotExist:
                # It's possible that a user may not exist locally (closed account)
                logger.debug("Could not find user for Recurly account (account_code: '%s') having username '%s'", self.account_code, self.username)
                pass

        super(Account, self).save(*args, **kwargs)

    def is_active(self):
        return self.state == 'active'

    def get_subscriptions(self, plan_code=None):
        """Get current (i.e. not 'expired') subscriptions for this Account. If
        no `plan_code` is specified then all current subscriptions are returned.

        NOTE: An account may have multiple subscriptions of the same `plan_code`.
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

        An exception will be raised if the account has more than one non-expired
        subscription of the specified type.
        """
        if plan_code is not None:
            return Subscription.current.get(account=self, plan_code=plan_code)
        else:
            return Subscription.current.get(account=self)

    def get_account(self):
        # TODO: Cache/store account object
        return recurly.Account.get(self.account_code)

    def get_billing_info(self):
        try:
            return self.get_account().billing_info
        except AttributeError:
            return None

    def get_invoices(self):
        return self.get_account().invoices

    def get_transactions(self):
        try:
            return self.get_account().transactions
        except AttributeError:
            return None

    def close(self):
        return self.get_account().delete()

    def reopen(self):
        return self.get_account().reopen()

    @classmethod
    def get_active(class_, user):
        return class_.active.filter(user=user).latest()

    @classmethod
    def sync(class_, recurly_account=None, account_code=None):
        if recurly_account is None:
            recurly_account = recurly.Account.get(account_code)

        account = modelify(recurly_account, class_)

        account.save()
        return account

    @classmethod
    def handle_notification(class_, **kwargs):
        """Update/create an account and its associated subscription using data
        from Recurly"""

        # First get the up-to-date account details directly from Recurly and
        # sync local record (update existing, or create new)
        account = class_.sync(account_code=kwargs.get("account").account_code)

        # Now do the same with the subscription (if there is one)
        if not kwargs.get("subscription"):
            subscription = None
        else:
            recurly_subscription = recurly.Subscription.get(kwargs.get("subscription").uuid)
            subscription = modelify(recurly_subscription, Subscription)
            subscription.xml = kwargs.get('xml')

            subscription.save()

        return account, subscription


class Subscription(SaveDirtyModel):
    SUBSCRIPTION_STATES = (
        ("active", "Active"),         # Active and everything is fine
        ("canceled", "Canceled"),     # Still active, but will not be renewed
        ("expired", "Expired"),       # Did not renew, or was forcibly expired
    )

    account = models.ForeignKey(Account, blank=True, null=True)
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
        except Exception as e:
            logger.debug("Failed to get pending changes: %s", e)
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
        if not len(kwargs):
            logger.debug("Nothing to change for subscription %d", self.pk)
            return

        recurly_subscription = recurly.Subscription.get(self.uuid)

        for k, v in kwargs.iteritems():
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
    def get_plans(class_):
        return [plan.name for plan in recurly.Plan.all()]

    @classmethod
    def sync(class_, recurly_subscription=None, uuid=None):
        if recurly_subscription is None:
            recurly_subscription = recurly.Subscription.get(uuid)

        subscription = modelify(recurly_subscription, Subscription)

        # TODO: >>> Hacky
        if subscription.account.is_dirty():
            subscription.account.save()
            subscription.account_id = subscription.account.pk

        subscription.save()
        return subscription


class Payment(SaveDirtyModel):
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
    transaction_id = models.CharField(max_length=40, unique=True)
    invoice_id = models.CharField(max_length=40, blank=True, null=True)
    action = models.CharField(max_length=10, choices=ACTION_CHOICES)
    amount_in_cents = models.IntegerField(blank=True, null=True) # Not always in cents!
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    message = models.CharField(max_length=250)
    created_at = models.DateTimeField(blank=True, null=True)
    xml = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ["-id"]
        get_latest_by = "id"

    def get_transaction(self):
        return recurly.Transaction.get(self.transaction_id)

    def get_invoice(self):
        return recurly.Invoice.get(self.invoice_id)

    @classmethod
    def sync(class_, recurly_transaction=None, uuid=None):
        if recurly_transaction is None:
            recurly_transaction = recurly.Transaction.get(uuid)

        payment = modelify(recurly_transaction, class_, remove_empty=True)

        if payment.invoice_id is None:
            payment.invoice_id = recurly_transaction.invoice().uuid

        # TODO: >>> Hacky
        # `modelify()` doesn't assume you want to save every generated model
        # object, including foreign relationships. So if the account has not
        # been created before saving the payment, the payment row will have a
        # null value for `account_id` (and the account will not be saved). Also,
        # simply saving `payment.account` first isn't enough because Django
        # doesn't automatically set `payment.account_id` to the generated pk,
        # even though `payment.account.pk` *does* get set.
        if payment.account.is_dirty():
            payment.account.save()
            payment.account_id = payment.account.pk

        payment.save()
        return payment

    @classmethod
    def handle_notification(class_, **kwargs):
        recurly_transaction = recurly.Transaction.get(kwargs.get("transaction").id)
        # account_code = kwargs.get("account").account_code

        payment = modelify(recurly_transaction, class_, remove_empty=True)
        payment.invoice_id = recurly_transaction.invoice().uuid
        payment.xml = kwargs.get('xml')

        if payment.account.is_dirty():
            payment.account.save()
            payment.account_id = payment.account.pk

        payment.save()

        return payment


# Connect model signal handlers

post_save.connect(handlers.account_post_save, sender=Account, dispatch_uid="account_post_save")
post_save.connect(handlers.subscription_post_save, sender=Subscription, dispatch_uid="subscription_post_save")
post_save.connect(handlers.payment_post_save, sender=Payment, dispatch_uid="payment_post_save")


### Helpers ###

def modelify(resource, model, remove_empty=False, context={}):
    '''Modelify handles the dirty work of converting Recurly Resource objects to
    Django model instances, including resolving any additional Resource objects
    required to satisfy foreign key relationships. This method will query for
    existing instances based on unique model fields, or return a new instance if
    there is no match. Modelify does not save any models back to the database,
    it is left up to the application logic to decide when to do that.'''

    # TODO: Make this smarter, not necessary.
    MODEL_MAP = {
        'user': User,
        'account': Account,
        'subscription': Subscription,
        'transaction': Payment,
    }

    fields = set(field.name for field in model._meta.fields)
    fields_by_name = dict((field.name, field) for field in model._meta.fields)
    fields.discard("id")

    logger.debug("Modelify: %s", resource.nodename)

    data = resource
    try:
        data = resource.to_dict()
    except AttributeError:
        logger.debug("Nope, not a resource: %s (expected %s)", resource, model)
        pass

    for k, v in data.items():
        # Expand 'uuid' to work with payment notifications and transaction API queries
        if k == 'uuid' and hasattr(resource, 'nodename') and not hasattr(data, resource.nodename + '_id'):
            data[resource.nodename + '_id'] = v

        # Recursively replace links to known keys with actual models
        # TODO: >>> Check that all expected foreign keys are mapped
        if k in MODEL_MAP and k in fields:
            logger.debug("Modelifying nested: %s", k)

            if isinstance(v, basestring):
                try:
                    v = resource.link(k)
                except AttributeError:
                    pass

            if callable(v):
                v = v()

            data[k] = modelify(v, MODEL_MAP[k], remove_empty=remove_empty)

    update = {}
    unique_fields = {}

    for k, v in data.items():
        if k in fields:
            # Check for uniqueness so we can update existing objects if they
            # exist
            if v and fields_by_name[k].unique:
                unique_fields[k] = v

            if k == "date" or k.endswith("_at"):
                # TODO: >>> Make sure dates are always in UTC and are tz-aware
                pass

            # Fields with limited choices should always be lower case
            if v and fields_by_name[k].choices:
                v = v.lower()

            if v or not remove_empty:
                update[str(k)] = v

    # Check for existing model object
    if unique_fields:
        try:
            obj = model.objects.get(**unique_fields)
            logger.debug("Updating %s", obj)

            # Update fields
            for k, v in update.items():
                setattr(obj, k, v)

            return obj
        except model.DoesNotExist:
            logger.debug("No row found matching unique fields '%s'", unique_fields)
            pass

    # This is a new instance
    # TODO: >>> Auto-save models?
    logger.debug("Returning new %s object", model)
    return model(**update)
