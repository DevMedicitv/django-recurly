from django.db import models
from django.contrib.auth.models import User
from datetime import datetime

from django_recurly.utilities import random_string, modelify

SUBSCRIPTION_STATES = (
    ("active", "Active"),         # Active and everything is fine
    ("cancelled", "Cancelled"),   # Still active, but will not be renewed
    ("expired", "Expired"),       # Did not renews, or was forcibly expired early
)

__all__ = ("Account", "Subscription", "User")

class Account(models.Model):
    account_code = models.CharField(max_length=32, unique=True)
    user = models.ForeignKey(User)
    created_at = models.DateTimeField(default=datetime.now())
    email = models.CharField(max_length=100)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    company_name = models.CharField(max_length=100, blank=True, null=True)
    cancelled = models.BooleanField(default=False)
    hosted_login_token = models.CharField(max_length=32, blank=True, null=True)
    
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
        for subscription in self.get_subscriptions():
            if subscription.is_current():
                return subscription
        
        return None
    
    def fetch_hosted_login_token(self):
        raise NotImplemented("Well, it's not. Sorry.")
    
    @classmethod
    def get_current(class_, user):
        return class_.objects.filter(user=user, cancelled=False).latest()
    
    @classmethod
    def update_from_xml(class_, data):
        """Update/create an account and it's associated subscription using data from Recurly"""
        
        # First get/create the account
        account_data = modelify(data.get("account"), Account)
        
        account, created = class_.objects.get_or_create(
            account_code=account_data["account_code"],
            defaults=account_data
        )
        
        if not created:
            for k, v in account_data.items():
                setattr(account, k, v)
            account.save()
        
        # Now get/create the subscription
        if not data.get("subscription"):
            return account, None
        
        subscription_data = modelify(data.get("subscription"), Subscription)
        subscription = account.get_current_subscription()
    
        if not subscription:
            # Not found, create it
            subscription = Subscription.objects.create(account=account, **subscription_data)
        else:
            # Found, update it
            subscription.update(**subscription_data)
            subscription.save()
        
        return account, subscription
    

class Subscription(models.Model):
    account = models.ForeignKey(Account)
    plan_code = models.CharField(max_length=100)
    plan_version = models.IntegerField(default=1)
    state = models.CharField(max_length=20, default="active", choices=SUBSCRIPTION_STATES)
    quantity = models.IntegerField(default=1)
    total_amount_in_cents = models.DecimalField(blank=True, null=True, decimal_places=2, max_digits=8) # NOT ALWAYS IN CENTS!
    activated_at = models.DateTimeField(blank=True, null=True)
    cancelled_at = models.DateTimeField(blank=True, null=True)
    expires_at = models.DateTimeField(blank=True, null=True)
    current_period_started_at = models.DateTimeField(blank=True, null=True)
    current_period_ends_at = models.DateTimeField(blank=True, null=True)
    trial_started_at = models.DateTimeField(blank=True, null=True)
    trial_ends_at = models.DateTimeField(blank=True, null=True)
    
    super_subscription = models.BooleanField(default=False)
    
    class Meta:
        ordering = ["-id"]
        get_latest_by = "id"
    
    def is_current(self):
        """Is this subscription current (i.e. not expired and good to be used)
        
        Note that 'cancelled' accounts are actually still 'current', as 
        'cancelled' just indicates they they will not renew after the 
        current billing period (at which point Recurly will tell us that 
        they are 'expired')
        """
        
        return self.super_subscription or self.state in ("active", "cancelled")
    
    def is_trial(self):
        if self.super_subscription:
            return False
        
        if not trial_started_at or not trial_ends_at:
            return False # No trial dates, so not a trial
        
        now = datetime.now()
        if trial_started_at <= now and trial_ends_at > now:
            return True
        else:
            return False
    
