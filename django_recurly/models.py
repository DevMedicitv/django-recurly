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

import logging, sys
logger = logging.getLogger(__name__)

__all__ = ("Account", "Subscription", "User", "Payment", "Token")


BLANKABLE_FIELD_ARGS = dict(blank=True, null=True)

# we let charfields nullable, else overriding from recurly API is a mess...
BLANKABLE_CHARFIELD_ARGS = BLANKABLE_FIELD_ARGS


# Configurable function used to match a new Recurly account with a Django
# User model. Custom functions may accept 'account_code' and 'account' as
# kwargs. It can be overridden in the Django settings file by setting
# 'RECURLY_ACCOUNT_CODE_TO_USER'.
def account_code_to_user(account_code, account):
    #if account_code in settings.RECURLY_OWNER_MAP:
    #    return User.objects.get(email=settings.RECURLY_OWNER_MAP[account_code])
    try:
        return User.objects.get(username=account_code)
    except User.DoesNotExist:
        try:
            return User.objects.get(email=account_code)
        except User.DoesNotExist:
            return None

RECURLY_ACCOUNT_CODE_TO_USER = account_code_to_user
if conf.RECURLY_ACCOUNT_CODE_TO_USER:
    import_parts = conf.RECURLY_ACCOUNT_CODE_TO_USER.rsplit('.', 1)
    mod = importlib.import_module(import_parts[0])
    try:
        RECURLY_ACCOUNT_CODE_TO_USER = getattr(mod, import_parts[1])
    except AttributeError as e:
        logger.warning("User function failed to load: %s", e)
        pass


class ActiveAccountManager(models.Manager):
    def get_query_set(self):
        return super(ActiveAccountManager, self).get_query_set().filter(state="active")


