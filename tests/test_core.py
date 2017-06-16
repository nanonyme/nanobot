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

    def testGetReaperNotRun(self):
        self.cache.update("foo", "bar")
        self.assertEquals(self.cache.fetch("foo"),
                          "bar", "Expected cache to have 'foo' for 'bar'")

    def testReaperExpiresItem(self):
        self.cache.update("foo", "bar")
        self.assertEquals(self.cache.fetch("foo"),
                          "bar", "Expected cache to have 'foo' for 'bar'")
        self.clock.advance(60)
        value = self.cache.fetch("foo")
        self.assertIs(value, None,
                      "Cache had '%s' for entry 'foo'" % value)

    def testReaperLeavesItem(self):
        self.clock.advance(59)
        self.cache.update("foo", "bar")
        self.assertEquals(self.cache.fetch("foo"),
                          "bar", "Expected cache to have 'foo' for 'bar'")
        self.clock.advance(1)
        self.cache.update("foo", "bar")
        self.assertEquals(self.cache.fetch("foo"),
                          "bar", "Expected cache to have 'foo' for 'bar'")

class IgnorantCache(object):
    def __init__(self):
        pass

    def fetch(self, key):
        pass

    def update(self, key, value):
        pass


class MockResponse(object):
    def __init__(self, data, headers, code):
        self.data = data
        self.code = code
        self._headers = headers
    
    @property
    def headers(self):
        return self

    def getRawHeaders(self, key):
        return self._headers[key.lower()]

class MockTreq(object):
    def __init__(self, url, data, headers, code=None):
        self.url = url
        self.data = data
        self.headers = headers
        self.code = code or 200

    def get(self, url, timeout=None, headers={}):
        if not self.url == url:
            raise Exception("Wrong URL, got %s, expected %s" % (url, self.url))
        return defer.succeed(MockResponse(self.data, self.headers,
                                          code=self.code))

    def head(self, url, timeout=None, headers={}):
        if not self.url == url:
            raise Exception("Wrong URL, got %s, expected %s" % (url, self.url))
        return defer.succeed(MockResponse("", self.headers, code=self.code))

    def collect(self, response, callback):
        callback(response.data)

class TestMessageHandler(unittest.TestCase):

    def setUp(self):
        self.clock = task.Clock()        
        self.hit_cache = IgnorantCache()
        self.miss_cache = IgnorantCache()
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
                                             255)
        d = next(iter(message_handler), None)
        self.assertIs(d, None, "Should not give any deferreds")

    def testUnsupportedScheme(self):
        message_handler = app.MessageHandler(self.clock, self.hit_cache,
                                             self.miss_cache, "gopher://foo/bar#baz",
                                             lambda x: self.fail(x),
                                             255)
        d = next(iter(message_handler), None)
        self.assertIs(d, None, "Should not give any deferreds")

    def testForbidden(self):
        msg = "http://foo/bar"
        message_handler = app.MessageHandler(self.clock, self.hit_cache,
                                             self.miss_cache, msg,
                                             lambda x: self.fail(x),
                                             255)
        iterator = iter(message_handler)
        d = self.step(iterator, msg, "foo", code=400)
        d.addCallback(self.ensureException)

    def testUnsupportedType(self):
        msg = "http://foo/bar"
        message_handler = app.MessageHandler(self.clock, self.hit_cache,
                                             self.miss_cache, msg,
                                             lambda x: self.fail(x),
                                             255)
        iterator = iter(message_handler)
        d = self.step(iterator, msg, "foo",
                      headers={"content-type": ("image/png",)})
        d.addCallback(self.ensureException)

    def testBrokenTypeHeader(self):
        msg = "http://foo/bar"
        message_handler = app.MessageHandler(self.clock, self.hit_cache,
                                             self.miss_cache, msg,
                                             lambda x: self.fail(x),
                                             255)
        iterator = iter(message_handler)
        d = self.step(iterator, msg, "foo",
                      headers={"content-type": tuple()})
        d.addCallback(self.ensureException)

    def testMissingTypeHeader(self):
        msg = "http://foo/bar"
        message_handler = app.MessageHandler(self.clock, self.hit_cache,
                                             self.miss_cache, msg,
                                             lambda x: self.fail(x),
                                             255)
        iterator = iter(message_handler)
        d = self.step(iterator, msg, "foo",
                      headers={})
        d.addCallback(self.ensureException)

    def ensureException(self, e):
        errors = self.flushLoggedErrors(app.AppException)
        self.assertEqual(len(errors), 1)


    def step(self, iterator, url, title, code=None, headers=None):
        if headers is None:
            headers = {"content-type": ("text/html;utf-8",)}
        self.output = "title: %s" % title
        app.treq = MockTreq(url, self.template.substitute(title=title),
                            headers=headers, code=code)
        d = next(iterator)
        title = "title: %s" % title
        d.addCallback(lambda e: self.clock.advance(2))
        return d
        
    def testHttpUrl(self):
        self.runSequence(["http://meep.com/foo/bar.baz.html#foo"])

    def testMultipleUrls(self):
        self.runSequence(["http://meep.com/foo/bar.baz.html#foo",
                          "http://meep.com/foo/bar.baz.html#bar"])

    def testHttpAndHttps(self):
        self.runSequence(["http://meep.com/foo/bar.baz.html#foo",
                          "https://meep.com/foo/bar.baz.html#bar"])

    def callback(self, x):
        self.assertEqual(x, self.output)
        return defer.succeed(None)

    def runSequence(self, urls):
        message_handler = app.MessageHandler(self.clock, self.hit_cache,
                                             self.miss_cache, " ".join(urls),
                                             self.callback,
                                             255)
        iterator = iter(message_handler)
        d = defer.succeed(None)
        for url in urls:
            _, _, title = url.partition("#")
            d.addCallback(lambda _:self.step(iterator, url, title))
        d.addCallback(lambda _: self.assertRaises(StopIteration, next, iterator))


    
