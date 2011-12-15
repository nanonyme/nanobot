import nanobot
import http_client
import unittest
from twisted.internet import defer, reactor
import BeautifulSoup

class ResultCollector(object):
    def __init__(self):
        self.content = None

    def __call__(self, content):
        self.content = content
        reactor.stop()


class TestHTTPClient(unittest.TestCase):
    def setUp(self):
        self.client = http_client.HTTPClient("cache")
        self.collector = ResultCollector()

    def test_google(self):
        d = self.client.fetch_url("http://www.google.fi")
        d.addBoth(self.collector)
        reactor.run()
        soup = BeautifulSoup.BeautifulSoup(self.collector.content)
        self.assertEqual(str(soup.title).strip(), "<title>Google</title>")