class CurrentSubscriptionManager(models.Manager):
    def get_query_set(self):
        # we returns LIVE subscriptions, i.e. not 'expired' or 'future'
        return (super(CurrentSubscriptionManager, self).get_query_set()
                .filter(Q(state__in=("active", "canceled"))))


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

    UNIQUE_LOOKUP_FIELD = "account_code"

    ACCOUNT_STATES = (
        ("active", "Active"),         # Active account (but may not have billing info)
        ("closed", "Closed"),         # Account has been closed
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="recurly_account",
                             on_delete=models.SET_NULL, **BLANKABLE_FIELD_ARGS)

    account_code = models.CharField(max_length=50, unique=True)

    state = models.CharField(max_length=20, default="active", choices=ACCOUNT_STATES)

    username = models.CharField(max_length=50, **BLANKABLE_CHARFIELD_ARGS)
    email = models.CharField(max_length=100, **BLANKABLE_CHARFIELD_ARGS)
    cc_emails = models.TextField(max_length=100, **BLANKABLE_FIELD_ARGS)  # comma-separated list
    first_name = models.CharField(max_length=50, **BLANKABLE_CHARFIELD_ARGS)
    last_name = models.CharField(max_length=50, **BLANKABLE_CHARFIELD_ARGS)
    company_name = models.CharField(max_length=50, **BLANKABLE_CHARFIELD_ARGS)
    vat_number = models.CharField(max_length=50, **BLANKABLE_CHARFIELD_ARGS)
    tax_exempt = models.NullBooleanField(default=None)

    # no ADDRESS/SHIPPING_ADDRESS info stored for now

    accept_language = models.CharField(max_length=6, **BLANKABLE_CHARFIELD_ARGS)
    hosted_login_token = models.CharField(max_length=40, **BLANKABLE_CHARFIELD_ARGS)

    # REMOTE dates!!
    created_at = models.DateTimeField(**BLANKABLE_FIELD_ARGS)
    updated_at = models.DateTimeField(**BLANKABLE_FIELD_ARGS)
    closed_at = models.DateTimeField(**BLANKABLE_FIELD_ARGS)

    objects = models.Manager()
    active = ActiveAccountManager()

    class Meta:
        ordering = ["-id"]
        get_latest_by = "id"

    def save(self, *args, **kwargs):
        ''' NOPE NOT HERE
        if self.user is None:

            assert RECURLY_ACCOUNT_CODE_TO_USER, RECURLY_ACCOUNT_CODE_TO_USER
            try:
                # Associate the account with a user-defined lookup
                self.user = RECURLY_ACCOUNT_CODE_TO_USER(
                    account_code=self.account_code, account=self)
            except Exception as e:
                raise
                # FIXME - this is deprecated, already done by RECURLY_ACCOUNT_CODE_TO_USER
                # Fallback to email address (the Recurly default)
                logger.warning("User lookup failed for account_code '%s'." \
                    "Falling back to User.email: %s", self.account_code, e)
                try:
                    validate_email(self.account_code)
                    self.user = User.objects.get(email=self.account_code)
                    return True
                except (ValidationError, User.DoesNotExist):  # TODO - multiple objects ??
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
            for attr, value in self.dirty_fields().items():
                setattr(recurly_account, attr, value['new'])
            recurly_account.save()
        '''

        super(Account, self).save(*args, **kwargs)

    def is_active(self):
        return self.state == 'active'

    def has_billing_info(self):
        try:
            self.billing_info
        except BillingInfo.DoesNotExist:
            return False
        return True

    def has_subscription(self, plan_code=None):
        return self.get_subscriptions(plan_code=plan_code).exists()

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
        subscriptions = self.get_subscriptions(plan_code=plan_code)
        if len(subscriptions) > 1:
            raise Subscription.MultipleObjectsReturned()
        elif len(subscriptions) == 0:
            raise Subscription.DoesNotExist()
        return subscriptions[0]

    def get_account(self):
        # TODO: (IW) Cache/store account object
        return recurly.Account.get(self.account_code)
    get_remote_account = get_account

    def get_invoices(self):
        return self.get_account().invoices

    def get_transactions(self):
        try:
            return self.get_account().transactions
        except AttributeError:
            return None

    def _______update_billing_info(self, billing_info):
        if isinstance(billing_info, dict):
            billing_info = recurly.BillingInfo(**billing_info)
        recurly_account = self.get_account()
        recurly_account.update_billing_info(billing_info)

        BillingInfo.sync_billing_info(account_code=self.account_code)

    def close(self):
        recurly_account = self.get_account()
        recurly_account.delete()

        self.sync(recurly_account)

    def reopen(self):
        recurly_account = self.get_account()
        recurly_account.reopen()

        self.sync(recurly_account)

    def subscribe(self, **kwargs):
        recurly_subscription = recurly.Subscription(**kwargs)
        self.get_account().subscribe(recurly_subscription)

        Subscription.sync_subscription(recurly_subscription=recurly_subscription)

    def __________sync(self, recurly_account=None):
        if recurly_account is None:
            recurly_account = self.get_account()
        try:
            data = recurly_account.to_dict()
        except AttributeError:
            logger.debug("Can't sync Account %s, arg is not a Recurly Resource: %s",
                self.pk, recurly_account, exc_info=True)
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
        # Save account
        self.save(remote=False)

        # Update billing info
        try:
            BillingInfo.sync_billing_info(recurly_billing_info=data.billing_info)
        except AttributeError as e:
            BillingInfo.sync_billing_info(account_code=self.account_code)

    @classmethod
    def get_active(class_, user):
        return class_.active.filter(user=user).latest()

    @classmethod
    def update_local_data_from_recurly_resource(cls, recurly_account=None, account_code=None):

        if recurly_account is None:
            assert account_code
            recurly_account = recurly.Account.get(account_code)
        assert isinstance(recurly_account, recurly.Account)

        logger.debug("Account.update_local_data_from_recurly_resource for %s", recurly_account.account_code)
        account = modelify(recurly_account, cls)
        ## useless account.save()

        ''' NOPE
        # Update billing info from nested account data
        if hasattr(recurly_account, "billing_info"):
            BillingInfo.update_local_data_from_recurly_resource(
                recurly_billing_info=recurly_account.billing_info
            )
        else:
            BillingInfo.update_local_data_from_recurly_resource(account_code=account.account_code)
            '''
        return account

    @classmethod
    def create(class_, **kwargs):

        # Make sure billing_info is a Recurly BillingInfo resource
        billing_info = kwargs.pop('billing_info', None)
        if billing_info and not isinstance(billing_info, recurly.BillingInfo):
            billing_info = dict(billing_info)
            kwargs['billing_info'] = recurly.BillingInfo(**billing_info)

        recurly_account = recurly.Account(**kwargs)
        recurly_account.save()  # WS API call

        if 'billing_info' in recurly_account.__dict__:
            # UGLY bug, some attributes like this are not updated by resource.update_from_element()
            del recurly_account.__dict__["billing_info"]

        return class_.update_local_data_from_recurly_resource(recurly_account=recurly_account)

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
            subscription.xml = recurly_subscription.as_log_output()

            subscription.save(remote=False)

        return account, subscription


