# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Adding model 'Account'
        db.create_table('django_recurly_account', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('account_code', self.gf('django.db.models.fields.CharField')(unique=True, max_length=32)),
            ('user', self.gf('django.db.models.fields.related.ForeignKey')(related_name='recurly_account', to=orm['auth.User'])),
            ('created_at', self.gf('timezones.fields.LocalizedDateTimeField')(default=datetime.datetime(2011, 10, 4, 10, 8, 10, 230744))),
            ('email', self.gf('django.db.models.fields.CharField')(max_length=100)),
            ('first_name', self.gf('django.db.models.fields.CharField')(max_length=100)),
            ('last_name', self.gf('django.db.models.fields.CharField')(max_length=100)),
            ('company_name', self.gf('django.db.models.fields.CharField')(max_length=100, null=True, blank=True)),
            ('canceled', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('hosted_login_token', self.gf('django.db.models.fields.CharField')(max_length=32, null=True, blank=True)),
        ))
        db.send_create_signal('django_recurly', ['Account'])

        # Adding model 'Subscription'
        db.create_table('django_recurly_subscription', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('account', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['django_recurly.Account'])),
            ('plan_code', self.gf('django.db.models.fields.CharField')(max_length=100)),
            ('plan_version', self.gf('django.db.models.fields.IntegerField')(default=1)),
            ('state', self.gf('django.db.models.fields.CharField')(default='active', max_length=20)),
            ('quantity', self.gf('django.db.models.fields.IntegerField')(default=1)),
            ('total_amount_in_cents', self.gf('django.db.models.fields.DecimalField')(null=True, max_digits=8, decimal_places=2, blank=True)),
            ('activated_at', self.gf('timezones.fields.LocalizedDateTimeField')(null=True, blank=True)),
            ('canceled_at', self.gf('timezones.fields.LocalizedDateTimeField')(null=True, blank=True)),
            ('expires_at', self.gf('timezones.fields.LocalizedDateTimeField')(null=True, blank=True)),
            ('current_period_started_at', self.gf('timezones.fields.LocalizedDateTimeField')(null=True, blank=True)),
            ('current_period_ends_at', self.gf('timezones.fields.LocalizedDateTimeField')(null=True, blank=True)),
            ('trial_started_at', self.gf('timezones.fields.LocalizedDateTimeField')(null=True, blank=True)),
            ('trial_ends_at', self.gf('timezones.fields.LocalizedDateTimeField')(null=True, blank=True)),
            ('super_subscription', self.gf('django.db.models.fields.BooleanField')(default=False)),
        ))
        db.send_create_signal('django_recurly', ['Subscription'])


    def backwards(self, orm):
        
        # Deleting model 'Account'
        db.delete_table('django_recurly_account')

        # Deleting model 'Subscription'
        db.delete_table('django_recurly_subscription')


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
            'created_at': ('timezones.fields.LocalizedDateTimeField', [], {'default': 'datetime.datetime(2011, 10, 4, 10, 8, 10, 230744)'}),
            'email': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'first_name': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'hosted_login_token': ('django.db.models.fields.CharField', [], {'max_length': '32', 'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'last_name': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'recurly_account'", 'to': "orm['auth.User']"})
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
            'total_amount_in_cents': ('django.db.models.fields.DecimalField', [], {'null': 'True', 'max_digits': '8', 'decimal_places': '2', 'blank': 'True'}),
            'trial_ends_at': ('timezones.fields.LocalizedDateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'trial_started_at': ('timezones.fields.LocalizedDateTimeField', [], {'null': 'True', 'blank': 'True'})
        }
    }

    complete_apps = ['django_recurly']
