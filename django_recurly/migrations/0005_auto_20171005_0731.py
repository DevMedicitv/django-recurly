# -*- coding: utf-8 -*-
# Generated by Django 1.9.2 on 2017-10-05 07:31
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('django_recurly', '0004_auto_20171004_1612'),
    ]

    operations = [
        migrations.AlterField(
            model_name='billinginfo',
            name='address1',
            field=models.CharField(blank=True, default='', max_length=200),
        ),
        migrations.AlterField(
            model_name='billinginfo',
            name='address2',
            field=models.CharField(blank=True, default='', max_length=200),
        ),
        migrations.AlterField(
            model_name='billinginfo',
            name='card_type',
            field=models.CharField(blank=True, default='', max_length=50),
        ),
        migrations.AlterField(
            model_name='billinginfo',
            name='city',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
        migrations.AlterField(
            model_name='billinginfo',
            name='company',
            field=models.CharField(blank=True, default='', max_length=50),
        ),
        migrations.AlterField(
            model_name='billinginfo',
            name='country',
            field=models.CharField(blank=True, default='', max_length=2),
        ),
        migrations.AlterField(
            model_name='billinginfo',
            name='first_six',
            field=models.IntegerField(blank=True, default=''),
        ),
        migrations.AlterField(
            model_name='billinginfo',
            name='ip_address_country',
            field=models.CharField(blank=True, default='', max_length=2),
        ),
        migrations.AlterField(
            model_name='billinginfo',
            name='last_four',
            field=models.IntegerField(blank=True, default=''),
        ),
        migrations.AlterField(
            model_name='billinginfo',
            name='month',
            field=models.IntegerField(blank=True, default=''),
        ),
        migrations.AlterField(
            model_name='billinginfo',
            name='paypal_billing_agreement_id',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
        migrations.AlterField(
            model_name='billinginfo',
            name='phone',
            field=models.CharField(blank=True, default='', max_length=50),
        ),
        migrations.AlterField(
            model_name='billinginfo',
            name='state',
            field=models.CharField(blank=True, default='', max_length=50),
        ),
        migrations.AlterField(
            model_name='billinginfo',
            name='type',
            field=models.CharField(blank=True, choices=[('credit_card', 'Credit Card'), ('paypal', 'PayPal')], default='', max_length=50),
        ),
        migrations.AlterField(
            model_name='billinginfo',
            name='vat_number',
            field=models.CharField(blank=True, default='', max_length=16),
        ),
        migrations.AlterField(
            model_name='billinginfo',
            name='year',
            field=models.IntegerField(blank=True, default=''),
        ),
        migrations.AlterField(
            model_name='billinginfo',
            name='zip',
            field=models.CharField(blank=True, default='', max_length=50),
        ),
    ]