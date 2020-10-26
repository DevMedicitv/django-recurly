
import copy

import recurly

from recurly.errors import NotFoundError

from .exceptions import PreVerificationTransactionRecurlyError
from .models import logger, Account, BillingInfo, Subscription, SubscriptionAddOn


def _construct_recurly_account_resource(account_params, billing_info_params=None):
    """
    Might modify "account_params" object.

    Returns UNSAVED instance.
    """

    if not isinstance(account_params, recurly.Account):
        account_params = recurly.Account(**account_params)

    if billing_info_params:
        if isinstance(billing_info_params, recurly.BillingInfo):
            billing_info = billing_info_params
        else:
            billing_info = recurly.BillingInfo(**billing_info_params)
        account_params.billing_info = billing_info  # OVERRIDE

    return account_params




def create_and_sync_recurly_account(account_params, billing_info_params=None, acquisition_params=None):
    """
    Creates a remote recurly Account, with a BillingInfo if provided.

    Returns a LOCAL Account instance (maybe with BillingInfo), sync'ed with remote.
    """

    recurly_account = _construct_recurly_account_resource(account_params,
                                                          billing_info_params=billing_info_params)

    recurly_account.save()  # WS API call

    if acquisition_params:
        set_acquisition_data(recurly_account.account_code, acquisition_params)

    # FULL RELOAD because recurly APi client refresh is damn buggy
    recurly_account = recurly.Account.get(recurly_account.account_code)
    '''
    if 'billing_info' in recurly_account.__dict__:
        # UGLY bug, some attributes like this are not updated by resource.update_from_element()
        del recurly_account.__dict__["billing_info"]
    '''
    local_account = update_local_account_data_from_recurly_resource(recurly_account=recurly_account)
    return local_account





def update_and_sync_recurly_billing_info(account, billing_info_params):
    """
    Gets and returns a LOCAL Account instance.
    """
    recurly_account = account.get_recurly_account()
    billing_info = recurly.BillingInfo(**billing_info_params)
    recurly_account.update_billing_info(billing_info)
    if hasattr(account, "billing_info"):
        account.billing_info.purge_billing_info()
    recurly_account = account.get_recurly_account()  # refresh
    local_account = update_local_account_data_from_recurly_resource(recurly_account=recurly_account)
    return local_account


def sync_local_add_ons_from_recurly_resource(remote_subscription, local_subscription):
    def __modelify_add_on(_local_subscription, _remote_subscription_add_on, _local_existing_add_on):
        assert isinstance(_remote_subscription_add_on, recurly.SubscriptionAddOn)

        # Update
        if _local_existing_add_on:
            modelify(_remote_subscription_add_on, SubscriptionAddOn, existing_instance=_local_existing_add_on)
        # Create
        else:
            subscription_add_on = modelify(_remote_subscription_add_on, SubscriptionAddOn)
            _local_subscription.subscription_add_ons.add(subscription_add_on)

    for recurly_subscription_add_on in remote_subscription.subscription_add_ons:
        local_subscription_add_on = \
            local_subscription.subscription_add_ons.filter(add_on_code=recurly_subscription_add_on.add_on_code).first()

        __modelify_add_on(_local_subscription=local_subscription,
                          _remote_subscription_add_on=recurly_subscription_add_on,
                          _local_existing_add_on=local_subscription_add_on,)

    return local_subscription


def create_remote_subsciption(subscription_params, account_params, billing_info_params=None):
    assert "account" not in subscription_params, subscription_params
    recurly_account = _construct_recurly_account_resource(account_params,
                                                          billing_info_params=billing_info_params)

    subscription_params = copy.deepcopy(subscription_params)  # do not touch input object
    subscription_params["account"] = recurly_account

    recurly_subscription = recurly.Subscription(**subscription_params)
    return recurly_subscription


