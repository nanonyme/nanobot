from twisted.trial import unittest
from twisted.internet import task
from nanobot import UrlCache

class CacheTests(unittest.TestCase):
    def setUp(self):
        self.clock = task.Clock()
        self.cache = UrlCache(reactor=self.clock, expiration=60)
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
