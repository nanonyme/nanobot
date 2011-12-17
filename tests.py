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

    def length_check(self, result, length):
        self.assertEqual(int(result.getErrorMessage()), length)

    def test_bad_site(self):
       self.client.limit = 10
       d = self.client.fetch_url("http://phreakocious.net/watchthemfall")
       d.addBoth(self.length_check, 10)
       return d