class BillingInfo(SaveDirtyModel):

    UNIQUE_LOOKUP_FIELD = None

    account = models.OneToOneField(Account, related_name='billing_info')

    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)

    company = models.CharField(max_length=50, **BLANKABLE_CHARFIELD_ARGS)

    address1 = models.CharField(max_length=200, **BLANKABLE_CHARFIELD_ARGS)
    address2 = models.CharField(max_length=200, **BLANKABLE_CHARFIELD_ARGS)

    city = models.CharField(max_length=100, **BLANKABLE_CHARFIELD_ARGS)

    state = models.CharField(max_length=50, **BLANKABLE_CHARFIELD_ARGS)

    zip = models.CharField(max_length=50, **BLANKABLE_CHARFIELD_ARGS)
    country = models.CharField(max_length=2, **BLANKABLE_CHARFIELD_ARGS)
    phone = models.CharField(max_length=50, **BLANKABLE_CHARFIELD_ARGS)

    vat_number = models.CharField(max_length=16, **BLANKABLE_CHARFIELD_ARGS)
    ip_address = models.GenericIPAddressField(**BLANKABLE_FIELD_ARGS)
    ip_address_country = models.CharField(max_length=2, **BLANKABLE_CHARFIELD_ARGS)

    # If billing_type credit_card
    card_type = models.CharField(max_length=50, **BLANKABLE_CHARFIELD_ARGS)
    month = models.IntegerField(**BLANKABLE_FIELD_ARGS)
    year = models.IntegerField(**BLANKABLE_FIELD_ARGS)
    first_six = models.IntegerField(**BLANKABLE_FIELD_ARGS)
    last_four = models.IntegerField(**BLANKABLE_FIELD_ARGS)

    # If billing_type paypal
    paypal_billing_agreement_id = models.CharField(max_length=100, **BLANKABLE_CHARFIELD_ARGS)

    updated_at = models.DateTimeField(**BLANKABLE_FIELD_ARGS)

    @property
    def billing_type(self):
        if self.paypal_billing_agreement_id:
            return "paypal"
        else:
            return "credit_card"


    def save(self, *args, **kwargs):
        '''
        # Update Recurly billing info
        if kwargs.pop('remote', True):
            recurly_account = self.account.get_account()
            recurly_billing_info = recurly_account.billing_info
            for attr, value in self.dirty_fields().items():
                setattr(recurly_billing_info, attr, value['new'])
            account.update_billing_info(billing_info)  #??? FIXME
        '''
        super(BillingInfo, self).save(*args, **kwargs)

    def ______sync(self, recurly_billing_info=None):
        if recurly_billing_info is None:
            recurly_account = self.account.get_account()
            try:
                recurly_billing_info = recurly_account.billing_info
            except AttributeError as e:
                logger.debug("No billing info available for Recurly account '%s' " \
                    "(account_code: '%s').",
                    self.account_id, self.account.account_code, self.pk)
                self.delete()
                return
        try:
            data = recurly_billing_info.to_dict()
        except AttributeError:
            logger.debug("Can't sync BillingInfo %s, arg is not a Recurly Resource: %s",
                self.pk, recurly_billing_info)
            raise

        fields_by_name = dict((field.name, field) for field in self._meta.fields)

        # Update fields
        for k, v in data.items():
            if not v or not hasattr(self, k):
                continue

            if k == 'account':
                continue

            if v and fields_by_name[k].choices:
                v = v.lower()

            setattr(self, k, v)

        self.save(remote=False)

    @classmethod
    def update_local_data_from_recurly_resource(cls, recurly_billing_info):

        logger.debug("BillingInfo.sync: %s", recurly_billing_info)
        billing_info = modelify(recurly_billing_info, cls)

        if hasattr(billing_info, 'account') and not billing_info.account.pk:
            billing_info.account.save(remote=False)
            billing_info.account_id = billing_info.account.pk

        billing_info.save(remote=False)
        return billing_info


