import sys

from django.core.management.base import BaseCommand
from optparse import make_option

from django.contrib.auth.models import User
from django_recurly.utils import dump, recurly
from django_recurly.models import Account, BillingInfo, Subscription, Payment


class Command(BaseCommand):
    option_list = BaseCommand.option_list + (

        make_option('--accounts',
            action='store_true',
            dest='accounts',
            default=False,
            help='Sync all active accounts'),
        make_option('--account',
            dest='account',
            help='Sync the specified account by account_code'),

        make_option('--subscriptions',
            action='store_true',
            dest='subscriptions',
            default=False,
            help='Sync all live subscriptions'),
        make_option('--subscription',
            dest='subscription',
            help='Sync the specified subscription by uuid'),

        make_option('--payments',
            action='store_true',
            dest='payments',
            default=False,
            help='Sync all payments'),
        make_option('--payment',
            dest='payment',
            help='Sync the specified payment by transaction uuid'),
    )

    help = "Update local Django-Recurly data by querying Recurly. Recurly is assumed to be the point of authority, and this command will overwrite any local discprepancies (unless '--dry-run' is specified)."

    def handle(self, *args, **options):
        something_chosen = False
        if options['accounts']:
            something_chosen = True

            i = 1
            page = recurly.Account.all()
            while page is not None:
                print("Syncing page %d..." % i)
                for recurly_account in page:
                    try:
                        account = Account.sync_account(recurly_account=recurly_account)
                    except User.DoesNotExist:
                        print("No user for Recurly account with account_code %s" % recurly_account.account_code)

                    if hasattr(recurly_account, 'billing_info'):
                        billing_info = BillingInfo.sync_billing_info(recurly_billing_info=recurly_account.billing_info)
                try:
                    page = page.next_page()
                    i += 1
                except recurly.resource.PageError:
                    page = None

        if options['account']:
            something_chosen = True

            Account.sync_account(account_code=options['account'])

        if options['subscriptions']:
            something_chosen = True

            # Sync all 'live' subscriptions
            i = 1
            page = recurly.Subscription.all_live()
            while page is not None:
                print("Syncing page %d..." % i)
                for recurly_subscription in page:
                    subscription = Subscription.sync_subscription(recurly_subscription=recurly_subscription)
                try:
                    page = page.next_page()
                    i += 1
                except recurly.resource.PageError:
                    page = None

            # Now do the same with 'expired' subscriptions
            i = 1
            page = recurly.Subscription.all_expired()
            while page is not None:
                print("Syncing page %d..." % i)
                for recurly_subscription in page:
                    subscription = Subscription.sync_subscription(recurly_subscription=recurly_subscription)
                try:
                    page = page.next_page()
                    i += 1
                except recurly.resource.PageError:
                    page = None

        if options['subscription']:
            something_chosen = True

            Subscription.sync(uuid=options['subscription'])

        if options['payments']:
            something_chosen = True

            i = 1
            page = recurly.Transaction.all()
            while page is not None:
                print("Syncing page %d..." % i)
                for recurly_transaction in page:
                    if recurly_transaction.action == 'verify':
                        continue
                    payment = Payment.sync_payment(recurly_transaction=recurly_transaction)
                try:
                    page = page.next_page()
                    i += 1
                except recurly.resource.PageError:
                    page = None

        if options['payment']:
            something_chosen = True

            Payment.sync_payment(uuid=options['payment'])

        if not something_chosen:
            self.print_help(None, None)
            sys.exit(1)
