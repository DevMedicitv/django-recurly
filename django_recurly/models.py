from django.conf import settings
from django.db import models
from django.db.models import Q
from django.contrib.auth.models import User
from django_extensions.db.models import TimeStampedModel
from django.utils import timezone
from django.core.validators import validate_email
from django.core.exceptions import ValidationError

from django_recurly import conf
from django_recurly.utils import recurly
# Do these here to ensure the handlers get hooked up
from django_recurly import handlers
from django.db.models.signals import post_save
import importlib

import logging
logger = logging.getLogger(__name__)

__all__ = ("Account", "Subscription", "User", "Payment", "Token")


# Configurable function used to match a new Recurly account with a Django
# User model. Custom functions may accept 'account_code' and 'account' as
# kwargs. It can be overridden in the Django settings file by setting
# 'RECURLY_ACCOUNT_CODE_TO_USER'.
def account_code_to_user(account_code, account):
    return User.objects.get(pk=account_code)

RECURLY_ACCOUNT_CODE_TO_USER = account_code_to_user
if conf.RECURLY_ACCOUNT_CODE_TO_USER:
    import_parts = conf.RECURLY_ACCOUNT_CODE_TO_USER.rsplit('.', 1)
    mod = importlib.import_module(import_parts[0])
    try:
        RECURLY_ACCOUNT_CODE_TO_USER = getattr(mod, import_parts[1])
    except Exception as e:
        logger.warning("User function failed to load: %s", e)
        pass


class ActiveAccountManager(models.Manager):
    def get_query_set(self):
        return super(ActiveAccountManager, self).get_query_set().filter(state="active")


class CurrentSubscriptionManager(models.Manager):
    def get_query_set(self):
        return super(CurrentSubscriptionManager, self).get_query_set().filter(Q(state__in=("active", "canceled")))  # i.e. not 'expired'


class SaveDirtyModel(models.Model):
    """Save only when new or modified."""

    SMART_SAVE_FORCE = False
    SMART_SAVE_IGNORE_FIELDS = ()

    class Meta:
        abstract = True

    def __init__(self, *args, **kwargs):
        super(SaveDirtyModel, self).__init__(*args, **kwargs)
        self._original_state = self._as_dict()
        self._previous_state = self._original_state

    def _iter_fields(self):
        for field in self._meta.fields:  # m2m changes do not require a save
            if field.name in self.SMART_SAVE_IGNORE_FIELDS:
                continue
            field_name = ('%s_id' % field.name) if field.rel else field.name
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
        else:
            logger.debug("Skipping save for %s (pk: %s) because it hasn't changed.", self.__class__.__name__, self.pk or "None")

    class Meta:
        abstract = True


