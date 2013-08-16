import json
from twisted.words.protocols import irc
from twisted.internet import protocol, defer
from twisted.python import log
import treq
import lxml.html
import time
import re
import Levenshtein
import urlparse

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
        self._reactor.callLater(0, self.page_title, user, channel, message)


    @defer.inlineCallbacks
    def page_title(self, user, channel, message):
        for m in re.finditer("(https?://[^ ]+)", message):
            url = m.group(0)
            try:
                title_data = self.bot._title_cache.get(url)
                if title_data is None or title_data["timestamp"] - time.time() > 60:
                    response = yield treq.get(url)
                    parser = lxml.html.HTMLParser()
                    yield treq.collect(response, parser.feed)
                    root = parser.close()
                    title_data = {"title": root.xpath("//title")[0].text.replace("\r\n", " ").replace("\n", " "),
                                  "timestamp": time.time()}
                    self.bot._title_cache["url"] = title_data
                title = title_data["title"]
                if Levenshtein.distance(urlparse.urlparse(url).path, title) > 7:
                    self.say(channel, "title: %s" % title)
                    yield self._reactor.callLater(2, (lambda x:x)) # throttle self
            except Exception:
                log.err()
            
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
        self._title_cache = dict()
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
    log.startLogging(open("nanobot.log", "a"))
    NanoBot(reactor, "config.json")
    reactor.run()

if __name__ == '__main__':
    main()
