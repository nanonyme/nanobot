import http_client
from twisted.trial import unittest
import BeautifulSoup

class TestHTTPClient(unittest.TestCase):
    def setUp(self):
        self.client = http_client.HTTPClient("cache")

    def title_check(self, result, title):
        soup = BeautifulSoup.BeautifulSoup(result)
        self.assertEqual(soup.title.string, title)

    def test_google(self):
        d = self.client.fetch_url("http://www.google.fi")
        d.addCallback(self.title_check, "Google")
        return d

    def test_bad_site(self):
       self.client.limit = 10
       d = self.client.fetch_url("http://phreakocious.net/watchthemfall")
       d.addBoth(self.title_check, "Error, maximum download limit %d" % self.client.limit)
       return d