def create_remote_subscription_with_add_on(subscription_params, account_params, add_ons_data, billing_info_params=None):
    def __check_add_ons_code(_subscription_params, _add_ons_data):
        plan = recurly.Plan.get(_subscription_params["plan_code"])
        remote_add_ons_code = [add_on.add_on_code for add_on in plan.add_ons()]
        submitted_add_ons_code = [add_on["add_on_code"] for add_on in _add_ons_data]
        for submit_code in submitted_add_ons_code:
            if submit_code not in remote_add_ons_code:
                raise PreVerificationTransactionRecurlyError(transaction_error_code="invalid_add_ons_code",)

    __check_add_ons_code(subscription_params, add_ons_data)
    remote_subscription = create_remote_subsciption(subscription_params, account_params, billing_info_params)

    created_subscription_add_ons = [recurly.SubscriptionAddOn(
        add_on_code=add_on["add_on_code"],
        quantity=1
    ) for add_on in add_ons_data]

    remote_subscription.subscription_add_ons = created_subscription_add_ons
    return remote_subscription


def create_and_sync_recurly_subscription(subscription_params, account_params,
                                         billing_info_params=None, add_ons_data=None):
    """
    Returns a LOCAL Subscription instance.

    The billing_info_params, if present, will override existing billing info.

    Beware, this newly created Subscription will not be
    automatically attached to a corresponding django Account instance.
    """

    if add_ons_data:
        remote_subscription = create_remote_subscription_with_add_on(subscription_params, account_params,
                                                                     add_ons_data, billing_info_params)
    else:
        remote_subscription = create_remote_subsciption(subscription_params, account_params, billing_info_params)
    remote_subscription.save()
    remote_account = remote_subscription.account()

    # FULL RELOAD because lots of stuffs may have changed, and recurly API client refresh is damn buggy
    account = update_full_local_data_for_account_code(account_code=remote_account.account_code)
    assert account.subscriptions.count()

    subscription = account.subscriptions.filter(uuid=remote_subscription.uuid).first()
    assert subscription
    return subscription


def update_and_sync_recurly_subscription(subscription, subscription_params):
    """
    Gets and returns a LOCAL Subscription instance.
    """
    assert isinstance(subscription, Subscription), subscription

    recurly_subscription = subscription.get_recurly_subscription()

    for (k, v) in subscription_params.items():
        setattr(recurly_subscription, k, v)

    recurly_subscription.save()

    recurly_subscription = subscription.get_recurly_subscription()
    return update_local_subscription_data_from_recurly_resource(
        recurly_subscription=recurly_subscription
    )


