import sys

from django.core.management.base import BaseCommand
from optparse import make_option

from django_recurly.utils import dump
from django_recurly import recurly
from django_recurly.models import Account, Subscription, Payment

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
            help='List all the subscriptions'),
        make_option('--subscription',
            dest='subscription',
            help='Get the specified subscription by uuid'),
    )

    help = "Update local Django-Recurly data by querying Recurly. Recurly is assumed to be the point of authority, and this command will overwrite any local discprepancies (unless '--dry-run' is specified)."

    def handle(self, *args, **options):

        if options['accounts']:
            i = 1
            page = recurly.Account.all_active()
            while page is not None:
                print("Syncing page %d..." % i)
                for recurly_account in page:
                    account = Account.sync(recurly_account=recurly_account)
                try:
                    page = page.next_page()
                    i += 1
                except recurly.resource.PageError:
                    page = None
        elif options['account']:
            Account.sync(account_code=options['account'])

        elif options['subscriptions']:
            i = 1
            page = recurly.Subscription.all_live()
            while page is not None:
                print("Syncing page %d..." % i)
                for recurly_subscription in page:
                    subscription = Subscription.sync(recurly_subscription=recurly_subscription)
                try:
                    page = page.next_page()
                    i += 1
                except recurly.resource.PageError:
                    page = None

        elif options['subscription']:
            subscription = recurly.Subscription.get()
            Subscription.sync(uuid=options['subscription'])

        else:
            self.print_help(None, None)
            sys.exit(1)
