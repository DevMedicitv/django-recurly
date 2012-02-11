#!/usr/bin/env python

from setuptools import setup, find_packages
from django_recurly import __version__

setup(
    name='django-recurly',
    license='BSD',
    packages=find_packages(),
    version=__version__,
    
    install_requires=[
        "iso8601",
        "django-timezones",
    ]
)
