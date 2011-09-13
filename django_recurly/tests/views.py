import unittest
import glob
import os.path

from django.test import TestCase

from django_recurly import views
from django_recurly.tests.base import BaseTest, RequestFactory

rf = RequestFactory()

class PushNotificationViewTest(BaseTest):
    
    def test_all(self):
        xml_dir = os.path.abspath(os.path.dirname(__file__)) + "/data/push_notifications/*/*"
        xml_files = glob.glob(xml_dir)
        
        for xml_file in xml_files:
            f = open(xml_file, "r")
            xml = f.read()
            f.close()
            
            request = rf.post("/junk", xml, content_type="text/xml")
            # Quick & dirty parsing of the expected singal name from the file name
            expected_signal = "_".join(xml_file.split("/")[-1].split("_")[:-1])
            
            self.resetSignals()
            views.push_notifications(request)
            self.assertSignal(expected_signal)
        
    
