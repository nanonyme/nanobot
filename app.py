# -*- coding: utf-8 -*-
from twisted.spread import pb
from twisted.internet import endpoints, task, defer
from os import environ
import functools
import treq
import lxml.html
import re
import Levenshtein
from urllib import parse as urlparse
import json
import sqlite3
import codecs
import simple_eval
import ipaddress
from twisted.logger import textFileLogObserver, globalLogPublisher, Logger

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

config = {}


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

    async def get_title(self, url):
        response  = await treq.get(url, timeout=30, headers=self.headers)
        root = await self.handle_response(response)
        
        title = root.xpath("//title")[0].text

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

    def __init__(self, reactor, hits, misses, callback, max_len):
        self._reactor = reactor
        self._hits = hits
        self._misses = misses
        self._max_len = max_len
        self._callback = callback

    async def success(self, title, url, new_url):
        if len(title) > self._max_len:
            title = title[:self._max_len]
        if new_url:
            self._hits.update(url, title)
        if title:
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
                handler = UrlHandler(
                    max_body=2 * 1024 ** 2, parser_class=lxml.html.HTMLParser)
                try:
                    title = await handler.get_title(url)
                except Exception:
                    self.fail(url)
                else:
                    await self.success(title, url, True)
            else:
                log.info(f"Cache hit for URL {url}")
                await self.success(title, url, False)


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


class API(pb.Referenceable):
    STALENESS_LIMIT = 24*60*60

    def __init__(self, reactor):
        self.reactor = reactor
        self.good_urls = UrlCache(self.reactor, expiration=3600)
        self.good_urls.enable()
        self.bad_urls = UrlCache(self.reactor, expiration=60)
        self.bad_urls.enable()

    def _staleness_check(self, timestamp):
        if self.reactor.seconds() - timestamp > self.STALENESS_LIMIT:
            log.info("Message stale, ignoring")
            return True
        else:
            return False

    def remote_handlePublicMessage(self, protocol, user, channel, message,
                                   max_line_length, timestamp):
        if self._staleness_check(timestamp):
            return
        try:
            callback = functools.partial(
                protocol.callRemote, "msg", channel)
            if message.startswith("!"):
                return handleCommand(protocol, user, channel, message[1:],
                                     max_line_length, callback)
            else:
                handler = MessageHandler(self.reactor, self.good_urls,
                                         self.bad_urls, callback,
                                         max_line_length)
                return defer.ensureDeferred(handler.find_links(message))
        except Exception:
            log.failure("FIXME, runaway exception")

    def remote_handlePrivateMessage(self, protocol, user, channel, message,
                                    max_line_length, timestamp):
        if self._staleness_check(timestamp):
            return
        channel, _, _ = user.partition("!")
        return self.remote_handlePublicMessage(protocol, user, channel,
                                               message,
                                               max_line_length,
                                               timestamp)


user_query = ("select roles.name from roles where roles.oid in "
              "(select userroles.oid from (users natural join usermask)"
              "natural join userroles where usermask.mask=?);")


def handleCommand(protocol, user, channel, message, max_line_length,
                  callback):
    command, _, suffix = message.partition(" ")
    with sqlite3.connect(config["core"]["db"]) as conn:
        cur = conn.cursor()
        res = cur.execute(user_query, (user,))
        roles = [role[0] for role in res.fetchmany()]
        if command == "reincarnate":
            if "superadmin" in roles:
                log.info("Restarting app")
                reactor.stop()
            else:
                log.info("User {user} tried to do code reload", user=user)
        elif command == "eval":
            truth, expr = suffix.split(":")
            truth = [s.strip() for s in truth.split(",")]
            try:
                ret = simple_eval.eval_bool(expr, truth)
            except simple_eval.EvalError as e:
                callback(str(e))
            else:
                callback("Result: %s" % ret)
        elif command == "join":
            channel, _, password = suffix.partition(" ")
            if not password:
                password = None
            if "superadmin" in roles:
                if password:
                    log.info(f"Joining {channel} ({password})")
                else:
                    log.info(f"Joining {channel}")
                return protocol.callRemote("join", channel, password)
        elif command == "leave":
            channel, _, reason = suffix.partition(" ")
            if not reason:
                reason = None
            if "superadmin" in roles:
                if reason:
                    log.info("Leaving {channel} ({reason})",
                             channel=channel, reason=reason)
                else:
                    log.info(f"Leaving {channel}")
                return protocol.callRemote("leave", channel, reason)
        else:
            log.info(f"Unrecognized command {command}")


def log_and_exit(ret, reactor):
    log.failure("Critical failure, terminating application")
    reactor.stop()


def register(root, reactor):
    log.info("Registering app for bot")
    return root.callRemote("register", API(reactor))


if __name__ == "__main__":
    from twisted.internet import reactor
    with open(environ["CONFIG"]) as f:
        config.update(json.load(f))
    f = open(config["core"]["log_file"], "a")
    globalLogPublisher.addObserver(textFileLogObserver(f))
    endpoint = endpoints.StandardIOEndpoint(reactor)
    factory = pb.PBClientFactory()
    d = endpoint.listen(factory)
    @d.addCallback
    def initialize(_):
        d = factory.getRootObject()
        d.addCallback(register, reactor)
        d.addErrback(log_and_exit, reactor)
        return
    reactor.run()
