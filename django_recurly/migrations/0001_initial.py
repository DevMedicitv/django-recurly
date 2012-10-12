# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'Account'
        db.create_table('django_recurly_account', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('created', self.gf('django.db.models.fields.DateTimeField')(default=datetime.datetime.now, blank=True)),
            ('modified', self.gf('django.db.models.fields.DateTimeField')(default=datetime.datetime.now, blank=True)),
            ('user', self.gf('django.db.models.fields.related.ForeignKey')(blank=True, related_name='recurly_account', null=True, on_delete=models.SET_NULL, to=orm['auth.User'])),
            ('account_code', self.gf('django.db.models.fields.CharField')(unique=True, max_length=32)),
            ('username', self.gf('django.db.models.fields.CharField')(max_length=200)),
            ('email', self.gf('django.db.models.fields.CharField')(max_length=100)),
            ('first_name', self.gf('django.db.models.fields.CharField')(max_length=100)),
            ('last_name', self.gf('django.db.models.fields.CharField')(max_length=100)),
            ('company_name', self.gf('django.db.models.fields.CharField')(max_length=100, null=True, blank=True)),
            ('state', self.gf('django.db.models.fields.CharField')(default='active', max_length=20)),
            ('hosted_login_token', self.gf('django.db.models.fields.CharField')(max_length=32, null=True, blank=True)),
            ('created_at', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
        ))
        db.send_create_signal('django_recurly', ['Account'])

        # Adding model 'Subscription'
        db.create_table('django_recurly_subscription', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('account', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['django_recurly.Account'], null=True, blank=True)),
            ('uuid', self.gf('django.db.models.fields.CharField')(unique=True, max_length=40)),
            ('plan_code', self.gf('django.db.models.fields.CharField')(max_length=100)),
            ('plan_version', self.gf('django.db.models.fields.IntegerField')(default=1)),
            ('state', self.gf('django.db.models.fields.CharField')(default='active', max_length=20)),
            ('quantity', self.gf('django.db.models.fields.IntegerField')(default=1)),
            ('unit_amount_in_cents', self.gf('django.db.models.fields.IntegerField')(null=True, blank=True)),
            ('currency', self.gf('django.db.models.fields.CharField')(default='USD', max_length=3)),
            ('activated_at', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
            ('canceled_at', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
            ('expires_at', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
            ('current_period_started_at', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
            ('current_period_ends_at', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
            ('trial_started_at', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
            ('trial_ends_at', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
            ('xml', self.gf('django.db.models.fields.TextField')(null=True, blank=True)),
        ))
        db.send_create_signal('django_recurly', ['Subscription'])

        # Adding model 'Payment'
        db.create_table('django_recurly_payment', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('account', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['django_recurly.Account'], null=True, blank=True)),
            ('transaction_id', self.gf('django.db.models.fields.CharField')(unique=True, max_length=40)),
            ('invoice_id', self.gf('django.db.models.fields.CharField')(max_length=40, null=True, blank=True)),
            ('action', self.gf('django.db.models.fields.CharField')(max_length=10)),
            ('amount_in_cents', self.gf('django.db.models.fields.IntegerField')(null=True, blank=True)),
            ('status', self.gf('django.db.models.fields.CharField')(max_length=10)),
            ('message', self.gf('django.db.models.fields.CharField')(max_length=250)),
            ('created_at', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
            ('xml', self.gf('django.db.models.fields.TextField')(null=True, blank=True)),
        ))
        db.send_create_signal('django_recurly', ['Payment'])

        # Adding model 'Token'
        db.create_table('django_recurly_token', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('created', self.gf('django.db.models.fields.DateTimeField')(default=datetime.datetime.now, blank=True)),
            ('modified', self.gf('django.db.models.fields.DateTimeField')(default=datetime.datetime.now, blank=True)),
            ('account', self.gf('django.db.models.fields.related.ForeignKey')(blank=True, related_name='tokens', null=True, to=orm['django_recurly.Account'])),
            ('token', self.gf('django.db.models.fields.CharField')(unique=True, max_length=40)),
            ('cls', self.gf('django.db.models.fields.CharField')(max_length=12)),
            ('identifier', self.gf('django.db.models.fields.CharField')(max_length=40)),
            ('xml', self.gf('django.db.models.fields.TextField')(null=True, blank=True)),
        ))
        db.send_create_signal('django_recurly', ['Token'])


    def backwards(self, orm):
        # Deleting model 'Account'
        db.delete_table('django_recurly_account')

        # Deleting model 'Subscription'
        db.delete_table('django_recurly_subscription')

        # Deleting model 'Payment'
        db.delete_table('django_recurly_payment')

        # Deleting model 'Token'
        db.delete_table('django_recurly_token')


    models = {
        'auth.group': {
            'Meta': {'object_name': 'Group'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '80'}),
            'permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'})
        },
        'auth.permission': {
            'Meta': {'ordering': "('content_type__app_label', 'content_type__model', 'codename')", 'unique_together': "(('content_type', 'codename'),)", 'object_name': 'Permission'},
            'codename': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['contenttypes.ContentType']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '50'})
        },
        'auth.user': {
            'Meta': {'object_name': 'User'},
            'date_joined': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'email': ('django.db.models.fields.EmailField', [], {'unique': 'True', 'max_length': '75', 'blank': 'True'}),
            'first_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'groups': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Group']", 'symmetrical': 'False', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'is_staff': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_superuser': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_login': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'last_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'password': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'user_permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'}),
            'username': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '200'})
        },
        'contenttypes.contenttype': {
            'Meta': {'ordering': "('name',)", 'unique_together': "(('app_label', 'model'),)", 'object_name': 'ContentType', 'db_table': "'django_content_type'"},
            'app_label': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'model': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'})
        },
        'django_recurly.account': {
            'Meta': {'ordering': "['-id']", 'object_name': 'Account'},
            'account_code': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '32'}),
            'company_name': ('django.db.models.fields.CharField', [], {'max_length': '100', 'null': 'True', 'blank': 'True'}),
            'created': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now', 'blank': 'True'}),
            'created_at': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'email': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'first_name': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'hosted_login_token': ('django.db.models.fields.CharField', [], {'max_length': '32', 'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'last_name': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'modified': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now', 'blank': 'True'}),
            'state': ('django.db.models.fields.CharField', [], {'default': "'active'", 'max_length': '20'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'recurly_account'", 'null': 'True', 'on_delete': 'models.SET_NULL', 'to': "orm['auth.User']"}),
            'username': ('django.db.models.fields.CharField', [], {'max_length': '200'})
        },
        'django_recurly.payment': {
            'Meta': {'ordering': "['-id']", 'object_name': 'Payment'},
            'account': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['django_recurly.Account']", 'null': 'True', 'blank': 'True'}),
            'action': ('django.db.models.fields.CharField', [], {'max_length': '10'}),
            'amount_in_cents': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'created_at': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'invoice_id': ('django.db.models.fields.CharField', [], {'max_length': '40', 'null': 'True', 'blank': 'True'}),
            'message': ('django.db.models.fields.CharField', [], {'max_length': '250'}),
            'status': ('django.db.models.fields.CharField', [], {'max_length': '10'}),
            'transaction_id': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '40'}),
            'xml': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'})
        },
        'django_recurly.subscription': {
            'Meta': {'ordering': "['-id']", 'object_name': 'Subscription'},
            'account': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['django_recurly.Account']", 'null': 'True', 'blank': 'True'}),
            'activated_at': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'canceled_at': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'currency': ('django.db.models.fields.CharField', [], {'default': "'USD'", 'max_length': '3'}),
            'current_period_ends_at': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'current_period_started_at': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'expires_at': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'plan_code': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'plan_version': ('django.db.models.fields.IntegerField', [], {'default': '1'}),
            'quantity': ('django.db.models.fields.IntegerField', [], {'default': '1'}),
            'state': ('django.db.models.fields.CharField', [], {'default': "'active'", 'max_length': '20'}),
            'trial_ends_at': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'trial_started_at': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'unit_amount_in_cents': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'uuid': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '40'}),
            'xml': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'})
        },
        'django_recurly.token': {
            'Meta': {'object_name': 'Token'},
            'account': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'tokens'", 'null': 'True', 'to': "orm['django_recurly.Account']"}),
            'cls': ('django.db.models.fields.CharField', [], {'max_length': '12'}),
            'created': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'identifier': ('django.db.models.fields.CharField', [], {'max_length': '40'}),
            'modified': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now', 'blank': 'True'}),
            'token': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '40'}),
            'xml': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'})
        }
    }

    complete_apps = ['django_recurly']