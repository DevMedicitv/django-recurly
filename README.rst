DJANGO RECURLY
#####################

Django-recurly provides a layer between django and the official recurly API client.

- django SQL models mirroring those of recurly (Account, Subscription Billing Info...)
- two-way synchronisation of data, via model.save() for the django->recurly way, and via recurly webhooks (notifications) for the recurly->django way
- django management command to force a global refresh of django model instances, overriding them with the current state of  recurly data
- django helpers to use recurly-hosted pages and recurly.js



REFERENCES
================

Doc of the recurly API : https://dev.recurly.com/docs/

List of webhooks : https://dev.recurly.com/page/webhooks

Python client instructions : https://dev.recurly.com/page/python

Python client repository : https://github.com/recurly/recurly-client-python



INSTALL
=============

Just use "pip install" as usual.

Or to install from a local checkout: `pip install -e path/to/django-recurly/ -U`



TESTS
===========

Launch from inside the repo root folder:

$ pytest -vl


