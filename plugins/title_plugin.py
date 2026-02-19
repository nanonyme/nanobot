# -*- coding: utf-8 -*-
"""
Title fetcher plugin for nanobot.

Fetches and announces the HTML title of URLs posted in IRC channels.
"""
import re
import codecs
import ipaddress
import lxml.html
import Levenshtein
import treq
from urllib import parse as urlparse

from twisted.internet import task, defer
from twisted.logger import Logger

from plugin import Plugin

log = Logger()


class AppException(Exception):
    pass


BLOCKLIST = [
    ipaddress.IPv4Network('127.0.0.0/8'),
    ipaddress.IPv4Network('192.168.0.0/16'),
    ipaddress.IPv4Network('10.0.0.0/8'),
    ipaddress.IPv4Network('172.16.0.0/12'),
    ipaddress.IPv6Network('::1'),
    ipaddress.IPv6Network('fe80::/10'),
]


def acceptable_netloc(hostname):
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        if hostname == "localhost":
            return False
        else:
            return True
    else:
        for network in BLOCKLIST:
            if address in network:
                return False
        else:
            return True


class UrlHandler(object):

    TIMEOUT = 30

    def __init__(self, max_body, parser_class,
                 accepted_mimes=("text/html",),
                 headers={"Accept-Language": "en-US",
                          "User-Agent": ("nanobot title fetching, contacts to"
                                         "http://github.com/nanonyme/nanobot")
                          }):
        self.max_body = max_body
        self.bytes = 0
        self.parser_class = parser_class
        self.parser = None
        self.accepted_mimes = accepted_mimes
        self.headers = headers

    def feed(self, data):
        if self.bytes < self.max_body:
            if len(data) > self.max_body - self.bytes:
                data = data[:self.max_body - self.bytes]
            data_len = len(data)
            self.bytes += data_len
            self.parser.feed(data)
        else:
            self.connection.cancel()

    async def handle_response(self, response):
        if response.code != 200:
            raise AppException(f"Response code {response.code}")
        try:
            headers = response.headers.getRawHeaders("Content-Type")
        except KeyError:
            raise AppException("No Content-Type")
        if not headers:
            raise AppException("Empty Content-Type")
        else:
            header = headers[0]
            log.info(f"Header line {header}")
            mime, _, encoding = header.partition(";")
            if encoding:
                _, _, encoding = encoding.strip().partition("=")
                try:
                    codecs.lookup(encoding)
                except LookupError:
                    encoding = None
            if mime not in self.accepted_mimes:
                raise AppException(f"Mime {mime} not supported")
        if encoding:
            log.info(f"Using encoding {encoding} to handle response")
        self.parser = self.parser_class()
        await response.collect(self.feed)
        return self.parser.close()

    async def get_url(self, url):
        return await treq.get(url, timeout=self.TIMEOUT, headers=self.headers)

    async def get_title(self, url):
        response = await self.get_url(url)
        root = await self.handle_response(response)

        titles = root.xpath("//title")
        if not titles:
            return ""
        title = titles[0].text

        if not title:
            return ""
        else:
            return " ".join(title.split())


def difference_check(a, s):
    if len(a) < 14 or len(s) < 14:
        if len(a) != len(s):
            return True
        else:
            return a != s
    else:
        return Levenshtein.distance(a, s) >= 7

def dynsearch(l, s):
    a, b = l[0], l[1:]
    if not b:
        return difference_check(a, s)
    else:
        if not dynsearch(b, s):
            return False
        else:
            return difference_check("".join(b), s)

def prepare_url(url):
    path = urlparse.unquote(urlparse.urlparse(url).path).replace("-", "")
    path = path.replace(" ", "").replace("+", "").replace("_", "").lower()
    path = path.rstrip("0123456789")
    return path.split("/")

def prepare_title(title):
    title = title.replace("+", "").replace(" ", "").replace("_", "").lower()
    return re.split("[-–]", title)[0]

