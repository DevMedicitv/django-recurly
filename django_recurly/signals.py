# http://docs.recurly.com/integration/push-notifications

from django.dispatch import Signal


## General use signals ##

# Fired when an account changes
account_updated = Signal(providing_args=('account','subscription'))
# Fired when a user gains a valid (i.e. 'active') account
account_opened = Signal(providing_args=('account','subscription'))
# Fired when a user's active account is closed
account_closed = Signal(providing_args=('account','subscription'))

# Fired when a new subscription is created
subscription_created = Signal(providing_args=('account','subscription'))
# Fired when a subscription changes
subscription_updated = Signal(providing_args=('account','subscription'))
# Fired when a user gains a valid (i.e. not 'expired') subscription
subscription_current = Signal(providing_args=('account','subscription'))
# Fired when a user's subscription expires
subscription_expired = Signal(providing_args=('account','subscription'))

# Fired when a new payment is created
payment_created = Signal(providing_args=('account','payment'))
# Fired when a payment is modified
payment_updated = Signal(providing_args=('account','payment'))


## Push notifications from Recurly ##

# Accounts
new_account_notification = Signal(
        providing_args=('account','xml','type',))
canceled_account_notification = Signal(
        providing_args=('account','xml','type',))
billing_info_updated_notification = Signal(
        providing_args=('account','xml','type',))
reactivated_account_notification = Signal(
        providing_args=('account','subscription','xml','type',))

# Subscriptions
new_subscription_notification = Signal(
        providing_args=('account','subscription','xml','type',))
updated_subscription_notification = Signal(
        providing_args=('account','subscription','xml','type',))
expired_subscription_notification = Signal(
        providing_args=('account','subscription','xml','type',))
canceled_subscription_notification = Signal(
        providing_args=('account','subscription','xml','type',))
renewed_subscription_notification = Signal(
        providing_args=('account','subscription','xml','type',))

# Payments
successful_payment_notification = Signal(
        providing_args=('account','transaction','xml','type',))
failed_payment_notification = Signal(
        providing_args=('account','transaction','xml','type',))
successful_refund_notification = Signal(
        providing_args=('account','transaction','xml','type',))
void_payment_notification = Signal(
        providing_args=('account','transaction','xml','type',))