class Subscription(SaveDirtyModel):

    UNIQUE_LOOKUP_FIELD = "uuid"

    SUBSCRIPTION_STATES = (
        ("future", "Future"),  # Will become active after a date
        ("active", "Active"),         # Active and everything is fine
        ("canceled", "Canceled"),     # Still active, but will not be renewed
        ("expired", "Expired"),       # Did not renew, or was forcibly expired
    )

    account = models.ForeignKey(Account, **BLANKABLE_FIELD_ARGS)

    uuid = models.CharField(max_length=40, unique=True)  # REQUIRED

    state = models.CharField(max_length=20, default="active", choices=SUBSCRIPTION_STATES)

    plan_code = models.CharField(max_length=60, **BLANKABLE_CHARFIELD_ARGS)
    plan_name = models.CharField(max_length=60, **BLANKABLE_CHARFIELD_ARGS)

    unit_amount_in_cents = models.IntegerField(**BLANKABLE_FIELD_ARGS)  # Not always in cents (i8n)!
    currency = models.CharField(max_length=3, default="USD")

    quantity = models.IntegerField(default=1)

    # REMOTE dates
    activated_at = models.DateTimeField(**BLANKABLE_FIELD_ARGS)
    canceled_at = models.DateTimeField(**BLANKABLE_FIELD_ARGS)
    expires_at = models.DateTimeField(**BLANKABLE_FIELD_ARGS)
    updated_at = models.DateTimeField(**BLANKABLE_FIELD_ARGS)

    current_period_started_at = models.DateTimeField(**BLANKABLE_FIELD_ARGS)
    current_period_ends_at = models.DateTimeField(**BLANKABLE_FIELD_ARGS)
    trial_started_at = models.DateTimeField(**BLANKABLE_FIELD_ARGS)
    trial_ends_at = models.DateTimeField(**BLANKABLE_FIELD_ARGS)

    # TODO - add fields for taxes, addons, gifts, terms etc?

    xml = models.TextField(**BLANKABLE_FIELD_ARGS)

    objects = models.Manager()
    current = CurrentSubscriptionManager()

    class Meta:
        ordering = ["-id"]
        get_latest_by = "id"

    def save(self, *args, **kwargs):
        # Update Recurly subscription
        if kwargs.pop('remote', True):
            recurly_subscription = self.get_subscription()
            for attr, value in self.dirty_fields().items():
                setattr(recurly_subscription, attr, value['new'])
            recurly_subscription.save()

        super(Subscription, self).save(*args, **kwargs)

    def is_canceled(self):
        return self.state == 'canceled'

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

        for k, v in kwargs.items():
            setattr(recurly_subscription, k, v)
        recurly_subscription.timeframe = timeframe
        recurly_subscription.save()

        self.sync(recurly_subscription)

    def cancel(self):
        """Cancel the subscription, it will expire at the end of the current
        billing cycle"""
        recurly_subscription = self.get_subscription()
        if recurly_subscription.state == 'active':
            recurly_subscription.cancel()

        self.sync(recurly_subscription)

    def reactivate(self):
        """Reactivate the canceled subscription so it renews at the end of the
        current billing cycle"""
        recurly_subscription = self.get_subscription()
        if recurly_subscription.state == 'canceled':
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

    def sync(self, recurly_subscription=None):
        if recurly_subscription is None:
            recurly_subscription = self.get_subscription()
        try:
            data = recurly_subscription.to_dict()
        except AttributeError:
            logger.debug("Can't sync Subscription %s, arg is not a Recurly Resource: %s",
                self.pk, recurly_subscription)
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

        logger.debug("Subscription.sync: %s", recurly_subscription.uuid)
        subscription = modelify(recurly_subscription, class_, follow=['account'])
        subscription.xml = recurly_subscription.as_log_output()

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

        if hasattr(subscription, 'account'):
            # Save the account
            if not subscription.account.pk:
                subscription.account.save(remote=False)
                subscription.account_id = subscription.account.pk

        subscription.save(remote=False)
        return subscription

    @classmethod
    def create(class_, **kwargs):
        recurly_subscription = recurly.Subscription(**kwargs)
        recurly_subscription.save()

        return class_.sync_subscription(recurly_subscription=recurly_subscription)


