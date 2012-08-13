from django.core.management.base import BaseCommand

from django_recurly import recurly

import datetime
import json
import sys

from optparse import make_option


class JsonEncoder(json.JSONEncoder):
    def default(self, obj):

        if isinstance(obj, datetime.datetime) or \
                isinstance(obj, recurly.resource.Money):
            return str(obj)

        if callable(obj):
            return obj().to_dict()

        if isinstance(obj, recurly.SubscriptionAddOn):
            return obj.to_dict()

        try:
            if issubclass(obj, dict) or issubclass(obj, list):
                return list(obj)
        except:
            pass

        return json.JSONEncoder.default(self, obj)


def dump(obj):
    return json.dumps(
        obj.to_dict(),
        sort_keys=True,
        indent=4,
        cls=JsonEncoder)


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

        if options['accounts']:
            account = recurly.Account().get(options['account'])
            print(dump(account))

        elif options['account']:
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
