from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models
from django.db.models import Q
from django.contrib.auth.models import User
from django_extensions.db.models import TimeStampedModel
from django.utils import timezone
from django.core.validators import validate_email
from django.core.exceptions import ValidationError

from django_recurly import monkey  # patches recurly client
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


class LiveSubscriptionsManager(models.Manager):
    def get_query_set(self):
        # we returns LIVE subscriptions, i.e. not 'expired' or 'future'
        return (super(LiveSubscriptionsManager, self).get_query_set()
                .filter(Q(state__in=Subscription.LIVE_STATES)))


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

    # BEWARE - no foreign key, because User model might be in a different DB
    user_id = models.IntegerField(unique=True, **BLANKABLE_FIELD_ARGS)

    # This field can be used to enforce periodic auto-sync of users,
    # eg. in case account has been modified from recurly console and no webhook was used
    last_provisioning_sync = models.DateTimeField(**BLANKABLE_FIELD_ARGS)

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
    has_past_due_invoice = models.NullBooleanField(default=None)

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

    @property
    def user(self):
        user_id = self.user_id
        user_model = get_user_model()
        if user_id:
            # might raise DoesNotExist if serious desync
            return user_model.objects.get(pk=user_id)
        return None


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

    def __is_active(self):
        return self.state == 'active'

    def __has_billing_info(self):
        try:
            self.billing_info
        except BillingInfo.DoesNotExist:
            return False
        return True

    def __has_subscription(self, plan_code=None):
        return self.get_subscriptions(plan_code=plan_code).exists()

    def __get_subscriptions(self, plan_code=None):
        """Get current (i.e. not 'expired') subscriptions for this Account. If
        no `plan_code` is specified then all current subscriptions are returned.

        NOTE: an account may have multiple subscriptions of the same `plan_code`,
        though recurly prevent multiple ACTIVE subscriptions on the same `plan_code`.
        """
        if plan_code is not None:
            return Subscription.live_subscriptions.filter(account=self, plan_code=plan_code)
        else:
            return Subscription.live_subscriptions.filter(account=self)

    def __get_subscription(self, plan_code=None):
        """Get current subscription of type `plan_code` for this Account.

        An exception will be raised if the account has more than one non-expired
        subscription of the specified type.
        """
        subscriptions = self.get_subscriptions(plan_code=plan_code)
        return subscriptions[0]

    def get_live_subscription_or_none(self):  # FIXME - test this
        """
            A SINGLE live subscription is returned.
        """

        plan_codes = [plan.get('plan_code') for plan in settings.RECURLY_PLANS]

        # RECURLY_PLAN doesn't list latin plans whose plan_code are like "plan_code+latin-america"
        q_objects = Q()
        for plan_code in plan_codes:
            q_objects |= Q(plan_code__contains=plan_code)

        queryset = Subscription.objects.filter(Q(account=self) & Q(state__in=Subscription.LIVE_STATES) & q_objects)

        return queryset.first()

    def get_live_rented_movie_subscription(self):
        """
            RECURLY_MOVIE_RENTAL_PLAN is a list of subscription for the movie rental
        """
        plan_codes = [plan.get('plan_code') for plan in settings.RECURLY_MOVIE_RENTAL_PLAN]
        queryset = Subscription.objects.filter(account=self, state__in=Subscription.LIVE_STATES,
                                               plan_code__in=plan_codes)
        subscriptions = queryset.all()
        return subscriptions

    def get_active_rented_movies(self):
        rented_movie_ids = []
        rented_movie_subscription = self.get_live_rented_movie_subscription()
        for subscription in rented_movie_subscription:
            for subscription_add_on in subscription.subscription_add_ons.all():
                # format add_on_code ex: "movie_100"
                rented_movie_ids.append(subscription_add_on.add_on_code.partition("movie_")[2])
        return rented_movie_ids

    def get_recurly_account(self):
        # TODO: (IW) Cache/store account object
        return recurly.Account.get(self.account_code)

    def get_recurly_invoices(self):
        return self.get_recurly_account().invoices()

    def __get_transactions(self):
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

    def __close(self):
        recurly_account = self.get_recurly_account()
        recurly_account.close()

        self.sync(recurly_account)

    def __reopen(self):
        recurly_account = self.get_account()
        recurly_account.reopen()

        self.sync(recurly_account)

    def __subscribe(self, **kwargs):
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
    def __get_active(class_, user):
        return class_.active.filter(user=user).latest()


    def _________create_subscription(class_, **kwargs):
        """Automatically attaches the new subscription to account instance"""
        subscription = Subscription.create(**kwargs)
        subscription.account = self
        subscription.save()



    @classmethod
    def __handle_notification(class_, **kwargs):
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

    def get_acquisition_data(self):
        recurly.AccountAcquisition.member_path="accounts/%s/acquisition"
        try:
            acquisition_data = recurly.AccountAcquisition.get(self.account_code)
            return acquisition_data
        except recurly.errors.NotFoundError:
            return None

    def redeem_coupon(self, coupon_code):
        from recurly import Coupon, Redemption
        coupon = Coupon.get(coupon_code)
        redemption = Redemption(account_code=self.account_code)
        redemption = coupon.redeem(redemption)
        return redemption


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
    country = models.CharField(max_length=5, **BLANKABLE_CHARFIELD_ARGS)
    phone = models.CharField(max_length=50, **BLANKABLE_CHARFIELD_ARGS)

    vat_number = models.CharField(max_length=16, **BLANKABLE_CHARFIELD_ARGS)
    ip_address = models.GenericIPAddressField(**BLANKABLE_FIELD_ARGS)
    ip_address_country = models.CharField(max_length=5, **BLANKABLE_CHARFIELD_ARGS)

    # If billing_type credit_card
    card_type = models.CharField(max_length=50, **BLANKABLE_CHARFIELD_ARGS)
    month = models.IntegerField(**BLANKABLE_FIELD_ARGS)
    year = models.IntegerField(**BLANKABLE_FIELD_ARGS)
    last_four = models.IntegerField(**BLANKABLE_FIELD_ARGS)  # not "first_six" too, it'd be too much info

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

    def purge_billing_info(self):
        self.company = None
        self.address1 = None
        self.address2 = None
        self.city = None
        self.state = None
        self.zip = None
        self.country = None
        self.phone = None
        self.vat_number = None
        self.ip_address = None
        self.ip_address_country = None
        self.card_type = None
        self.month = None
        self.year = None
        self.last_four = None
        self.paypal_billing_agreement_id = None
        self.updated_at = None
        self.save()


