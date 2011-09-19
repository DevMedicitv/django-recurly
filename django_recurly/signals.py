# http://docs.recurly.com/integration/push-notifications

from django.dispatch import Signal

## General use signals ##

# Fired when a user gains a valid (i.e. current) account
account_opened = Signal(providing_args=('account','subscription'))

# Fired when a user's valid (i.e. current) account stops being valid (i.e. is 'expired')
account_closed = Signal(providing_args=('account','subscription'))

## Notifications from recurly ##

# Accounts
new_account_notification = Signal(providing_args=('data',))
canceled_account_notification = Signal(providing_args=('data',))
billing_info_updated_notification = Signal(providing_args=('data',))

# Subscriptions
new_subscription_notification = Signal(providing_args=('data',))
updated_subscription_notification = Signal(providing_args=('data',))
expired_subscription_notification = Signal(providing_args=('data',))
canceled_subscription_notification = Signal(providing_args=('data',))
renewed_subscription_notification = Signal(providing_args=('data',))
reactivated_account_notification = Signal(providing_args=('data',))

# Payments
successful_payment_notification = Signal(providing_args=('data',))
failed_payment_notification = Signal(providing_args=('data',))
successful_refund_notification = Signal(providing_args=('data',))
void_payment_notification = Signal(providing_args=('data',))