# TODO - update fields of this model according to recurly.Transaction
class Payment(SaveDirtyModel):

    UNIQUE_LOOKUP_FIELD = "transaction_id"

    ACTION_CHOICES = (
        ("verify", "Verify"),
        ("purchase", "Purchase"),
        ("refund", "Refund"),
        # ("credit", "Credit"),                   # Push notifications
    )

    STATUS_CHOICES = (
        ("success", "Success"),
        ("failed", "Failed"),
        ("void", "Void"),
        # ("declined", "Declined"),               # Push notifications
    )

    SOURCE_CHOICES = (
        ("transaction", "One-time transaction"),
        ("subscription", "Subscription"),
        ("billing_info", "Updated billing info"),
    )

    account = models.ForeignKey(Account, db_index=True, **BLANKABLE_FIELD_ARGS)
    transaction_id = models.CharField(max_length=40, unique=True, db_index=True)
    invoice_id = models.CharField(max_length=40, db_index=True, **BLANKABLE_CHARFIELD_ARGS)
    action = models.CharField(max_length=10, choices=ACTION_CHOICES)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    source = models.CharField(max_length=100, choices=SOURCE_CHOICES)
    amount_in_cents = models.IntegerField(**BLANKABLE_FIELD_ARGS)  # Not always in 'cents' (i8n)!
    created_at = models.DateTimeField(**BLANKABLE_FIELD_ARGS)

    message = models.CharField(max_length=250)  # Only set from push notifications

    reference = models.CharField(max_length=100, **BLANKABLE_CHARFIELD_ARGS)
    details = models.TextField(**BLANKABLE_FIELD_ARGS)
    xml = models.TextField(**BLANKABLE_FIELD_ARGS)

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

        logger.debug("Payment.sync: %s", recurly_transaction.uuid)
        payment = modelify(recurly_transaction, class_, remove_empty=True, follow=['account'])
        payment.xml = recurly_transaction.as_log_output(full=True)

        if payment.invoice_id is None:
            payment.invoice_id = recurly_transaction.invoice().uuid

        # TODO: (IW) Hacky
        if hasattr(payment, 'account'):
            # Account
            if not payment.account.pk:
                payment.account.save(remote=False)
                payment.account_id = payment.account.pk

        if payment.is_dirty():
            logger.debug("dirty payment: %s", payment.dirty_fields())
        payment.save()
        return payment

    @classmethod
    def handle_notification(class_, **kwargs):
        # Get latest transaction details from Recurly
        recurly_transaction = recurly.Transaction.get(kwargs.get("transaction").id)

        payment = modelify(recurly_transaction, class_, remove_empty=True)
        payment.invoice_id = recurly_transaction.invoice().uuid
        # payment.xml = recurly_transaction.as_log_output(full=True)

        # Extra data sent only with notifications
        notification_transaction = kwargs.get('transaction')
        payment.message = notification_transaction.message
        payment.notification_xml = kwargs.get('xml')

        if hasattr(payment, 'account'):
            # Account
            if payment.account is not None and not payment.account.pk:
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

    account = models.ForeignKey(Account, related_name="tokens", **BLANKABLE_FIELD_ARGS)
    token = models.CharField(max_length=40, unique=True)
    cls = models.CharField(max_length=12, choices=TYPE_CHOICES)
    identifier = models.CharField(max_length=40)
    xml = models.TextField(**BLANKABLE_FIELD_ARGS)



