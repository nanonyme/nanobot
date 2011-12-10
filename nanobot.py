from yaml import load, Loader

from twisted.words.protocols import irc
from twisted.application import service
from twisted.internet import reactor, protocol
import socket
import exocet
from twisted.python import log
import re

def resolve(server, port, callback, *args, **kwargs):
    addresses = []
    try:
        for line in socket.getaddrinfo(server, port):
            (address, port) = line[4]
            addresses.append(address)
    except socket.gaierror, e:
        log.err("%s", str(e))
    else:
        reactor.callFromThread(callback, server, port, addresses,
                               *args, **kwargs)

class NanoBotProtocol(object, irc.IRCClient):
    ping_delay = 180
    
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)
        self.online = False

    def connectionMade(self):
        irc.IRCClient.connectionMade(self)
        self.online = True
        log.msg("Connected to %s" % self.server)
        reactor.callLater(0, self.sendPing)
        self.delegate(self, "connectionMade")
        
    def signedOn(self):
        irc.IRCClient.signedOn(self)
        self.delegate(self, 'signedOn')
        

    def sendPing(self):
        self.ping(self.nickname)
        if self.ping_delay is not None and self.online:
            reactor.callLater(self.ping_delay, self.sendPing)

    def connectionLost(self, reason):
        self.online = False
        log.msg("Connection to %s lost" % self.server)
        self.delegate(self, "connectionLost", reason)
        irc.IRCClient.connectionLost(self, reason)

    def privmsg(self, user, channel, message):
        irc.IRCClient.privmsg(self, user, channel, message)
        self.delegate(self, 'privmsg', user, channel, message)

    def noticed(self, user, channel, message):
        irc.IRCClient.privmsg(self, user, channel, message)
        self.delegate(self, 'privmsg', user, channel, message)

class ReconnectingFactory(object, protocol.ReconnectingClientFactory):
    maxDelay = 120
    initialDelay = 10
    factory = 1.5
    jitter = 0

class NanoBotFactory(ReconnectingFactory):
    protocol = NanoBotProtocol

    def __init__(self, bot, config):
        super(NanoBotFactory, self).__init__()
        self.bot = bot
        self.config = config
        self.network_mapping = dict()

    def buildProtocol(self, address):
        server = self.network_mapping[(address.host, address.port)]
        kwargs = self.config['core']
        kwargs['server'] = server
        kwargs['factory'] = self
        kwargs['delegate'] = self.bot.delegate
        return self.protocol(**kwargs)

    def map_to_network(self, address, network):
        self.network_mapping[address] = network


class NanoBot(object, service.MultiService):
    def __init__(self, configfile):
        service.MultiService.__init__(self)
        self._rehash()
        with open(configfile) as f:
            self.config = load(f, Loader=Loader)
        factory = NanoBotFactory(self, self.config)
        for network in self.config['networks']:
            server = network['server']
            port = int(network.get('port', 6667))
            reactor.callInThread(resolve, server, port, self.connect, factory)

    def connect(self, server, port, addrinfo, factory):
        for address in addrinfo:
            factory.map_to_network((address, port), server)
        for network in self.config['networks']:
            if network['server'] == server:
                if network.get('ssl', False):
                    reactor.connectSSL(server, port, factory)
                else:
                    reactor.connectTCP(server, port, factory)
                break

    def _rehash(self):
        log.msg("Beginning rehash")
        for plugin in self:
            plugin.disownServiceParent()
        for module_iter in exocet.getModule("plugins_enabled").iterModules():
            plugin_module = exocet.load(module_iter, exocet.pep302Mapper)
            for plugin_name in module_iter.iterExportNames():
                plugin_class = getattr(plugin_module, plugin_name)
                if issubclass(plugin_class, service.Service):
                    plugin = plugin_class()
                    plugin.setServiceParent(self)
        log.msg("Finished rehash")

    def cmd_rehash(self, instance, user, channel, parameters):
        self._rehash()
        self.reply(instance, user, channel, "Succesfully rehashed")
        

    def signedOn(self, instance):
        for network in self.config['networks']:
            if instance.server == network['server']:
                for channel in network['channels']:
                    if 'key' in channel:
                        instance.join(channel['name'], channel['key'])
                    else:
                        instance.join(channel['name'])
                break

    def reply(self, instance, user, channel, message):
        nick, _, _ = user.partition("!")
        log.msg(nick)
        if instance.nickname == channel:
            instance.msg(nick, message)
        else:
            instance.msg(channel, "%s, %s" % (nick, message))

    def privmsg(self, instance, user, channel, message):
        cmd = False
        if message.startswith(instance.nickname):
            cmd = True
            pattern = r'(%s[^\w]+)' % instance.nickname
            message = re.sub(pattern, '', message)
        if cmd or channel == instance.nickname:
            admins = self.config['core'].get('admins', None)
            is_admin = False
            if not admins:
                self.reply(instance, user, channel,
                           "I'm free, I've no masters")
                return
            for admin in admins:
                if re.match(admin, user):
                    is_admin = True
                    break
            if not is_admin:
                self.reply(instance, user, channel, "You are not an admin")
            message = message.lower()
            command, _, parameters = message.partition(" ")
            self.delegate(instance, "cmd_" + command, user, channel,
                          parameters)

    def delegate(self, instance, description, *args, **kwargs):
        try:
            f = getattr(self, description)
        except AttributeError:
            pass
        else:
            f(instance, *args, **kwargs)
        for plugin in self:
            try:
                f = getattr(plugin, description)
            except AttributeError:
                pass
            else:
                f(self, instance, *args, **kwargs)
        

if __name__ == '__main__':
    log.startLogging(open("nanobot.log", "a"))
    bot = NanoBot("config.yaml")
    reactor.run()
