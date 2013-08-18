import json
from twisted.words.protocols import irc
from twisted.internet import protocol, task
from twisted.python import log
import treq
import lxml.html
import re
import Levenshtein
import functools
import urlparse

class MessageHandler(object):
    def __init__(self, reactor, cache, message, callback,
                 encoding):
        self._callback = callback
        self._reactor = reactor
        self._message = message
        self._cache = cache
        self._encoding = encoding

    def __iter__(self):
        for m in re.finditer("(https?://[^ ]+)", self._message):
            try:
                url = m.group(0)
                title = self._cache.fetch(url)
                if title is None:
                    d = treq.get(url)
                    parser = lxml.html.HTMLParser()
                    d.addCallback(treq.collect, parser.feed)
                    yield d
                    root = parser.close()
                    title = root.xpath("//title")[0].text
                    title = title.replace("\r\n", "").replace("\n", "")
                    title = title.encode(self._encoding)
                    self._cache.update("url", title)
                    if Levenshtein.distance(urlparse.urlparse(url).path,
                                            title) > 7:
                        self._callback("title: %s" % title)
                        yield task.deferLater(self._reactor, 2,
                                              (lambda x:x), None) # throttle self
            except Exception:
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

class NanoBotProtocol(object, irc.IRCClient):
    ping_delay = 180

    def __init__(self, reactor, server, bot):
        self._reactor = reactor
        self.server = server
        self.bot = bot

    @property
    def channels(self):
        return self.server.channels
    
    def connectionMade(self):
        irc.IRCClient.connectionMade(self)
        log.msg("Connected to %s" % self.server.hostname)
        
    def signedOn(self):
        irc.IRCClient.signedOn(self)
        for channel in self.channels:
            if 'key' in channel:
                self.join(channel['name'].encode(self.server.encoding),
                          channel['key'].encode(self.server.encoding))
            else:
                self.join(channel['name'].encode(self.server.encoding))

    def connectionLost(self, reason):
        log.msg("Connection to %s lost" % self.server.hostname)
        irc.IRCClient.connectionLost(self, reason)

    def privmsg(self, user, channel, message):
        irc.IRCClient.privmsg(self, user, channel, message)
        callback = functools.partial(self.say, channel)
        handler = MessageHandler(self._reactor, self.bot._url_cache,
                                 message, callback, self.server.encoding)
        return task.coiterate(iter(handler))
            
class ServerConnection(protocol.ReconnectingClientFactory):
    protocol = NanoBotProtocol
    def __init__(self, reactor, network_config, bot):
        self._reactor = reactor
        self.bot = bot
        self.network_config = network_config

    def buildProtocol(self, addr):
        protocol = self.protocol(self._reactor, server=self, bot=self.bot)
        if self.bot.nickname:
            protocol.nickname = self.bot.nickname.encode(self.encoding)
        if self.bot.realname:
            protocol.realname = self.bot.realname.encode(self.encoding)
        return protocol

    @property
    def channels(self):
        return self.network_config.get('channels', dict())

    @property
    def name(self):
        return self.network_config['name']

    @property
    def hostname(self):
        return self.network_config['hostname']

    @property
    def port(self):
        return int(self.network_config.get('port', 6667))

    @property
    def is_ssl(self):
        return bool(self.network_config.get('ssl', False))

    @property
    def encoding(self):
        return self.network_config.get('encoding', 'utf-8')

    def connect(self):
        if self.is_ssl:
            self._reactor.connectSSL(self.hostname.encode(self.encoding),
                                     self.port, self)
        else:
            self._reactor.connectTCP(self.hostname.encode(self.encoding),
                                     self.port, self)
    

class NanoBot(object):

    def __init__(self, reactor, config_filename):
        self._network = None
        self._reactor = reactor
        self._config_filename = config_filename
        self.connections = dict()
        self._url_cache = UrlCache(self._reactor, 3600)
        self._url_cache.enable()
        with open(config_filename) as f:
            self.config = json.load(f)
            self._init_connections()

    def _init_connections(self):
        for network_config in self.config['networks']:
            network = ServerConnection(reactor=self._reactor,
                                       network_config=network_config,
                                       bot=self)
            self.connections[network.name] = network
            network.connect()

    @property
    def core_config(self):
        if 'core' in self.config:
            return self.config['core']
        raise Exception("Missing core section from config")

    @property
    def nickname(self):
        return self.core_config.get('nickname', u'nanobot')

    @property
    def realname(self):
        return self.core_config.get('realname', u'https://bitbucket.org/nanonyme/nanobot')


def main():
    from twisted.internet import reactor
    log.startLogging(open("nanobot.log2", "a"))
    NanoBot(reactor, "config.json")
    reactor.run()

if __name__ == '__main__':
    main()
