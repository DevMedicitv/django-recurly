import sys

from django.core.management.base import BaseCommand
from optparse import make_option

from django_recurly.util import dump
from django_recurly import recurly

class Command(BaseCommand):
    option_list = BaseCommand.option_list + (

        make_option('--accounts',
            action='store_true',
            dest='accounts',
            default=False,
            help='List all the accounts'),
        make_option('--account',
            dest='account',
            help='Get the specified account by code'),

        make_option('--subscription',
            dest='subscription',
            help='Get the specified subscription by uuid'),
        make_option('--subscriptions',
            action='store_true',
            dest='subscriptions',
            default=False,
            help='List all the subscriptions'),

        make_option('--plan',
            dest='plan',
            help='Get the specified plan by code'),
        make_option('--plans',
            action='store_true',
            dest='plans',
            default=False,
            help='List all the subscriptions'),
         )

    help = 'Display recurly data'

    def handle(self, *args, **options):

        if options['account']:
            account = recurly.Account().get(options['account'])
            print(dump(account))

        elif options['accounts']:
            for account in recurly.Account().all_active():
                print(dump(account))

        elif options['plan']:
            plan = recurly.Plan().get(options['plan'])
            print(dump(plan))

        elif options['plans']:
            for plan in recurly.Plan().all():
                print(dump(plan))

        elif options['subscription']:
            subscription = recurly.Subscription().get(options['subscription'])
            print(dump(subscription))

        elif options['subscriptions']:
            for subscription in recurly.Subscription().all():
                print(dump(subscription))

        else:
            self.print_help(None, None)
            sys.exit(1)
