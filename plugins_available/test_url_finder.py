from twisted.application import service
try:
    import unittest2 as unittest
except ImportError:
    import unittest
import mock
import url_finder

class TestWellDefinedURLs(unittest.TestCase):
    def setUp(self):
        """Mock some stuff up"""
        self.parent = service.MultiService()
        self.parent.delegate = self.collect_delegated_data
        self.testable = url_finder.URLFinder()
        self.parent.addService(self.testable)
        self.user = "foo!bar@baz"
        self.channel = "#testchannel"
        self.instance = mock.Mock()
        self.instance.nickname = "testguy"
        self.data = dict()

    def collect_delegated_data(self, instance, description,
                               user, channel, url, *args, **kwargs):
        self.data = {'description':description, 'url':url}
    
    @unittest.expectedFailure
    def test_url_at_beginning(self):
        message = "http://www.google.fi/webhp?aq=0 and some other text"
        self.testable.privmsg(self.instance, self.user, self.channel,
                              message)
        self.validate_data()

    @unittest.expectedFailure
    def test_url_in_middle(self):
        message = "awe http://www.google.fi/webhp?aq=0 vwer"
        self.testable.privmsg(self.instance, self.user, self.channel,
                              message)
        self.validate_data()
                        
    @unittest.expectedFailure
    def test_url_at_end(self):
        message = "useless crap and finally   http://www.google.fi/webhp?aq=0"
        self.testable.privmsg(self.instance, self.user, self.channel,
                              message)
        self.validate_data()
                

    def validate_data(self):
        self.assertEqual(self.data.get('description', ''), 'google',
                         'description was not google')
        self.assertEqual(self.data.get('url', ''),
                         "http://www.google.fi/webhp?aq=0",
                         "url did not contain the full URL")
        
        
        
