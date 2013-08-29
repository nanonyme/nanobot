from twisted.spread import pb
from twisted.internet.endpoints import clientFromString
from os import environ
from twisted.internet import task, reactor
from twisted.python import log
import functools
import treq
import lxml.html
import re
import Levenshtein
import urlparse
import iptools
import json
import sqlite3
import codecs

INTERNAL_IPS = iptools.IpRangeList(
    '127/8',                # full range
    '192.168/16',               # CIDR network block
    ('10.0.0.1', '10.0.0.19'),  # arbitrary inclusive range
    '::1',                      # single IPv6 address
    'fe80::/10',                # IPv6 CIDR block
    '::ffff:172.16.0.2'         # IPv4-mapped IPv6 address
)

config = {}

def acceptable_netloc(hostname):
    acceptable = True
    try:
        if hostname in INTERNAL_IPS:
            acceptable = False
    except TypeError:
        if hostname == "localhost":
            acceptable = False
    return acceptable

class ResponseHandler(object):
    
    
    def __init__(self, max_body, parser_class,
                 accepted_mimes=("text/html",)):
        self.max_body = max_body
        self.bytes = 0
        self.parser_class = parser_class
        self.parser = None
        self.d = None
        self.accepted_mimes = accepted_mimes
        self.err = None

    def feed(self, data):
        if self.bytes < self.max_body:
            if len(data) > self.max_body - self.bytes:
                data = data[:self.max_body-self.bytes]
            data_len = len(data)
            self.bytes += data_len
            self.parser.feed(data)
        else:
            d.cancel()

    def handle(self, response):
        headers = response.headers.getRawHeaders("Content-Type")
        self.d = treq.collect(response, self.feed)
        self.d.addErrback(self.trap_cancellation)
        if not headers:
            self.d.cancel()
        else:
            header = headers[0]
            log.msg("Header line %s" % header)
            mime, _, encoding = header.partition(";")
            if encoding:
                _, _, encoding = encoding.strip().partition("=")
                try:
                    codecs.lookup(encoding)
                except LookupError:
                    encoding = None
            if mime not in self.accepted_mimes:
                self.d.cancel()
            else:
                if encoding:
                    self.parser = self.parser_class(encoding=encoding)
                    log.msg("Using encoding %s to handle response" % encoding)
                else:
                    self.parser = self.parser_class()
        return self.d

    def trap_cancellation(self, err):
        self.err = err


class MessageHandler(object):
    def __init__(self, reactor, hits, misses, message, callback,
                 encoding, max_len):
        self._callback = callback
        self._reactor = reactor
        self._message = message
        self._hits = hits
        self._misses = misses
        self._encoding = encoding
        self._max_len = max_len

    def __iter__(self):
        for m in re.finditer("(https?://[^ ]+)", self._message):
            try:
                url = m.group(0)
                log.msg("Fetching title for URL %s" % url)
                title = self._hits.fetch(url)
                miss = self._misses.fetch(url)
                if not acceptable_netloc(urlparse.urlparse(url).netloc):
                    continue
                if miss:
                    log.msg("Skipped")
                    continue
                if title is None:
                    d = treq.get(url, timeout=5)
                    handler = ResponseHandler(max_body=2*1024**2, parser_class=lxml.html.HTMLParser)
                    d.addCallback(handler.handle)
                    yield d
                    if handler.err:
                        handler.err.raiseException()
                    root = handler.parser.close()
                    title = root.xpath("//title")[0].text
                    title = " ".join(title.split())
                    if len(title) > self._max_len:
                        title = title[:self._max_len]
                    title = title.encode(self._encoding)
                    self._hits.update("url", title)
                log.msg("Got title %s" % title)
                if Levenshtein.distance(urlparse.urlparse(url).path,
                                        title) > 7:
                    log.msg("Will try to send title as a message")
                    yield self._callback("title: %s" % title)
                    yield task.deferLater(self._reactor, 2,
                                          (lambda x:x), None) # throttle self
            except Exception:
                self._misses.update(url, "miss")
                log.err()