class Subscription(SaveDirtyModel):

    UNIQUE_LOOKUP_FIELD = "uuid"

    SUBSCRIPTION_STATES = (
        ("future", "Future"),         # Will become active after a date
        ("active", "Active"),         # Active and everything is fine
        ("canceled", "Canceled"),     # Still active, but will not be renewed
        ("expired", "Expired"),       # Did not renew, or was forcibly expired
    )

    COLLECTION_METHODS = (
        ('automatic', 'Automatic'),
        ('manual', 'Manual')
    )

    LIVE_STATES = ("active", "canceled")  # subscriptions granting premium NOW

    account = models.ForeignKey(Account, related_name="subscriptions", **BLANKABLE_FIELD_ARGS)

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
    collection_method = models.CharField(max_length=20, default='automatic', choices=COLLECTION_METHODS)
    imported_trial = models.BooleanField(default=False)
    started_with_gift = models.BooleanField(default=False)
    legacy_starts_at = models.DateTimeField(**BLANKABLE_FIELD_ARGS)  # by default the same as activated_at, but can be different if subscription imported from legacy


    # TODO - add fields for taxes, addons, gifts, terms etc?

    xml = models.TextField(**BLANKABLE_FIELD_ARGS)

    objects = models.Manager()
    live_subscriptions = LiveSubscriptionsManager()

    class Meta:
        ordering = ["-id"]
        get_latest_by = "id"

    def save(self, *args, **kwargs):

        '''
        # Update Recurly subscription
        if kwargs.pop('remote', True):
            recurly_subscription = self.get_subscription()
            for attr, value in self.dirty_fields().items():
                setattr(recurly_subscription, attr, value['new'])
            recurly_subscription.save()
        '''

        super(Subscription, self).save(*args, **kwargs)


    @property
    def is_live(self):
        return self.state in self.LIVE_STATES

    @property
    def is_canceled(self):
        return self.state == 'canceled'

    @property
    def is_cancellable(self):
        return self.state in ('future', 'active')


    @property
    def ___is_current(self):
        """Is this subscription current (i.e. not 'expired')

        Note that 'canceled' subscriptions are actually still considered
        current, as 'canceled' just indicates they they will not renew after
        the current billing period (at which point Recurly will tell us that
        they are 'expired')
        """
        res = (self.is_live or self.state == "future")
        assert res == (self.state != "expired")  # safety check
        return res

    def is_in_trial(self):
        if not self.trial_started_at or not self.trial_ends_at:
            return False  # No trial dates, so not a trial
        now = timezone.now()
        if self.trial_started_at <= now and self.trial_ends_at > now:
            return True
        return False

    def get_recurly_subscription(self):
        # TODO: (IW) Cache/store subscription object
        return recurly.Subscription.get(self.uuid)

    def get_pending_subscription_or_none(self):
        recurly_subscription = self.get_recurly_subscription()
        recurly_pending_subscription = getattr(recurly_subscription, "pending_subscription", None)
        if recurly_pending_subscription:
            from django_recurly.provisioning import modelify
            pending_subscription = modelify(recurly_pending_subscription, Subscription, save=False)
            return pending_subscription
        return None

    def get_subcription_date(self):
        if self.legacy_starts_at:
            return self.legacy_starts_at
        return self.activated_at

    def __get_pending_changes(self):
        if self.xml is None:
            return None
        try:
            return recurly.Subscription().from_element(self.xml).pending_subscription
        except Exception as e:
            logger.debug("Failed to get pending changes: %s", e)
            return None

    def __get_plan(self):
        return recurly.Plan.get(self.plan_code)

    def __change_plan(self, plan_code, timeframe='now'):
        """Change this subscription to the specified plan_code.

        This will call the Recurly API and update the subscription.
        """
        self.change(timeframe, plan_code=plan_code)

    def __change_quantity(self, quantity, incremental=False, timeframe='now'):
        """Change this subscription quantity. The quantity will be changed to
        `quantity` if `incremental` is `False`, and increment the quantity by
        `quantity` if `incremental` is `True`.

        This will call the Recurly API and update the subscription.
        """

        new_quantity = quantity if not incremental else (self.quantity + quantity)

        self.change(timeframe, quantity=new_quantity)

    def __change(self, timeframe='now', **kwargs):
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

    def __cancel(self):
        """Cancel the subscription, it will expire at the end of the current
        billing cycle"""
        recurly_subscription = self.get_subscription()
        if recurly_subscription.state == 'active':
            recurly_subscription.cancel()

        self.sync(recurly_subscription)

    def reactivate(self):
        """Reactivate the canceled subscription so it renews at the end of the
        current billing cycle"""
        recurly_subscription = self.get_recurly_subscription()
        if recurly_subscription.state == 'canceled':
            recurly_subscription.reactivate()

    def __terminate(self, refund="none"):
        """Terminate the subscription

        `refund` may be one of:
            - "none" : No refund, subscription is just expired
            - "partial" : Give a prorated refund
            - "full" : Provide a full refund of the most recent charge
        """
        recurly_subscription = self.get_subscription()
        recurly_subscription.terminate(refund=refund)

        self.sync(recurly_subscription)

    def ______sync(self, recurly_subscription=None):
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
    def __get_plans(class_):
        return [plan.name for plan in recurly.Plan.all()]

    @classmethod
    def ______sync_subscription(class_, recurly_subscription=None, uuid=None):
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