class MessageHandler(object):

    _URL_HANDLER_CLASS = UrlHandler

    def __init__(self, reactor, hits, misses, callback, max_len):
        self._reactor = reactor
        self._hits = hits
        self._misses = misses
        self._max_len = max_len
        self._callback = callback

    async def success(self, title, url):
        log.info(f"Got title {title}")
        if dynsearch(prepare_url(url), prepare_title(title)):
            log.info("Will try to send title as a message")
            await self._callback("title: %s" % title)
            await task.deferLater(self._reactor, 2, defer.succeed,
                                  None)

    def fail(self, url):
        self._misses.update(url, "miss")
        log.failure(f"Adding {url} to temporary block list")

    async def find_links(self, message):
        for m in re.finditer("(https?://[^ ]+)", message):
            url = m.group(0)
            if not acceptable_netloc(urlparse.urlparse(url).netloc):
                continue
            if self._misses.fetch(url):
                log.info((f"Skipped title check for URL {url} because of "
                    "previous failures"))
                continue
            title = self._hits.fetch(url)
            if title is None:
                log.info(f"Cache miss for URL {url}")
                handler = self._URL_HANDLER_CLASS(
                    max_body=2 * 1024 ** 2, parser_class=lxml.html.HTMLParser)
                try:
                    title = await handler.get_title(url)
                except Exception:
                    self.fail(url)
                else:
                    if len(title) > self._max_len:
                        title = title[:self._max_len]
                    if title:
                        self._hits.update(url, title)
                        await self.success(title, url)
            else:
                log.info(f"Cache hit for URL {url}")
                await self.success(title, url)


class UrlCache(object):

    def __init__(self, reactor, expiration=60):
        self._reactor = reactor
        self._expiration = expiration
        self._db = {}
        self._reaper = task.LoopingCall(self._reap)
        self._reaper.clock = reactor

    def fetch(self, key):
        try:
            value = self._db[key]["value"]
        except KeyError:
            value = None
        return value

    def update(self, key, value):
        self._db[key] = {"value": value,
                         "timestamp": self._reactor.seconds()}

    def _valid(self):
        for key, value in self._db.items():
            if self._reactor.seconds() - value["timestamp"] < self._expiration:
                yield key, value

    def enable(self):
        if not self._reaper.running:
            self._reaper.start(self._expiration, False)

    def disable(self):
        if self._reaper.running:
            self._reaper.stop()

    def _reap(self):
        self._db = dict(self._valid())


class TitlePlugin(Plugin):
    """
    Plugin that fetches and announces HTML titles for URLs posted in IRC.
    """

    def load(self):
        """Load the plugin, initialise URL caches and register privmsg handler."""
        log.info(f"Loading {self.name} plugin")
        self._good_urls = UrlCache(self.reactor, expiration=3600)
        self._good_urls.enable()
        self._bad_urls = UrlCache(self.reactor, expiration=60)
        self._bad_urls.enable()
        self._max_len = self.config.get('max_title_length', 200)
        self.register_handler('privmsg', self.on_privmsg)
        log.info(f"{self.name} plugin loaded successfully")

    def unload(self):
        """Unload the plugin and stop cache reapers."""
        log.info(f"Unloading {self.name} plugin")
        self._good_urls.disable()
        self._bad_urls.disable()

    def on_privmsg(self, protocol, user, channel, message):
        """
        Called when a message is received; fetches titles for any URLs found.

        Args:
            protocol: NanoBotProtocol instance
            user: User who sent the message (nick!user@host)
            channel: Channel name or bot nickname (for private messages)
            message: Message text
        """
        # For private messages reply to the sender, not the channel
        if channel == protocol.nickname:
            target = user.split('!')[0]
        else:
            target = channel

        async def callback(text):
            protocol.msg(target, text)

        handler = MessageHandler(
            self.reactor, self._good_urls, self._bad_urls,
            callback, self._max_len,
        )
        d = defer.ensureDeferred(handler.find_links(message))
        d.addErrback(lambda f: log.failure("Error in title plugin: {f}", f=f))
        return d


def load(registry, config):
    """
    Plugin entry point called by PluginRegistry when loading the plugin.

    Args:
        registry: PluginRegistry instance
        config: Plugin configuration dictionary

    Returns:
        TitlePlugin instance
    """
    plugin_name = config.get('name', 'title')
    plugin_config = config.get('config', {})
    plugin = TitlePlugin(plugin_name, registry, plugin_config)
    plugin.load()
    return plugin