def modelify(resource, model_class, existing_instance=None, remove_empty=False, presave_callback=None, save=True):
    """
    Convert recurly resource objects to django models, by creating new instances or updating existing ones.

    Saves immediately the models created/updated, unless save=False if given.
    """

    __old = '''Modelify handles the dirty work of converting Recurly Resource objects to
    Django model instances, including resolving any additional Resource objects
    required to satisfy foreign key relationships. This method will query for
    existing instances based on unique model fields, or return a new instance if
    there is no match. Modelify does not save any models back to the database,
    it is left up to the application logic to decide when to do that.'''

    sentinel = object()

    # maps substructures of recurly records to corresponding django models
    SUBMODEL_MAPPER = {
        #'account': Account,  NOPE
        'billing_info': BillingInfo,
        #'subscription': Subscription,
        #'transaction': Payment,
    }

    UNTOUCHABLE_MODEL_FIELDS = ["id", "user", "account"] + list(SUBMODEL_MAPPER.keys())  # pk and foreign keys
    EXTRA_ATTRIBUTES = ("hosted_login_token", "state", "closed_at")  # missing in resource.attributes
    model_fields_by_name = dict((field.name, field) for field in model_class._meta.fields
                                if field.name not in UNTOUCHABLE_MODEL_FIELDS)
    model_fields = set(model_fields_by_name.keys())

    # we ensure that missing attributes of xml payload don't lead to bad overrides of model fields
    # some values may be present and None though, due to nil="nil" xml attribute
    remote_data = {key: getattr(resource, key, sentinel) for key in resource.attributes + EXTRA_ATTRIBUTES}
    remote_data = {key: value for (key, value) in remote_data.items() if value is not sentinel}

    logger.debug("Modelify %s record input: %s", resource.nodename, remote_data)

    '''
    for k, v in data.copy().items():

        # FIXME - still useful ???
        # Expand 'uuid' to work with payment notifications and transaction API queries
        if k == 'uuid' and hasattr(resource, 'nodename') and not hasattr(data, resource.nodename + '_id'):
            data[resource.nodename + '_id'] = v

        # Recursively replace links to known keys with actual models
        # TODO: (IW) Check that all expected foreign keys are mapped
        if k in MODEL_MAP and k in fields:
            if k in context:
                logger.debug("Using provided context object for: %s", k)
                data[k] = context[k]
            elif not k in follow:
                logger.debug("Not following linked: %s", k)
                del data[k]
                continue

            logger.debug("Following linked: %s", k)
            if isinstance(v, str):
                try:
                    v = resource.link(k)
                except AttributeError:
                    pass

            if callable(v):  # ??? when ???
                v = v()

            logger.debug("Modelifying nested: %s", k)
            # TODO: (IW) This won't attach foreign keys for reverse lookups
            # e.g. account has no attribute 'billing_info'
            data[k] = modelify(v, MODEL_MAP[k], remove_empty=remove_empty, follow=follow, context=context)
    '''


    model_updates = {}

    for k, v in remote_data.items():

        if k not in model_fields:
            continue  # data not mirrored in SQL DB

        # Fields with limited choices should always be lower case
        if v and model_fields_by_name[k].choices:
            v = v.lower()  # this shall be a string

        if v or not remove_empty:
            model_updates[k] = v

    logger.debug("Modelify %s model pending updates: %s", resource.nodename, model_updates)

    # Check for existing model object with the same unique field (account_code, uuid...)

    if existing_instance:
        logger.debug("Using already provided %s instance with id=%s for update",
                     model_class.__name__, existing_instance.pk)

    elif not save:
        pass  # no unicity problem, just a transient object

    elif getattr(model_class, "UNIQUE_LOOKUP_FIELD", None):

        if not model_updates.get(model_class.UNIQUE_LOOKUP_FIELD):
            raise RuntimeError("Remote recurly record has no value for unique field %s" %
                                 model_class.UNIQUE_LOOKUP_FIELD)

        unique_field_filter = {model_class.UNIQUE_LOOKUP_FIELD:
                               model_updates[model_class.UNIQUE_LOOKUP_FIELD]}

        try:
            existing_instance = model_class.objects.get(**unique_field_filter)
            logger.debug("Found existing %s instance id=%s matching remote recurly data",
                         model_class.__name__, existing_instance.pk)
        except model_class.DoesNotExist:
            logger.debug("No %s instance found matching unique field filter '%s', returning new object",
                         model_class.__name__, unique_field_filter)

    else:
        pass  # eg. case of a billing_info not existing locally yet

    if existing_instance:
        # Update fields of existing object (even with None values)
        obj = existing_instance
        for k, v in model_updates.items():
            setattr(obj, k, v)
    else:
        # Create a new model instance
        obj = model_class(**model_updates)

    if presave_callback:
        presave_callback(obj)
    if save:
        obj.save()  # sets primary key if not present

    for (relation, subsinstance_klass) in SUBMODEL_MAPPER.items():

        if not hasattr(model_class, relation):
            continue  # this model doesn't contain such a relation

        is_one_to_one_relation = not relation.endswith("s")  # quick and dirty
        if is_one_to_one_relation:
            def _new_presave_callback(_subobj):
                setattr(obj, relation, _subobj)
        else:
            raise RuntimeError("NOT is_one_to_one_relation case not tested yet")
            # it's a pool of related objects like "subscriptions"...
            def _new_presave_callback(_subobj):
                rels = getattr(obj, relation)
                rels.add(_subobj)

        local_subinstance = getattr(obj, relation, None)

        #logger.debug("LOOOOOOOOKING UP RESOURCE EXTRACT %s %s %s", resource, relation, resource.__dict__)

        try:
            remote_subresource = getattr(resource, relation, None)
        except recurly.errors.NotFoundError:
            remote_subresource = None
        #logger.debug("Remote_resource _elem: %s", remote_resource._elem)

        if remote_subresource:
            # we create or override sub-instance
            subobj = modelify(remote_subresource, subsinstance_klass,
                              existing_instance=local_subinstance,
                              presave_callback=_new_presave_callback)
            setattr(obj, relation, subobj)  # might be a NO-OP here
            if save:
                obj.save()  # just in case
        else:
            assert not remote_subresource
            if local_subinstance:
                local_subinstance.delete()  # delete obsolete instance in DB
                assert getattr(obj, relation) is local_subinstance  # proxy remains
            else:
                pass  # both unexisting, it's OK

    return obj