class SubscriptionAddOn(SaveDirtyModel):
    subscription = models.ForeignKey(Subscription, related_name="subscription_add_ons", **BLANKABLE_FIELD_ARGS)
    add_on_code = models.CharField(max_length=200)
    quantity = models.IntegerField(default=1)
    unit_amount_in_cents = models.IntegerField(**BLANKABLE_FIELD_ARGS)
    address = models.CharField(max_length=200, **BLANKABLE_CHARFIELD_ARGS)


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



class GiftCardMemo(TimeStampedModel):
    """
    The only purpose of this table is to remember how many months a gift card
    is equivalent to, when it's purchased.

    The target "plan code" is supposed to be a fixed-length, non-renewable
    premium subscription whose pricing will be set equal to the gift
    card value, when redeeming occurs.
    """
    gift_card_id = models.CharField(max_length=50, unique=True)
    redemption_code = models.CharField(max_length=50, unique=True, null=True)  # null due to retrocompatibility
    redemption_date = models.DateTimeField(**BLANKABLE_FIELD_ARGS)
    target_plan_code = models.CharField(max_length=50)




# Connect model signal handlers
''' DISABLED ATM BECAUSE UNTESTED

post_save.connect(handlers.account_post_save, sender=Account, dispatch_uid="account_post_save")
post_save.connect(handlers.billing_info_post_save, sender=BillingInfo, dispatch_uid="billing_info_post_save")
post_save.connect(handlers.subscription_post_save, sender=Subscription, dispatch_uid="subscription_post_save")
post_save.connect(handlers.payment_post_save, sender=Payment, dispatch_uid="payment_post_save")
post_save.connect(handlers.token_post_save, sender=Token, dispatch_uid="token_post_save")

'''
