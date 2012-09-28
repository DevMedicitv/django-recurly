import sys

from django.core.management.base import BaseCommand
from optparse import make_option

from django_recurly.utils import dump
from django_recurly import recurly

class Command(BaseCommand):
    option_list = BaseCommand.option_list + (

        make_option('--accounts',
            action='store_true',
            dest='accounts',
            default=False,
            help='List all active accounts'),
        make_option('--account',
            dest='account',
            help='Get the specified account by account_code'),

        make_option('--subscriptions',
            action='store_true',
            dest='subscriptions',
            default=False,
            help='List all subscriptions'),
        make_option('--subscription',
            dest='subscription',
            help='Get the specified subscription by uuid'),

        make_option('--plans',
            action='store_true',
            dest='plans',
            default=False,
            help='List all available plans'),
        make_option('--plan',
            dest='plan',
            help='Get the specified plan by plan_code'),
    )

    help = 'Query Recurly for current data.'

    def handle(self, *args, **options):

        if options['accounts']:
            for account in recurly.Account.all_active():
                print(dump(account))
        elif options['account']:
            account = recurly.Account.get(options['account'])
            print(dump(account))

        elif options['subscriptions']:
            for subscription in recurly.Subscription.all():
                print(dump(subscription))
        elif options['subscription']:
            subscription = recurly.Subscription.get(options['subscription'])
            print(dump(subscription))

        elif options['plans']:
            for plan in recurly.Plan.all():
                print(dump(plan))
        elif options['plan']:
            plan = recurly.Plan.get(options['plan'])
            print(dump(plan))

        else:
            self.print_help(None, None)
            sys.exit(1)
