#!/usr/bin/env python

from setuptools import setup, find_packages
from django_recurly import __version__

setup(
    name='django-recurly',
    license='BSD',
    packages=find_packages(),
    version=__version__,
    url="https://github.com/adamcharnock/django-recurly",
    author="Adam Charnock",
    author_email="adam@playnice.ly",
    description="Django integration for Recurly, a subscription billing service.",
    
    install_requires=[
        "iso8601",
        "django-timezones",
    ]
)
