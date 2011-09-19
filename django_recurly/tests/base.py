import weakref
import glob
import os.path
import base64

from django.test import TestCase
from django.test.client import Client
from django.conf import settings
from django.core.handlers.wsgi import WSGIRequest

from django_recurly import signals
from django_recurly.models import *

class BaseTest(TestCase):
    def setUp(self):
        super(BaseTest, self).setUp()
        self._signals = set([])
        self._setUpSignals()
        self.setUpData()
        
        self.user = User.objects.create(username="verena", email="moo@cow.com")
    
    def tearDown(self):
        super(BaseTest, self).tearDown()
        self._tearDownSignals()
    
    def _setUpSignals(self):
        def reg(k, signal):
            signal.connect(lambda sender, **kwargs: self._receiveSignal(k, signal, sender, **kwargs), dispatch_uid="unittest_uid", weak=False)
        
        for k in signals.__dict__:
            signal = signals.__dict__[k]
            if hasattr(signal, "providing_args"):
                reg(k, signal)
    
    def _tearDownSignals(self):
        for k in signals.__dict__:
            signal = signals.__dict__[k]
            if hasattr(signal, "providing_args"):
                signal.disconnect(dispatch_uid="unittest_uid", weak=False)
    
    def _receiveSignal(self, signal_key, signal_object, sender, **kwargs):
        self._signals.add(signal_key)
    
    def assertSignal(self, signal):
        self.assertTrue(signal in self._signals, "Signal '%s' was never sent" % signal)
    
    def resetSignals(self):
        self._signals = set([])
    
    def assertNoSignal(self, signal):
        self.assertFalse(signal in self._signals, "Signal '%s' was sent" % signal)
    
    def setUpData(self):
        xml_dir = os.path.abspath(os.path.dirname(__file__)) + "/data/push_notifications/*/*"
        xml_files = glob.glob(xml_dir)
        
        self.push_notifications = {}
        for xml_file in xml_files:
            f = open(xml_file, "r")
            xml = f.read()
            f.close()
            
            name = xml_file.split("/")[-1]
            
            self.push_notifications[name] = xml
    
    def parse_xml(self, xml):
        from django_recurly.client import get_client
        
        client = get_client()
        client.parse_notification(xml)
        
        return client.response
    

class RequestFactory(Client):
    # Used to generate request objects.
    def request(self, **request):
        credentials = base64.encodestring(settings.RECURLY_HTTP_AUTHENTICATION).strip()
        auth_string = 'Basic %s' % credentials
        
        environ = {
            'HTTP_COOKIE': self.cookies,
            'PATH_INFO': '/',
            'QUERY_STRING': '',
            'REQUEST_METHOD': 'GET',
            'SCRIPT_NAME': '',
            'SERVER_NAME': 'testserver',
            'SERVER_PORT': 80,
            'SERVER_PROTOCOL': 'HTTP/1.1',
            'HTTP_AUTHORIZATION': auth_string,
        }
        environ.update(self.defaults)
        environ.update(request)
        return WSGIRequest(environ)
    
