from twisted.trial import unittest
from twisted.internet import task, defer
from collections import OrderedDict
import nanobot
import app
import string
import twisted.internet.base
from plugins.title_plugin import UrlCache, MessageHandler, AppException
twisted.internet.base.DelayedCall.debug = True

class CacheTests(unittest.TestCase):
    def setUp(self):
        self.clock = task.Clock()
        self.cache = UrlCache(reactor=self.clock, expiration=60)
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
        if headers is None:
            self._headers = {"content-type": ("text/html;utf-8",)}
        else:
            self._headers = headers

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


def patch_handler(handler, mock_treq):

    original_handler_class = handler._URL_HANDLER_CLASS

    def make_handler(*args, **kwargs):
        url_handler = original_handler_class(*args, **kwargs)

        async def get_url(url):
            return await mock_treq.get(url, timeout=url_handler.TIMEOUT, headers=url_handler.headers)

        url_handler.get_url = get_url

        return url_handler

    handler._URL_HANDLER_CLASS = make_handler


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
        message_handler = MessageHandler(self.clock, self.hit_cache,
                                             self.miss_cache,
                                             lambda x: self.fail(x),
                                             255)
        return self.step(message_handler, "foo bar")

    def testUnsupportedScheme(self):
        message_handler = MessageHandler(self.clock, self.hit_cache,
                                             self.miss_cache,
                                             lambda x: self.fail(x),
                                             255)
        return self.step(message_handler, "gopher://foo/bar#bar")


    def testForbidden(self):
        msg = "http://foo/bar"
        message_handler = MessageHandler(self.clock, self.hit_cache,
                                             self.miss_cache,
                                             lambda x: self.fail(x),
                                             255)
        d = self.step(message_handler, msg, "foo", code=400)
        d.addCallback(self.ensureException)
        return d

    def testUnsupportedType(self):
        msg = "http://foo/bar"
        message_handler = MessageHandler(self.clock, self.hit_cache,
                                             self.miss_cache,
                                             lambda x: self.fail(x),
                                             255)
        d = self.step(message_handler, msg, "foo",
                      headers={"content-type": ("image/png",)})
        d.addCallback(self.ensureException)
        return d

    def testBrokenTypeHeader(self):
        msg = "http://foo/bar"
        message_handler = MessageHandler(self.clock, self.hit_cache,
                                             self.miss_cache,
                                             lambda x: self.fail(x),
                                             255)
        d = self.step(message_handler, msg, "foo",
                      headers={"content-type": tuple()})
        d.addCallback(self.ensureException)
        return d

    def testMissingTypeHeader(self):
        msg = "http://foo/bar"
        message_handler = MessageHandler(self.clock, self.hit_cache,
                                             self.miss_cache,
                                             lambda x: self.fail(x),
                                             255)
        d = self.step(message_handler, msg, "foo",
                      headers={})
        d.addCallback(self.ensureException)
        return d

    def ensureException(self, e):
        errors = self.flushLoggedErrors(AppException)
        self.assertEqual(len(errors), 1)


    def step(self, handler, url, title="", code=None, headers=None):
        self.output = "title: %s" % title
        url_map = {
            url: {
                "code": code,
                "data": self.template.substitute(title=title),
                "headers": headers}
        }
        patch_handler(handler, MockTreq(url_map))
        d = defer.ensureDeferred(handler.find_links(url))
        d.addCallback(lambda _: self.clock.advance(2))
        return d
        
    def testHttpUrl(self):
        return self.runSequence(["http://meep.com/foo/bar.baz.html#foo"])
        
    def testMultipleUrls(self):
        return self.runSequence(["http://meep.com/foo/bar.baz.html#foo",
                                 "http://meep.com/foo/bar.baz.html#bar"])

    def testHttpAndHttps(self):
        return self.runSequence(["http://meep.com/foo/bar.baz.html#foo",
                                 "https://meep.com/foo/bar.baz.html#bar"])

    def runSequence(self, urls):
        message = " ".join(urls)
        expected_urls = list(reversed(urls))
        url_map = {
            url: self.urlitem_from_url(url) for url in urls
        }
        def callback(title):
            url = expected_urls.pop()
            expected_title = url_map[url]["title"]
            self.assertEqual(title,  f"title: {expected_title}")
            self.clock.advance(2)
            return defer.succeed(None)
            
        message_handler = MessageHandler(self.clock, self.hit_cache,
                                             self.miss_cache,
                                             callback, 255)
        patch_handler(message_handler, MockTreq(url_map))
        d = defer.ensureDeferred(message_handler.find_links(message))
        d.addCallback(lambda _: self.clock.advance(2))


    def urlitem_from_url(self, url):
        title = title_from_url(url)
        return {
            "title": title,
            "data": self.template.substitute(title=title)
        }
        

def title_from_url(url):
    _, _, title = url.partition("#")
    return title