def update_local_account_data_from_recurly_resource(recurly_account):
    """
    Overrides local Account and BillingInfo fields with remote ones.
    """

    logger.debug("update_local_account_data_from_recurly_resource for %s", recurly_account.account_code)
    account = modelify(recurly_account, Account)

    ## useless account.save()
    ''' NOPE
    # Update billing info from nested account data
    if hasattr(recurly_account, "billing_info"):
        BillingInfo.update_local_data_from_recurly_resource(
            recurly_billing_info=recurly_account.billing_info
        )
    else:
        BillingInfo.update_local_data_from_recurly_resource(account_code=account.account_code)
        '''
    return account



# FIXME - UNUSED ???
def ______update_local_billing_info_data_from_recurly_resource(recurly_billing_info):

    cls = BillingInfo

    logger.debug("BillingInfo.sync: %s", recurly_billing_info)
    billing_info = modelify(recurly_billing_info, cls)

    if hasattr(billing_info, 'account') and not billing_info.account.pk:
        billing_info.account.save(remote=False)
        billing_info.account_id = billing_info.account.pk

    billing_info.save(remote=False)
    return billing_info


def update_local_subscription_data_from_recurly_resource(recurly_subscription):
    """
    Overrides local fields of this Subscription with remote ones.
    """

    ####print("------------------->", recurly_subscription)
    assert isinstance(recurly_subscription, recurly.Subscription)

    logger.debug("update_local_subscription_data_from_recurly_resource for %s", recurly_subscription.uuid)
    subscription = modelify(recurly_subscription, Subscription)

    return subscription


def update_full_local_data_for_account_code(account_code):

    recurly_account = recurly.Account.get(account_code)
    assert isinstance(recurly_account, recurly.Account), recurly_account

    account = update_local_account_data_from_recurly_resource(recurly_account)

    legit_uuids = []
    for recurly_subscription in recurly_account.subscriptions():
        local_subscription = update_local_subscription_data_from_recurly_resource(recurly_subscription)
        local_subscription = sync_local_add_ons_from_recurly_resource(recurly_subscription, local_subscription)
        account.subscriptions.add(local_subscription)  # model linking
        legit_uuids.append(local_subscription.uuid)

    for subscription in account.subscriptions.all():
        if subscription.uuid not in legit_uuids:
            # TODO - issue a warning, it's ABNORMAL that subscriptions disappear in recurly servers!
            subscription.delete()  # remove obsolete subscription

    return account


def set_acquisition_data(account_code, acquisition_params):
    """
    add acquisition data to a remote recurly account
    """
    acquisition_params['account_code'] = account_code
    recurly_account_acquisition = recurly.AccountAcquisition(**acquisition_params)
    collection_path = "{}/{}/acquisition".format(recurly.Account.collection_path, account_code)
    recurly_account_acquisition.collection_path = collection_path
    recurly_account_acquisition.save()


def lookup_plan_add_on(plan_code, add_on_code=None):
    def _serializer_add_on(add_on):
        serialized_add_on_data = {"add_on_code": add_on.add_on_code, "name": add_on.name,
                                  "currencies": add_on.unit_amount_in_cents.currencies}
        return serialized_add_on_data

    def _serializer_plan(plan, add_on_list):
        serialized_plan_data = {
            "plan_duration": plan.plan_interval_length,
            "plan_duration_unit": plan.plan_interval_unit,
            "add_on_list": [_serializer_add_on(add_on) for add_on in add_on_list]
        }
        return serialized_plan_data

    add_on_list = []
    plan = recurly.Plan.get(plan_code)
    if not add_on_code:
        for add_on in plan.add_ons():
            add_on_list.append(add_on)
    else:
        add_on_list.append(plan.get_add_on(add_on_code))

    return _serializer_plan(plan, add_on_list)
