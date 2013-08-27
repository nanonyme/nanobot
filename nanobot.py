import json
from twisted.words.protocols import irc
from twisted.internet import protocol, task, endpoints
from twisted.spread import pb
import sys

from twisted.python import log

class RemoteProtocol(pb.Referenceable):
    def __init__(self, protocol):
        self.protocol = protocol

    def remote_say(self, channel, message):
        self.protocol.say(channel, message)

    def remote_join(self, channel, key):
        self.protocol.join(channel, key)

    def remote_leave(self, channel, reason=None):
        self.protocol.leave(channel, reason)

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
        ref = RemoteProtocol(self)
        fmt = 'PRIVMSG %s :' % (user,)
        max_len = self._safeMaximumLineLength(fmt) - len(fmt) - 50
        d = self.bot.app.callRemote("handleMessage", ref, user, channel,
                                    message, self.server.encoding, max_len)
        d.addErrback(log.err)

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


class RegistrationApi(pb.Root):
    def __init__(self, bot):
        self.bot = bot

    def remote_register(self, app):
        log.msg("Got registration request for %s" % str(app))
        self.bot.app = app
        return self.bot.core_config

class ProcessProtocol(protocol.ProcessProtocol):
    def __init__(self, bot):
        self.bot = bot
        self.logs = []

    def errReceived(self, data):
        self.logs.append(data)

    def processExited(self, status):
        log.msg("Process exited with status code %s" % status)
        log.msg("".join(self.logs))
        return self.bot.reconnect_app()


class NanoBot(object):
    app = None
    exiting = False

    def __init__(self, reactor, config_filename):
        self._network = None
        self._proc = None
        self._reactor = reactor
        self._config_filename = config_filename
        self.connections = dict()
        with open(config_filename) as f:
            self.config = json.load(f)
        log.startLogging(open(self.core_config["log_file"], "a"))
        endpoint = endpoints.serverFromString(self._reactor,
                                              str(self.core_config["masterEndpoint"]))
        factory = pb.PBServerFactory(RegistrationApi(self))
        conn = endpoint.listen(factory)
        self.reconnect_app()
        self._init_connections()


    def _init_connections(self):
        log.msg("Setting up networks")
        for network_config in self.config['networks']:
            network = ServerConnection(reactor=self._reactor,
                                       network_config=network_config,
                                       bot=self)
            self.connections[network.name] = network
            network.connect()

    def reconnect_app(self):
        log.msg("App start requested")
        if not self.exiting:
            return task.deferLater(self._reactor, 1, self._do_reconnect)


    def _do_reconnect(self):
        log.msg("Starting app logic layer and telling it to connect")
        self._proc = self._reactor.spawnProcess(ProcessProtocol(self),
                                                sys.executable,
                                                args=[sys.executable,
                                                      "app.py"],
                                                env={"CONFIG": "config.json"})
            

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

    def shutdown(self):
        self.exiting = True
        if self._proc:
            self.proc.signalProcess('KILL')
        

def main():
    from twisted.internet import reactor
    nanobot = NanoBot(reactor, "config.json")
    reactor.addSystemEventTrigger("before", "shutdown", nanobot.shutdown)
    reactor.run()

if __name__ == '__main__':
    main()
