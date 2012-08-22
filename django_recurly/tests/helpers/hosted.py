# -*- coding: utf-8 -*-

from django.test import TestCase

from django_recurly.helpers import hosted
from django_recurly.tests.base import BaseTest
from django_recurly.models import *


class GetSubscribeUrlTest(BaseTest):
    
    def test_encoding(self):
        expected = "https://dummy_subdomain.recurly.com/subscribe/myplan/mya%C3%A7%C3%A7o+unt/ad%2Fa%C3%A5m?quantity=2&first_name=%C3%85dam&last_name=%C3%87harnock&email=adam@test.com"
        
        self.user.username = u"ad/aåm"
        self.user.first_name = u"Ådam"
        self.user.last_name = u"Çharnock"
        self.user.email = u"adam@test.com"
        
        self.assertEqual(hosted.get_subscribe_url(
            plan_code=u"myplan",
            user=self.user,
            quantity=2,
            account_code=u"myaçço unt"
        ), expected)
    
