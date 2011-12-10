from twisted.application import service
try:
    import unittest2 as unittest
except ImportError:
    import unittest
import mock
import exocet
import twisted.internet

class MockReactor(object):
    def callLater(self, delay, callable, instance,
                  description, user, channel, url):
        self.description = description
        self.url = url

class TestWellDefinedURLs(unittest.TestCase):
    def setUp(self):
        """Mock some stuff up"""
        import sys
        self.reactor = MockReactor()
        import base_url_handler
        base_url_handler.reactor = self.reactor
        self.parent = service.MultiService()
        self.parent.delegate = self.collect_delegated_data
        self.testable = base_url_handler.URLFinder()
        self.testable.setServiceParent(self.parent)
        self.user = "foo!bar@baz"
        self.channel = "#testchannel"
        self.instance = mock.Mock()
        self.instance.nickname = "testguy"
        self.data = dict()

    def collect_delegated_data(self, instance, description,
                               user, channel, url, *args, **kwargs):
        self.data = {'description':description, 'url':url}
    

    def test_http_beginning(self):
        message = "http://www.google.fi/webhp?aq=0 and some other text"
        self.testable.privmsg(self.instance, self.user, self.channel,
                              message)
        self.validate_data()

    def test_http_middle(self):
        message = "awe http://www.google.fi/webhp?aq=0 vwer"
        self.testable.privmsg(self.instance, self.user, self.channel,
                              message)
        self.validate_data()
                        
    def test_http_end(self):
        message = "useless crap and finally   http://www.google.fi/webhp?aq=0"
        self.testable.privmsg(self.instance, self.user, self.channel,
                              message)
        self.validate_data()
                

    def validate_data(self):
        self.assertEqual(self.reactor.description, 'handle_url',
                         'description was not google')
        self.assertEqual(self.reactor.url, "http://www.google.fi/webhp?aq=0",
                         "url did not contain the full URL")
        
        
        
