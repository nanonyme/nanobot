from twisted.trial import unittest
from twisted.internet import task
import nanobot

class CacheTests(unittest.TestCase):
    def setUp(self):
        self.clock = task.Clock()
        self.cache = nanobot.UrlCache(reactor=self.clock, expiration=60)
        self.cache.enable()

    def tearDown(self):
        self.cache.disable()

    def testGetNotExpired(self):
        self.cache.update("foo", "bar")
        self.assertEquals(self.cache.fetch("foo"),
                          "bar", "Expected cache to have 'foo' for 'bar'")

    def testGetExpired(self):
        self.cache.update("foo", "bar")
        self.assertEquals(self.cache.fetch("foo"),
                          "bar", "Expected cache to have 'foo' for 'bar'")
        self.clock.advance(60)
        value = self.cache.fetch("foo")
        self.assertIs(value, None,
                      "Cache had '%s' for entry 'foo'" % value)

class TestNanoBotProtocol(unittest.TestCase):
    def testNoUrl(self):
        self.fail("not implemented")

    def testHttpUrl(self):
        self.fail("not implemented")

    def testHttpsUrl(self):
        self.fail("not implemented")

    def testMultipleUrls(self):
        self.fail("not implemented")
