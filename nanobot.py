from yaml import load, Loader
from zope.interface import implements
from twisted.words.protocols import irc
from twisted.application import service
from twisted.internet import reactor, protocol
import socket
import exocet
from twisted.python import log
import re
import urllib


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


class NanoBot(object):
    implements(service.IServiceCollection)
    def __init__(self, configfile):
        self.url_cache = dict()
        self._services = dict()
        self._services = dict()
        self._rehash()
        with open(configfile) as f:
            self.config = load(f, Loader=Loader)
        factory = NanoBotFactory(self, self.config)
        for network in self.config['networks']:
            server = network['server']
            port = int(network.get('port', 6667))
            reactor.callInThread(resolve, server, port, self.connect, factory)

    def addService(self, s):
        if str(s) in self._services:
            raise RuntimeError("Two services with same name not allowed")
        self._services[str(s)] = s

    def removeService(self, s):
        if str(s) in self._services:
            del self._services[str(s)]

    def __iter__(self):
        for s in self._services:
            yield self._services[s]

    def getServiceNamed(self, name):
        if name not in self._services:
            raise KeyError(name)
        return self._services[name]

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
        _service = service
        for plugin in list(self):
            plugin.disownServiceParent()
        for module_iter in exocet.getModule("plugins_enabled").iterModules():
            plugin_module = exocet.load(module_iter, exocet.pep302Mapper)
            if 'BasePlugin' in dir(plugin_module):
                continue
            for plugin_name in module_iter.iterExportNames():
                plugin_class = getattr(plugin_module, plugin_name)
                if issubclass(plugin_class, _service.Service):
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

    def reply(self, instance, user, channel, message, direct=True):
        if 'unicode' in str(type(message)):
            encoding = self.config['core'].get('encoding', 'utf-8')
            message = message.encode(encoding)
        nick, _, _ = user.partition("!")
        if instance.nickname == channel:
            instance.msg(nick, message)
        elif direct:
            instance.msg(channel, "%s, %s" % (nick, message))
        else:
            instance.msg(channel, message)

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

    def fetch_url(self, url):
        name = self.url_cache.get(url, None)
        if name:
            try:
                f = open(name)
            except IOError:
                del self.url_cache[url]
                f = None
        if not name:
            try:
                name, _ = urllib.urlretrieve(url)
            except IOError:
                log.err("Couldn't connect to %s" % url)
                return
            self.url_cache[url] = name
        with open(name) as f:
            return f.read()
            

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
                f(instance, *args, **kwargs)

def main():
    log.startLogging(open("nanobot.log", "a"))
    bot = NanoBot("config.yaml")
    reactor.run()

if __name__ == '__main__':
    main()
