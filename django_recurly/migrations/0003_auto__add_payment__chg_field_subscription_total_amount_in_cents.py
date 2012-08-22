# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Adding model 'Payment'
        db.create_table('django_recurly_payment', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('account', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['django_recurly.Account'], null=True, blank=True)),
            ('transaction_id', self.gf('django.db.models.fields.CharField')(max_length=40)),
            ('invoice_id', self.gf('django.db.models.fields.CharField')(max_length=40, null=True, blank=True)),
            ('action', self.gf('django.db.models.fields.CharField')(max_length=10)),
            ('date', self.gf('timezones.fields.LocalizedDateTimeField')(null=True, blank=True)),
            ('amount_in_cents', self.gf('django.db.models.fields.IntegerField')(null=True, blank=True)),
            ('status', self.gf('django.db.models.fields.CharField')(max_length=10)),
            ('message', self.gf('django.db.models.fields.CharField')(max_length=250)),
        ))
        db.send_create_signal('django_recurly', ['Payment'])

        # Changing field 'Subscription.total_amount_in_cents'
        db.alter_column('django_recurly_subscription', 'total_amount_in_cents', self.gf('django.db.models.fields.IntegerField')(null=True))


    def backwards(self, orm):
        
        # Deleting model 'Payment'
        db.delete_table('django_recurly_payment')

        # Changing field 'Subscription.total_amount_in_cents'
        db.alter_column('django_recurly_subscription', 'total_amount_in_cents', self.gf('django.db.models.fields.DecimalField')(null=True, max_digits=8, decimal_places=2))


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
            'email': ('django.db.models.fields.EmailField', [], {'max_length': '75', 'blank': 'True'}),
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
            'username': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '30'})
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
            'canceled': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'company_name': ('django.db.models.fields.CharField', [], {'max_length': '100', 'null': 'True', 'blank': 'True'}),
            'created_at': ('timezones.fields.LocalizedDateTimeField', [], {'default': 'datetime.datetime(2011, 10, 5, 22, 11, 15, 437027)'}),
            'email': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'first_name': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'hosted_login_token': ('django.db.models.fields.CharField', [], {'max_length': '32', 'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'last_name': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'recurly_account'", 'null': 'True', 'to': "orm['auth.User']"})
        },
        'django_recurly.payment': {
            'Meta': {'ordering': "['-id']", 'object_name': 'Payment'},
            'account': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['django_recurly.Account']", 'null': 'True', 'blank': 'True'}),
            'action': ('django.db.models.fields.CharField', [], {'max_length': '10'}),
            'amount_in_cents': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'date': ('timezones.fields.LocalizedDateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'invoice_id': ('django.db.models.fields.CharField', [], {'max_length': '40', 'null': 'True', 'blank': 'True'}),
            'message': ('django.db.models.fields.CharField', [], {'max_length': '250'}),
            'status': ('django.db.models.fields.CharField', [], {'max_length': '10'}),
            'transaction_id': ('django.db.models.fields.CharField', [], {'max_length': '40'})
        },
        'django_recurly.subscription': {
            'Meta': {'ordering': "['-id']", 'object_name': 'Subscription'},
            'account': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['django_recurly.Account']"}),
            'activated_at': ('timezones.fields.LocalizedDateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'canceled_at': ('timezones.fields.LocalizedDateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'current_period_ends_at': ('timezones.fields.LocalizedDateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'current_period_started_at': ('timezones.fields.LocalizedDateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'expires_at': ('timezones.fields.LocalizedDateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'plan_code': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'plan_version': ('django.db.models.fields.IntegerField', [], {'default': '1'}),
            'quantity': ('django.db.models.fields.IntegerField', [], {'default': '1'}),
            'state': ('django.db.models.fields.CharField', [], {'default': "'active'", 'max_length': '20'}),
            'super_subscription': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'total_amount_in_cents': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'trial_ends_at': ('timezones.fields.LocalizedDateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'trial_started_at': ('timezones.fields.LocalizedDateTimeField', [], {'null': 'True', 'blank': 'True'})
        }
    }

    complete_apps = ['django_recurly']
