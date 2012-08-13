from django.core.management.base import BaseCommand

from django_recurly import recurly

import datetime
import json
import sys

from optparse import make_option


class JsonEncoder(json.JSONEncoder):
    def default(self, obj):

        if isinstance(obj, datetime.datetime):
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
            help='Get the specified account code'),
        make_option('--subscription',
            dest='subscription',
            help='Get the specified subscription uuid'),
        make_option('--subscriptions',
            action='store_true',
            dest='subscriptions',
            default=False,
            help='List all the subscriptions'),
        )

    help = 'Display recurly data'

    def handle(self, *args, **options):

        if options['accounts']:
            for account in recurly.Account().all_active():
                print(dump(account))

        elif options['subscriptions']:
            for subscription in recurly.Subscription().all():
                print(dump(subscription))

        elif options['account']:
            account = recurly.Account().get(options['account'])
            print(dump(account))

        elif options['subscription']:
            subscription = recurly.Subscription().get(options['subscription'])
            print(dump(subscription))

        else:
            self.print_help(None, None)
            sys.exit(1)