class UrlCache(object):
    def __init__(self, reactor, expiration=60):
        self._reactor = reactor
        self._expiration = expiration
        self._db = {}
        self._reaper = None

    def fetch(self, key):
        item = self._db.get(key)
        if item is not None:
            return item["value"]
        return None

    def update(self, key, value):
        self._db[key] = {"value": value,
                         "timestamp": self._reactor.seconds()}

    def _valid(self):
        for key, value in self._db.iteritems():
            if self._reactor.seconds() - value["timestamp"] < self._expiration:
                yield key, value

    def enable(self):
        if self._reaper is None:
            self._reaper = task.LoopingCall(self._reap)
            self._reaper.clock = self._reactor
            self._reaper.start(self._expiration, False)

    def disable(self):
        if self._reaper is not None:
            self._reaper.stop()
            self._reaper = None
        
    def _reap(self):
        self._db = dict(self._valid())

class API(pb.Referenceable):
    def __init__(self, reactor):
        self.reactor = reactor
        self.good_urls = UrlCache(self.reactor, expiration=3600)
        self.good_urls.enable()
        self.bad_urls = UrlCache(self.reactor, expiration=60)
        self.bad_urls.enable()
    
    def remote_handlePublicMessage(self, protocol, user, channel, message,
                                   encoding, max_line_length):
        try:
            if message.startswith("!"):
                return handleCommand(protocol, user, channel, message[1:], encoding, max_line_length)
            else:
                callback = functools.partial(protocol.callRemote, "msg", channel)
                handler = MessageHandler(self.reactor, self.good_urls, self.bad_urls,
                                     message, callback, encoding, max_line_length)
                return task.coiterate(iter(handler))
        except Exception:
            log.err()

    def remote_handlePrivateMessage(self, protocol, user, channel, message,
                                    encoding, max_line_length):
        channel, _, _ = user.partition("!")
        return self.remote_handlePublicMessage(protocol, user, channel, message,
                                               encoding, max_line_length)

def handleCommand(protocol, user, channel, message, encoding, max_line_length):
    command, _, suffix = message.partition(" ")
    with sqlite3.connect(config["core"]["db"]) as conn:
        cur = conn.cursor()
        res = cur.execute("select roles.name from roles where roles.oid in (select userroles.oid from (user natural join usermask) natural join userroles where usermask.mask=?);", (user,))
        roles = [role[0] for role in res.fetchmany()]
        if command == "reincarnate":
            if "superadmin" in roles:
                log.msg("Restarting app")
                reactor.stop()
            else:
                log.msg("User %s tried to do code reload" % user)
        elif command == "join":
            channel, _, password = suffix.partition(" ")
            if not password:
                password = None
            if "superadmin" in roles:
                if password:
                    log.msg("Joining %s (%s)" % (channel, password))
                else:
                    log.msg("Joining %s" % channel)
                return protocol.callRemote("join", channel, password)
        elif command == "leave":
            channel, _, reason = suffix.partition(" ")
            if not reason:
                reason = None
            if "superadmin" in roles:
                if reason:
                    log.msg("Leaving %s (%s)", (channel, reason))
                else:
                    log.msg("Leaving %s", channel)
                return protocol.callRemote("leave", channel, reason)
        else:
            log.msg("Unrecognized command %s" % command)

def log_and_exit(ret, reactor):
    log.err()
    reactor.stop()

def register(root, reactor):
    log.msg("Registering app for bot")
    return root.callRemote("register", API(reactor))

if __name__ == "__main__":
    with open(environ["CONFIG"]) as f:
        config.update(json.load(f))
    log.startLogging(open(config["core"]["log_file"], "a"))
    appEndpoint = str(config["core"]["slaveEndpoint"])
    client = clientFromString(reactor, str(appEndpoint))
    factory = pb.PBClientFactory()
    client.connect(factory)
    d = factory.getRootObject()
    d.addCallback(register, reactor)
    d.addErrback(log_and_exit, reactor)
    reactor.run()

