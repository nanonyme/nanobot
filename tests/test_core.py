from twisted.trial import unittest
from twisted.internet import task, defer
from collections import OrderedDict
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
        self.code = code or 200
        self._headers = headers or {"content-type": ("text/html;utf-8",)}

    @property
    def headers(self):
        return self

    def getRawHeaders(self, key):
        return self._headers[key.lower()]

    def collect(self, collector):
        d = defer.Deferred()
        d.callback(None)
        collector(self.data)
        return d

class MockTreq(object):
    def __init__(self, url_map):
        self.url_map = url_map

    def get(self, url, timeout=None, headers={}):
        if url not in self.url_map:
            raise Exception("Wrong URL, got %s, not in %s" % (url, self.url_map))
        data = self.url_map[url]["data"]
        headers = self.url_map[url].get("headers")
        code = self.url_map[url].get("code")
        
        return defer.succeed(MockResponse(data, headers, code))

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
                                             self.miss_cache,
                                             lambda x: self.fail(x),
                                             255)
        return defer.ensureDeferred(message_handler.find_links("foo bar"))

    def testUnsupportedScheme(self):
        message_handler = app.MessageHandler(self.clock, self.hit_cache,
                                             self.miss_cache,
                                             lambda x: self.fail(x),
                                             255)
        return defer.ensureDeferred(message_handler.find_links("gopher://foo/bar#bar"))

    def testForbidden(self):
        msg = "http://foo/bar"
        message_handler = app.MessageHandler(self.clock, self.hit_cache,
                                             self.miss_cache,
                                             lambda x: self.fail(x),
                                             255)
        d = self.step(message_handler, msg, "foo", code=400)
        d.addCallback(self.ensureException)

    def testUnsupportedType(self):
        msg = "http://foo/bar"
        message_handler = app.MessageHandler(self.clock, self.hit_cache,
                                             self.miss_cache,
                                             lambda x: self.fail(x),
                                             255)
        d = self.step(message_handler, msg, "foo",
                      headers={"content-type": ("image/png",)})
        d.addCallback(self.ensureException)

    def testBrokenTypeHeader(self):
        msg = "http://foo/bar"
        message_handler = app.MessageHandler(self.clock, self.hit_cache,
                                             self.miss_cache,
                                             lambda x: self.fail(x),
                                             255)
        d = self.step(message_handler, msg, "foo",
                      headers={"content-type": tuple()})
        d.addCallback(self.ensureException)

    def testMissingTypeHeader(self):
        msg = "http://foo/bar"
        message_handler = app.MessageHandler(self.clock, self.hit_cache,
                                             self.miss_cache,
                                             lambda x: self.fail(x),
                                             255)
        d = self.step(message_handler, msg, "foo",
                      headers={})
        d.addCallback(self.ensureException)

    def ensureException(self, e):
        errors = self.flushLoggedErrors(app.AppException)
        self.assertEqual(len(errors), 1)


    def step(self, handler, url, title, code=None, headers=None):
        self.output = "title: %s" % title
        url_map = {
            url: {
                "code": code,
                "data": self.template.substitute(title=title),
                "headers": headers}
        }
        app.treq = MockTreq(url_map)
        d = defer.ensureDeferred(handler.find_links(url))
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

    def runSequence(self, urls):
        message = " ".join(urls)
        expected_urls = reversed(urls)
        url_map = {
            url: self.urlitem_from_url(url) for url in urls
        }
        app.treq = MockTreq(url_map)
        def callback(title):
            url = urls_left_pop()
            self.assertEqual(title, url_map[url]["title"])
        message_handler = app.MessageHandler(self.clock, self.hit_cache,
                                             self.miss_cache,
                                             callback, 255)
        return defer.ensureDeferred(message_handler.find_links(message))


    def urlitem_from_url(self, url):
        title = title_from_url(url)
        return {
            "title": title,
            "data": self.template.substitute(title=title)
        }
        

def title_from_url(url):
    _, _, title = url.partition("#")
    return title
