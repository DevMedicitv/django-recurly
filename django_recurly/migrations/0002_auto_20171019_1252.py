# -*- coding: utf-8 -*-
# Generated by Django 1.9.2 on 2017-10-19 12:52
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('django_recurly', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='giftcardmemo',
            name='redemption_code',
            field=models.CharField(max_length=50, null=True, unique=True),
        ),
        migrations.AddField(
            model_name='giftcardmemo',
            name='redemption_date',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
