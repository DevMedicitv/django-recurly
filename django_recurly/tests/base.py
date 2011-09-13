import weakref

from django.test import TestCase
from django.test.client import Client
from django.conf import settings
from django.core.handlers.wsgi import WSGIRequest

from django_recurly import signals

class BaseTest(TestCase):
    def setUp(self):
        super(BaseTest, self).setUp()
        self._signals = set([])
        self._setUpSignals()
    
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
    

class RequestFactory(Client):
    # Used to generate request objects.
    def request(self, **request):
        environ = {
            'HTTP_COOKIE': self.cookies,
            'PATH_INFO': '/',
            'QUERY_STRING': '',
            'REQUEST_METHOD': 'GET',
            'SCRIPT_NAME': '',
            'SERVER_NAME': 'testserver',
            'SERVER_PORT': 80,
            'SERVER_PROTOCOL': 'HTTP/1.1',
        }
        environ.update(self.defaults)
        environ.update(request)
        return WSGIRequest(environ)
    
