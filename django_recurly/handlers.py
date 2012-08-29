"""
Push notifications are not meant to be actionable and should not be used for
critical account functions like provisioning accounts. Use the receipt of a
push notification to trigger an API query, validating both the push
notification action and the details of the action.

http://docs.recurly.com/push-notifications
"""

from django_recurly import signals

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
