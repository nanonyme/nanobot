from twisted.trial import unittest
from twisted.internet import task, defer
import nanobot
import app
import string

class CacheTests(unittest.TestCase):
    def setUp(self):
        self.clock = task.Clock()
        self.cache = app.UrlCache(reactor=self.clock, expiration=60)
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

class IgnorantCache(object):
    def __init__(self):
        pass

    def fetch(self, key):
        pass

    def update(self, key, value):
        pass


class MockResponse(object):
    def __init__(self, data, headers, code=200):
        self.data = data
        self.code = code
        self._headers = headers
    
    @property
    def headers(self):
        return self

    def getRawHeaders(self, key):
        return self._headers[key.lower()]

class MockTreq(object):
    def __init__(self, url, data, headers):
        self.url = url
        self.data = data
        self.headers = headers

    def get(self, url, timeout=None, headers={}):
        if not self.url == url:
            raise Exception("Wrong URL, got %s, expected %s" % (url, self.url))
        return defer.succeed(MockResponse(self.data, self.headers))

    def head(self, url, timeout=None, headers={}):
        if not self.url == url:
            raise Exception("Wrong URL, got %s, expected %s" % (url, self.url))
        return defer.succeed(MockResponse("", self.headers))

    def collect(self, response, callback):
        callback(response.data.decode("utf-8"))

class TestMessageHandler(unittest.TestCase):

    def setUp(self):
        self.clock = task.Clock()        
        self.hit_cache = IgnorantCache()
        self.miss_cache = IgnorantCache()
        self.encoding = "UTF-8"
        self.template = string.Template("""<html>
        <head>
        <title>${title}</title>
        </head>
        <body>Example body</body>
        </html>""")


    def testNoUrl(self):
        message_handler = app.MessageHandler(self.clock, self.hit_cache,
                                             self.miss_cache, "foo bar",
                                             lambda x: self.fail(x),
                                             self.encoding, 255)
        d = next(iter(message_handler), None)
        self.assertIs(d, None, "Should not give any deferreds")


    def step(self, iterator, url, title):
        app.treq = MockTreq(url, self.template.substitute(title=title),
                            {"content-type": ("text/html;utf-8",)})
        d = next(iterator)
        title = "title: %s" % title
        d.addCallback(lambda: self.clock.advance(2))
        return d
        
    def runSequence(self, message, urls, titles):
        for url, title in zip(urls, titles):
            yield self.step(message_handler, url, title)

    def testHttpUrl(self):
        url = "http://meep.com/foo/bar.baz.html#foo"
        m = "foo %s meep" % url
        title = "Foo bar baz"
        output = "title: %s" % title
        def callback(x):
            self.assertEqual(x, output)
            return defer.succeed(None)
        message_handler = app.MessageHandler(self.clock, self.hit_cache,
                                             self.miss_cache, url,
                                             callback,
                                             self.encoding, 255)
        iterator = iter(message_handler)
        self.step(iterator, url, title)
        self.assertRaises(StopIteration, next, iterator)


    
