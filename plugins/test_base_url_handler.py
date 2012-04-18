from twisted.application import service
from twisted.trial import unittest
import mock
import base_url_handler

class TestWellDefinedURLs(unittest.TestCase):
    def setUp(self):
        """Mock some stuff up"""
        self.parent = service.MultiService()
        self.parent.dispatch = self.collect_delegated_data
        self.testable = base_url_handler.URLFinder()
        self.testable.setServiceParent(self.parent)
        self.user = "foo!bar@baz"
        self.channel = "#testchannel"
        self.instance = mock.Mock()
        self.instance.nickname = "testguy"
        self.data = dict()

    def collect_delegated_data(self, description, url):
        self.description = description
        self.url = url
        self.validate_data()
    

    def test_http_beginning(self):
        message = "http://www.google.fi/webhp?aq=0 and some other text"
        self.testable.privmsg(message, self.user, self.channel)

    def test_http_middle(self):
        message = "awe http://www.google.fi/webhp?aq=0 vwer"
        self.testable.privmsg(message, self.user, self.channel)

    def test_http_end(self):
        message = "useless crap and finally   http://www.google.fi/webhp?aq=0"
        self.testable.privmsg(message, self.user, self.channel)
                

    def validate_data(self):
        self.assertEqual(self.description, 'handle_url',
                         'description was not google')
        self.assertEqual(self.url, "http://www.google.fi/webhp?aq=0",
                         "url did not contain the full URL")
        
        
        
