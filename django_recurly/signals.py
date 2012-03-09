# http://docs.recurly.com/integration/push-notifications

from django.dispatch import Signal

# Accounts
new_account_notification = Signal(
        providing_args=('account','xml','type',))
canceled_account_notification = Signal(
        providing_args=('account','xml','type',))
billing_info_updated_notification = Signal(
        providing_args=('account','xml','type',))
reactivated_account_notification = Signal(
        providing_args=('account', 'subscription','xml','type',))

# Subscriptions
new_subscription_notification = Signal(
        providing_args=('account', 'subscription','xml','type',))
updated_subscription_notification = Signal(
        providing_args=('account', 'subscription','xml','type',))
expired_subscription_notification = Signal(
        providing_args=('account', 'subscription','xml','type',))
canceled_subscription_notification = Signal(
        providing_args=('account', 'subscription','xml','type',))
renewed_subscription_notification = Signal(
        providing_args=('account', 'subscription','xml','type',))

# Payments
successful_payment_notification = Signal(
        providing_args=('account', 'transaction','xml','type',))
failed_payment_notification = Signal(
        providing_args=('account', 'transaction','xml','type',))
successful_refund_notification = Signal(
        providing_args=('account', 'transaction','xml','type',))
void_payment_notification = Signal(
        providing_args=('account', 'transaction','xml','type',))
