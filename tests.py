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
    def __init__(self, data, headers):
        self.data = data
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

    def get(self, url, timeout=None):
        if not self.url == url:
            raise Exception("Wrong URL, got %s, expected %s" % (url, self.url))
        return defer.succeed(self.data)

    def head(self, url, timeout=None):
        if not self.url == url:
            raise Exception("Wrong URL, got %s, expected %s" % (url, self.url))
        return defer.succeed(MockResponse("", self.headers))

    def collect(self, data, callback):
        callback(data)

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
                                             self.fail, self.encoding, 255)
        d = next(iter(message_handler), None)
        self.assertIs(d, None, "Should not give any deferreds")


    def step(self, iterator, url, title):
        app.treq = MockTreq(url, self.template.substitute(title=title),
                            {"content-type": ("text/html;utf-8",)})
        d = next(iterator)
        self.title = "title: %s" % title
        yield d
        d = next(iterator)
        yield d
        d = next(iterator)
        self.clock.advance(2)
        yield d
        
    def checkTitle(self, title):
        self.assertEqual(self.title, title)


    def run_sequence(self, message, urls, titles):
        message_handler = app.MessageHandler(self.clock, self.hit_cache,
                                             self.miss_cache, message,
                                             self.checkTitle, self.encoding, 255)
        iterator = iter(message_handler)
        for url, title in zip(urls, titles):
            for d in self.step(iterator, url, title):
                yield d
        self.assertRaises(StopIteration, next, iterator)

    def testHttpUrl(self):
        url = "http://meep.com/foo/bar.baz.html#foo"
        m = "foo %s meep" % url
        title = "Foo bar baz"
        return task.coiterate(iter(self.run_sequence("foo %s bar" % url,
                                                     (url,), (title,))))



    