class Account(SaveDirtyModel, TimeStampedModel):
    ACCOUNT_STATES = (
        ("active", "Active"),         # Active account (but may not have billing info)
        ("closed", "Closed"),         # Account has been closed
    )

    user = models.ForeignKey(User, related_name="recurly_account", blank=True, null=True, on_delete=models.SET_NULL)

    account_code = models.CharField(max_length=50, unique=True, null=False)
    username = models.CharField(max_length=50, blank=True, null=True)
    email = models.CharField(max_length=100, blank=True, null=True)
    first_name = models.CharField(max_length=50, blank=True, null=True)
    last_name = models.CharField(max_length=50, blank=True, null=True)
    company_name = models.CharField(max_length=50, blank=True, null=True)
    accept_language = models.CharField(max_length=2, blank=True, null=True)

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
                # Associate the account with a user-defined lookup
                self.user = RECURLY_ACCOUNT_CODE_TO_USER(
                    account_code=self.account_code, account=self)
            except Exception as e:
                # Fallback to email address (the Recurly default)
                logger.warning("User lookup failed for account_code '%s'." \
                    "Falling back to User.email: %s", self.account_code, e)
                try:
                    validate_email(self.account_code)
                    self.user = User.objects.get(email=self.account_code)
                    return True
                except (ValidationError, User.DoesNotExist):
                    pass

        if self.user is None:
            # It's possible that a user does not exist locally (e.g. user closed
            # account in app, but account still exists in Recurly)
            logger.debug("Could not find user for Recurly account " \
                "(account_code: '%s') having username '%s'", \
                self.account_code, self.username)

        # Update Recurly account
        if kwargs.pop('remote', True):
            recurly_account = self.get_account()
            for attr, value in self.dirty_fields().iteritems():
                setattr(recurly_account, attr, value['new'])
            recurly_account.save()

        super(Account, self).save(*args, **kwargs)

    def is_active(self):
        return self.state == 'active'

    def has_billing_info(self):
        return hasattr(self, 'billing_info')

    def has_subscription(self, plan_code=None):
        if plan_code is not None:
            return Subscription.current.filter(account=self, plan_code=plan_code).count() > 0
        else:
            return Subscription.current.filter(account=self).count() > 0

    def get_subscriptions(self, plan_code=None):
        """Get current (i.e. not 'expired') subscriptions for this Account. If
        no `plan_code` is specified then all current subscriptions are returned.

        NOTE: An account may have multiple subscriptions of the same `plan_code`.
        """
        if plan_code is not None:
            return Subscription.current.filter(account=self, plan_code=plan_code)
        else:
            return Subscription.current.filter(account=self)

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
        # TODO: (IW) Cache/store account object
        return recurly.Account.get(self.account_code)

    def get_billing_info(self):
        raise DeprecationWarning("Use Account.billing_info instead.")

        try:
            return self.billing_info
        except AttributeError:
            return None

    def get_invoices(self):
        return self.get_account().invoices

    def get_transactions(self):
        try:
            return self.get_account().transactions
        except AttributeError:
            return None

    def update_billing_info(self, billing_info):
        if isinstance(billing_info, dict):
            billing_info = recurly.BillingInfo(**billing_info)
        recurly_account = self.get_account()
        recurly_account.update_billing_info(billing_info)

        self.sync(recurly_account)

    def close(self):
        recurly_account = self.get_account().delete()

        self.sync(recurly_account)

    def reopen(self):
        recurly_account = self.get_account()
        recurly_account.reopen()

        self.sync(recurly_account)

    def subscribe(self, **kwargs):
        recurly_subscription = recurly.Subscription(**kwargs)
        self.get_account().subscribe(recurly_subscription)

        Subscription.sync_subscription(recurly_subscription=recurly_subscription)

    def sync(self, recurly_account):
        try:
            data = recurly_account.to_dict()
        except AttributeError:
            logger.debug("Can't sync Account %s, arg is not a Recurly Resource: %s", self.pk, recurly_account)
            raise

        fields_by_name = dict((field.name, field) for field in self._meta.fields)

        # Update fields
        for k, v in data.items():
            if not v or not hasattr(self, k):
                continue

            if k == 'billing_info':
                continue

            if v and fields_by_name[k].choices:
                v = v.lower()

            setattr(self, k, v)

        self.save(remote=False)

    @classmethod
    def get_active(class_, user):
        return class_.active.filter(user=user).latest()

    @classmethod
    def sync_account(class_, recurly_account=None, account_code=None):
        if recurly_account is None:
            recurly_account = recurly.Account.get(account_code)

        account = modelify(recurly_account, class_)

        if hasattr(account, 'billing_info') and account.billing_info.is_dirty():
            account.billing_info.save(remote=False)

        account.save(remote=False)
        return account

    @classmethod
    def create(class_, **kwargs):
        # Make sure billing_info is a Recurly BillingInfo resource
        billing_info = kwargs.pop('billing_info', {})
        if len(billing_info) and isinstance(billing_info, dict):
            kwargs['billing_info'] = recurly.BillingInfo(**billing_info)
        recurly_account = recurly.Account(**kwargs)
        recurly_account.save()

        return class_.sync_account(recurly_account=recurly_account)

    @classmethod
    def handle_notification(class_, **kwargs):
        """Update/create an account and its associated subscription using data
        from Recurly"""

        # First get the up-to-date account details directly from Recurly and
        # sync local record (update existing, or create new)
        account = class_.sync_account(account_code=kwargs.get("account").account_code)

        # Now do the same with the subscription (if there is one)
        if not kwargs.get("subscription"):
            subscription = None
        else:
            recurly_subscription = recurly.Subscription.get(kwargs.get("subscription").uuid)
            subscription = modelify(recurly_subscription, Subscription, context={'account': account})
            subscription.xml = recurly_subscription.as_log_output(full=True)

            subscription.save(remote=False)

        return account, subscription