# Connect model signal handlers

post_save.connect(handlers.account_post_save, sender=Account, dispatch_uid="account_post_save")
post_save.connect(handlers.billing_info_post_save, sender=BillingInfo, dispatch_uid="billing_info_post_save")
post_save.connect(handlers.subscription_post_save, sender=Subscription, dispatch_uid="subscription_post_save")
post_save.connect(handlers.payment_post_save, sender=Payment, dispatch_uid="payment_post_save")
post_save.connect(handlers.token_post_save, sender=Token, dispatch_uid="token_post_save")


### Helpers ###


def modelify(resource, model_class, existing_instance=None, remove_empty=False, presave_callback=None):
    """
    Convert recurly resource objects to django models, by creating new instances or updating existing ones.

    Saves immediately the models created/updated.
    """

    __old = '''Modelify handles the dirty work of converting Recurly Resource objects to
    Django model instances, including resolving any additional Resource objects
    required to satisfy foreign key relationships. This method will query for
    existing instances based on unique model fields, or return a new instance if
    there is no match. Modelify does not save any models back to the database,
    it is left up to the application logic to decide when to do that.'''

    sentinel = object()

    # maps substructures of recurly records to corresponding django models
    SUBMODEL_MAPPER = {
        #'account': Account,
        'billing_info': BillingInfo,
        #'subscription': Subscription,
        #'transaction': Payment,
    }

    UNTOUCHABLE_MODEL_FIELDS = ["id", "user", "account"] + list(SUBMODEL_MAPPER.keys())  # pk and foreign keys
    EXTRA_ATTRIBUTES = ("hosted_login_token", "state", "closed_at")  # missing in resource.attributes
    model_fields_by_name = dict((field.name, field) for field in model_class._meta.fields
                                if field.name not in UNTOUCHABLE_MODEL_FIELDS)
    model_fields = set(model_fields_by_name.keys())

    # we ensure that missing attributes of xml payload don't lead to bad overrides of model fields
    # some values may be present and None though, due to nil="nil" xml attribute
    remote_data = {key: getattr(resource, key, sentinel) for key in resource.attributes + EXTRA_ATTRIBUTES}
    remote_data = {key: value for (key, value) in remote_data.items() if value is not sentinel}

    logger.debug("Modelify %s record input: %s", resource.nodename, remote_data)

    '''
    for k, v in data.copy().items():

        # FIXME - still useful ???
        # Expand 'uuid' to work with payment notifications and transaction API queries
        if k == 'uuid' and hasattr(resource, 'nodename') and not hasattr(data, resource.nodename + '_id'):
            data[resource.nodename + '_id'] = v

        # Recursively replace links to known keys with actual models
        # TODO: (IW) Check that all expected foreign keys are mapped
        if k in MODEL_MAP and k in fields:
            if k in context:
                logger.debug("Using provided context object for: %s", k)
                data[k] = context[k]
            elif not k in follow:
                logger.debug("Not following linked: %s", k)
                del data[k]
                continue

            logger.debug("Following linked: %s", k)
            if isinstance(v, str):
                try:
                    v = resource.link(k)
                except AttributeError:
                    pass

            if callable(v):  # ??? when ???
                v = v()

            logger.debug("Modelifying nested: %s", k)
            # TODO: (IW) This won't attach foreign keys for reverse lookups
            # e.g. account has no attribute 'billing_info'
            data[k] = modelify(v, MODEL_MAP[k], remove_empty=remove_empty, follow=follow, context=context)
    '''


    model_updates = {}

    for k, v in remote_data.items():

        if k not in model_fields:
            continue  # data not mirrored in SQL DB

        # Fields with limited choices should always be lower case
        if v and model_fields_by_name[k].choices:
            v = v.lower()  # this shall be a string

        if v or not remove_empty:
            model_updates[k] = v

    logger.debug("Modelify %s model pending updates: %s", resource.nodename, model_updates)

    # Check for existing model object with the same unique field (account_code, uuid...)

    if existing_instance:
        logger.debug("Using already provided %s instance with id=%s for update",
                     model_class.__name__, existing_instance.pk)

    elif model_class.UNIQUE_LOOKUP_FIELD:

        if not model_updates.get(model_class.UNIQUE_LOOKUP_FIELD):
            raise RuntimeError("Remote recurly record has no value for unique field %s" %
                                 model_class.UNIQUE_LOOKUP_FIELD)

        unique_field_filter = {model_class.UNIQUE_LOOKUP_FIELD:
                               model_updates[model_class.UNIQUE_LOOKUP_FIELD]}

        try:
            existing_instance = model_class.objects.get(**unique_field_filter)
            logger.debug("Found existing %s instance id=%s matching remote recurly data",
                         model_class.__name__, existing_instance.pk)
        except model_class.DoesNotExist:
            logger.debug("No %s instance found matching unique field filter '%s', returning new object",
                         model_class.__name__, unique_field_filter)

    else:
        pass  # eg. case of a billing_info not existing locally yet

    if existing_instance:
        # Update fields of existing object (even with None values)
        obj = existing_instance
        for k, v in model_updates.items():
            setattr(obj, k, v)
    else:
        # Create a new model instance
        obj = model_class(**model_updates)

    if presave_callback:
        presave_callback(obj)
    obj.save()  # sets primary key if not present

    for (relation, subsinstance_klass) in SUBMODEL_MAPPER.items():

        if not hasattr(model_class, relation):
            continue  # this model doesn't contain such a relation

        is_one_to_one_relation = not relation.endswith("s")  # quick and dirty
        if is_one_to_one_relation:
            def _new_presave_callback(_subobj):
                setattr(obj, relation, _subobj)
        else:
            # it's a pool of related objects like "subscriptions"...
            def _new_presave_callback(_subobj):
                rels = getattr(obj, relation)
                rels.add(_subobj)

        local_instance = getattr(obj, relation, None)

        logger.debug("LOOOOOOOOKUUING UP RESOURCE EXTRACT %s %s %s", resource, relation, resource.__dict__)
        remote_resource = getattr(resource, relation, None)
        #logger.debug("Remote_resource _elem: %s", remote_resource._elem)

        if remote_resource:
            # we create or override sub-instance
            subobj = modelify(remote_resource, subsinstance_klass,
                              existing_instance=local_instance,
                              presave_callback=_new_presave_callback)
            setattr(obj, relation, subobj)
        else:
            assert not remote_resource
            if local_instance:
                local_instance.delete()  # delete obsolete instance
                setattr(obj, relation, None)  # security
            else:
                pass  # both unexisting, it's OK

    return obj


