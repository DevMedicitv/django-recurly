"""
Push notifications are not meant to be actionable and should not be used for
critical account functions like provisioning accounts. Use the receipt of a
push notification to trigger an API query, validating both the push
notification action and the details of the action.

http://docs.recurly.com/push-notifications
"""
from django_recurly import signals


# Push notification signal handlers

def new(sender, **kwargs):
    """Create the account and the subscription

    We do these at the same time (rather than using
    the new_account signal) to avoid concurrency problems.
    """
    from django_recurly import models
    models.Account.handle_notification(**kwargs)

def update(sender, **kwargs):
    """Update a subscription and account"""
    from django_recurly import models
    models.Account.handle_notification(**kwargs)

def payment(sender, **kwargs):
    from django_recurly import models
    models.Payment.handle_notification(**kwargs)

# Connect push notification signals

#signals.new_account_notification.connect(new)
signals.new_subscription_notification.connect(new)
signals.updated_subscription_notification.connect(update)
signals.expired_subscription_notification.connect(update)
signals.canceled_subscription_notification.connect(update)
signals.renewed_subscription_notification.connect(update)
signals.reactivated_account_notification.connect(update)

signals.canceled_account_notification.connect(update)
signals.billing_info_updated_notification.connect(update)

signals.successful_payment_notification.connect(payment)
signals.failed_payment_notification.connect(payment)
signals.successful_refund_notification.connect(payment)
signals.void_payment_notification.connect(payment)


## Model signal handlers ##

def account_post_save(sender, instance, created, **kwargs):
    if created:
        signals.account_created.send(sender=sender, account=instance)
    else:
        signals.account_updated.send(sender=sender, account=instance)

    was_active = not created and instance._previous_state['state'] == 'active'
    now_active = instance.is_active()

    # Send account closed/opened signals
    if was_active and not now_active:
        signals.account_closed.send(sender=sender, account=instance)
    elif not was_active and now_active:
        signals.account_opened.send(sender=sender, account=instance)

def subscription_post_save(sender, instance, created, **kwargs):
    if created:
        signals.subscription_created.send(sender=sender, subscription=instance)
    else:
        signals.subscription_updated.send(sender=sender, subscription=instance)

    was_current = not created and instance._previous_state['state'] != 'expired'
    now_current = instance.state != 'expired'

    # Send subscription current/expired signals
    if was_current and not now_current:
        signals.subscription_expired.send(sender=sender, subscription=instance)
    elif not was_current and now_current:
        signals.subscription_current.send(sender=sender, subscription=instance)

def payment_post_save(sender, instance, created, **kwargs):
    if created:
        signals.payment_created.send(sender=sender, payment=instance)
    else:
        signals.payment_updated.send(sender=sender, payment=instance)