class BillingInfo(SaveDirtyModel):
    BILLING_TYPES = (
        ("credit_card", "Credit Card"),
        ("paypal", "PayPal"),
    )

    account = models.OneToOneField(Account, related_name='billing_info')

    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)

    type = models.CharField(max_length=50, blank=True, null=True, choices=BILLING_TYPES)

    company_name = models.CharField(max_length=50, blank=True, null=True)
    address1 = models.CharField(max_length=200, blank=True, null=True)
    address2 = models.CharField(max_length=200, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    state = models.CharField(max_length=50, blank=True, null=True)
    zip = models.CharField(max_length=50, blank=True, null=True)
    country = models.CharField(max_length=2, null=True, blank=True)
    phone = models.CharField(max_length=50, blank=True, null=True)

    vat_number = models.CharField(max_length=16, blank=True, null=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    ip_address_country = models.CharField(max_length=2, null=True, blank=True)

    card_type = models.CharField(max_length=50, blank=True, null=True)
    month = models.IntegerField(max_length=2, blank=True, null=True)
    year = models.IntegerField(max_length=4, blank=True, null=True)
    first_six = models.IntegerField(max_length=6, blank=True, null=True)
    last_four = models.IntegerField(max_length=4, blank=True, null=True)
    start_month = models.IntegerField(max_length=2, blank=True, null=True)
    start_year = models.IntegerField(max_length=4, blank=True, null=True)
    issue_number = models.IntegerField(max_length=4, blank=True, null=True)

    # PayPal
    billing_agreement_id = models.CharField(max_length=100, blank=True, null=True)

    def save(self, *args, **kwargs):
        # Update Recurly billing info
        if kwargs.pop('remote', True):
            recurly_account = self.account.get_account()
            billing_infp = recurly_account.get_billing_info()
            for attr, value in self.dirty_fields().iteritems():
                setattr(recurly_billing_info, attr, value['new'])
            account.update_billing_info(billing_info)

        super(BillingInfo, self).save(*args, **kwargs)

    def sync(self, recurly_billing_info):
        try:
            data = recurly_billing_info.to_dict()
        except AttributeError:
            logger.debug("Can't sync BillingInfo %s, arg is not a Recurly Resource: %s", self.pk, recurly_billing_info)
            raise

        fields_by_name = dict((field.name, field) for field in self._meta.fields)

        # Update fields
        for k, v in data.items():
            if not v or not hasattr(self, k):
                continue

            if v and fields_by_name[k].choices:
                v = v.lower()

            setattr(self, k, v)

        self.save(remote=False)

    @classmethod
    def sync_billing_info(class_, recurly_billing_info=None, account_code=None):
        if recurly_billing_info is None:
            recurly_billing_info = recurly.Account.get(account_code).get_billing_info()

        billing_info = modelify(recurly_billing_info, class_)

        if billing_info.account.is_dirty():
            billing_info.account.save(remote=False)
            billing_info.account_id = billing_info.account.pk

        billing_info.save(remote=False)
        return billing_info


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
    unit_amount_in_cents = models.IntegerField(blank=True, null=True)  # Not always in cents (i8n)!
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

    def save(self, *args, **kwargs):
        # Update Recurly subscription
        if kwargs.pop('remote', True):
            recurly_subscription = self.get_subscription()
            for attr, value in self.dirty_fields().iteritems():
                setattr(recurly_subscription, attr, value['new'])
            recurly_subscription.save()

        super(Subscription, self).save(*args, **kwargs)

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
            return False  # No trial dates, so not a trial

        now = timezone.now()
        if self.trial_started_at <= now and self.trial_ends_at > now:
            return True
        else:
            return False

    def get_subscription(self):
        # TODO: (IW) Cache/store subscription object
        return recurly.Subscription.get(self.uuid)

    def get_pending_changes(self):
        if self.xml is None:
            return None

        try:
            return recurly.Subscription().from_element(self.xml).pending_subscription
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

        recurly_subscription = self.get_subscription()

        for k, v in kwargs.iteritems():
            setattr(recurly_subscription, k, v)
        recurly_subscription.timeframe = timeframe
        recurly_subscription.save()

        self.sync(recurly_subscription)

    def cancel(self):
        """Cancel the subscription, it will expire at the end of the current
        billing cycle"""
        recurly_subscription = self.get_subscription()
        recurly_subscription.cancel()

        self.sync(recurly_subscription)

    def reactivate(self):
        """Reactivate the canceled subscription so it renews at the end of the
        current billing cycle"""
        recurly_subscription = self.get_subscription()
        recurly_subscription.reactivate()

        self.sync(recurly_subscription)

    def terminate(self, refund="none"):
        """Terminate the subscription

        `refund` may be one of:
            - "none" : No refund, subscription is just expired
            - "partial" : Give a prorated refund
            - "full" : Provide a full refund of the most recent charge
        """
        recurly_subscription = self.get_subscription()
        recurly_subscription.terminate(refund=refund)

        self.sync(recurly_subscription)

    def sync(self, recurly_subscription):
        try:
            data = recurly_subscription.to_dict()
        except AttributeError:
            logger.debug("Can't sync Subscription %s, arg is not a Recurly Resource: %s", self.pk, recurly_subscription)
            raise

        fields_by_name = dict((field.name, field) for field in self._meta.fields)

        # Update fields
        for k, v in data.items():
            if not v or not hasattr(self, k):
                continue

            # Skip relationships
            # TODO: (IW) Remove this once 'account' is taken out of the
            # recurly-client-python 'attributes' list.
            if k == 'account':
                continue

            if v and fields_by_name[k].choices:
                v = v.lower()

            setattr(self, k, v)

        self.xml = recurly_subscription.as_log_output(full=True)
        self.save(remote=False)

    @classmethod
    def get_plans(class_):
        return [plan.name for plan in recurly.Plan.all()]

    @classmethod
    def sync_subscription(class_, recurly_subscription=None, uuid=None):
        if recurly_subscription is None:
            recurly_subscription = recurly.Subscription.get(uuid)

        subscription = modelify(recurly_subscription, Subscription)
        subscription.xml = recurly_subscription.as_log_output(full=True)

        # TAKE NOTE:
        # `modelify()` doesn't assume you want to save every generated model
        # object, including foreign relationships. So if this is a subscription
        # for a new account, and you save the subscription before creating the
        # account, the subscription will have a null value for `account_id`
        # (as the account will not have been created yet). Also, simply saving
        # `payment.account` first isn't enough because Django doesn't
        # automatically set `payment.account_id` with the newly generated
        # account pk (note, though, that `payment.account.pk` *will* be set
        # after calling `payment.account.save()`).
        if subscription.account.is_dirty():
            subscription.account.save(remote=False)
            subscription.account_id = subscription.account.pk

        subscription.save(remote=False)
        return subscription

    @classmethod
    def create(class_, **kwargs):
        recurly_subscription = recurly.Subscription(**kwargs)
        recurly_subscription.save()

        return class_.sync_subscription(recurly_subscription=recurly_subscription)


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
    amount_in_cents = models.IntegerField(blank=True, null=True)  # Not always in 'cents' (i8n)!
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
    def sync_payment(class_, recurly_transaction=None, uuid=None):
        if recurly_transaction is None:
            recurly_transaction = recurly.Transaction.get(uuid)

        payment = modelify(recurly_transaction, class_, remove_empty=True)
        payment.xml = recurly_transaction.as_log_output(full=True)

        if payment.invoice_id is None:
            payment.invoice_id = recurly_transaction.invoice().uuid

        # TODO: (IW) Hacky
        if payment.account.is_dirty():
            payment.account.save(remote=False)
            payment.account_id = payment.account.pk

        payment.save(remote=False)
        return payment

    @classmethod
    def handle_notification(class_, **kwargs):
        recurly_transaction = recurly.Transaction.get(kwargs.get("transaction").id)
        # account_code = kwargs.get("account").account_code

        payment = modelify(recurly_transaction, class_, remove_empty=True)
        payment.invoice_id = recurly_transaction.invoice().uuid
        # payment.xml = kwargs.get('xml')
        payment.xml = recurly_transaction.as_log_output(full=True)

        if payment.account.is_dirty():
            payment.account.save(remote=False)
            payment.account_id = payment.account.pk

        payment.save()
        return payment


class Token(TimeStampedModel):
    """Tokens are returned from successful Recurly.js submissions as a way to
    look up transaction details. This is an alternative to waiting for Recurly
    push notifications."""

    TYPE_CHOICES = (
        ('subscription', 'Subscription'),
        ('billing_info', 'Billing Info'),
        ('invoice', 'Invoice'),
    )

    account = models.ForeignKey(Account, blank=True, null=True, related_name="tokens")
    token = models.CharField(max_length=40, unique=True)
    cls = models.CharField(max_length=12, choices=TYPE_CHOICES)
    identifier = models.CharField(max_length=40)
    xml = models.TextField(blank=True, null=True)


# Connect model signal handlers

post_save.connect(handlers.account_post_save, sender=Account, dispatch_uid="account_post_save")
post_save.connect(handlers.billing_info_post_save, sender=BillingInfo, dispatch_uid="billing_info_post_save")
post_save.connect(handlers.subscription_post_save, sender=Subscription, dispatch_uid="subscription_post_save")
post_save.connect(handlers.payment_post_save, sender=Payment, dispatch_uid="payment_post_save")
post_save.connect(handlers.token_post_save, sender=Token, dispatch_uid="token_post_save")


### Helpers ###

# TODO: (IW) Add a method on a model base class so this can be used to refresh
# instances
def modelify(resource, model, remove_empty=False, context={}):
    '''Modelify handles the dirty work of converting Recurly Resource objects to
    Django model instances, including resolving any additional Resource objects
    required to satisfy foreign key relationships. This method will query for
    existing instances based on unique model fields, or return a new instance if
    there is no match. Modelify does not save any models back to the database,
    it is left up to the application logic to decide when to do that.'''

    # TODO: (IW) Make this smarter, not necessary.
    MODEL_MAP = {
        'user': User,
        'account': Account,
        'billing_info': BillingInfo,
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

    if not isinstance(data, dict):
        raise TypeError("Cannot modelify non-dict '%s' (%s)" % (data, data.__class__.__name__))

    for k, v in data.items():
        # Expand 'uuid' to work with payment notifications and transaction API queries
        if k == 'uuid' and hasattr(resource, 'nodename') and not hasattr(data, resource.nodename + '_id'):
            data[resource.nodename + '_id'] = v

        # Recursively replace links to known keys with actual models
        # TODO: (IW) Check that all expected foreign keys are mapped
        if k in MODEL_MAP and k in fields:
            logger.debug("Modelifying nested: %s", k)

            if k in context:
                logger.debug("Using provided context object for: %s", k)
                data[k] = context[k]
            else:
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
                # TODO: (IW) Make sure dates are always in UTC and are tz-aware
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
    # TODO: (IW) Auto-save models?
    logger.debug("Returning new %s object", model)
    return model(**update)
