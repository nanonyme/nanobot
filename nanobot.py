from yaml import load, Loader
from twisted.words.protocols import irc
from twisted.internet import protocol
from twisted.python import log
import dispatcher

class NanoBotProtocol(object, irc.IRCClient):
    ping_delay = 180

    def __init__(self, server, bot):
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
                self.join(channel['name'], channel['key'])
            else:
                self.join(channel['name'])

    def connectionLost(self, reason):
        log.msg("Connection to %s lost" % self.server.hostname)
        irc.IRCClient.connectionLost(self, reason)

    def privmsg(self, user, channel, message):
        irc.IRCClient.privmsg(self, user, channel, message)
        self.bot.dispatcher('privmsg', user=user, channel=channel,
                                    message=message, protocol=protocol)

    def noticed(self, user, channel, message):
        irc.IRCClient.privmsg(self, user, channel, message)
        self.bot.dispatcher("noticed", user=user, channel=channel,
                                    message=message, protocol=protocol)

    def reply(self, message, target):
        if 'unicode' in str(type(message)):
            encoding = self.factory.config['core'].get('encoding', 'utf-8')
            message = message.encode(encoding)
            target = None
            self.msg(target, message)
            raise StopIteration()

class ServerConnection(protocol.ReconnectingClientFactory):
    protocol = NanoBotProtocol
    def __init__(self, reactor, network_config, bot):
        self._reactor = reactor
        self.bot = bot
        self.network_config = network_config

    def buildProtocol(self, addr):
        protocol = self.protocol(server=self, bot=self.bot)
        if self.bot.nickname:
            protocol.nickname = self.bot.nickname
        if self.bot.realname:
            protocol.realname = self.bot.realname
        return protocol

    @property
    def channels(self):
        return self.network_config.get('channels', dict())

    @property
    def name(self):
        return self.network_config.get('name')

    @property
    def hostname(self):
        return self.network_config.get('hostname')

    @property
    def port(self):
        return int(self.network_config.get('port', 6667))

    @property
    def is_ssl(self):
        return bool(self.network_config.get('ssl', False))

    def connect(self):
        if self.is_ssl:
            self._reactor.connectSSL(self.hostname, self.port, self)
        else:
            self._reactor.connectTCP(self.hostname, self.port, self)
    

class NanoBot(object):

    def __init__(self, reactor, config_filename):
        self._network = None
        self._reactor = reactor
        self._config_filename = config_filename
        self.connections = dict()
        with open(config_filename) as f:
            self.config = load(f, Loader=Loader)
            self._init_connections()
        self.dispatcher = dispatcher.Dispatcher(reactor=self._reactor,
                                                bot=self)

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
        return self.core_config.get('nickname', 'nanobot')

    @property
    def realname(self):
        return self.core_config.get('realname',
                                    'https://bitbucket.org/nanonyme/nanobot')


def main():
    from twisted.internet import reactor
    log.startLogging(open("nanobot.log", "a"))
    NanoBot(reactor, "config.yaml")
    reactor.run()

if __name__ == '__main__':
    main()
