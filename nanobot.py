import json
from twisted.words.protocols import irc
from twisted.internet import protocol, task
from twisted.spread import pb
import sys
from collections import deque
from twisted.logger import textFileLogObserver, globalLogPublisher, Logger

log = Logger()


class RemoteProtocol(pb.Referenceable):

    def __init__(self, protocol):
        self.protocol = protocol

    def remote_msg(self, user, message):
        self.protocol.msg(user, message)

    def remote_join(self, channel, key):
        self.protocol.join(channel, key)

    def remote_leave(self, channel, reason):
        self.protocol.leave(channel, reason)


class NanoBotProtocol(irc.IRCClient):
    ping_delay = 180

    def __init__(self, reactor, server, bot, fallback_encoding):
        self._reactor = reactor
        self.server = server
        self.bot = bot
        self.fallback_encoding = fallback_encoding

    @property
    def channels(self):
        return self.server.channels

    def lineReceived(self, line):
        try:
            text = line.decode("utf-8")
        except UnicodeDecodeError:
            if self.fallback_encoding is not None:
                text = line.decode(fallback_encoding)
            else:
                text = line.decode("utf-8", "ignore")
        super().lineReceived(text)

    def connectionMade(self):
        irc.IRCClient.connectionMade(self)
        log.info(f"Connected to {self.server.hostname}")

    def signedOn(self):
        irc.IRCClient.signedOn(self)
        for channel in self.channels:
            if 'key' in channel:
                self.join(channel['name'], channel['key'])
            else:
                self.join(channel['name'])

    def connectionLost(self, reason):
        log.info(f"Connection to {self.server.hostname} lost")
        irc.IRCClient.connectionLost(self, reason)

    def privmsg(self, user, channel, message):
        irc.IRCClient.privmsg(self, user, channel, message)
        ref = RemoteProtocol(self)
        fmt = f'PRIVMSG {user} :'
        max_len = self._safeMaximumLineLength(fmt) - len(fmt) - 50
        if channel == self.nickname:
            self.bot.api.callRemote("handlePrivateMessage", ref, user, channel,
                                    message, max_len)
        else:
            self.bot.api.callRemote("handlePublicMessage", ref, user, channel,
                                    message, max_len)


class ServerConnection(protocol.ReconnectingClientFactory):
    protocol = NanoBotProtocol

    def __init__(self, reactor, network_config, bot):
        self._reactor = reactor
        self.bot = bot
        self.network_config = network_config
        self.fallback_encoding = self.network_config.get('fallback_encoding', None)

    def buildProtocol(self, addr):
        protocol = self.protocol(self._reactor, server=self, bot=self.bot,
                                 fallback_encoding=self.fallback_encoding)
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

    def connect(self):
        if self.is_ssl:
            self._reactor.connectSSL(self.hostname, self.port, self)
        else:
            self._reactor.connectTCP(self.hostname, self.port, self)


class ApiProxy(pb.Root):

    def __init__(self, reactor):
        self.reactor = reactor
        self.app = None
        self.queue = deque()
        self.running = False

    def callRemote(self, *args, **kwargs):
        self.queue.append((self.reactor.seconds(), args, kwargs))
        self.run()

    def run(self):
        if not self.running:
            self.running = True
            task.coiterate(iter(self))

    def __iter__(self):
        while True:
            if not self.app:
                log.info("Messages in loop but no app is connected")
                self.running = False
                break
            elif not self.queue:
                self.running = False
                break
            else:
                seconds, args, kwargs = self.queue.popleft()
                d = self.app.callRemote(timestamp=seconds, *args, **kwargs)
                @d.addErrback
                def log_error(failure):
                    log.error("Ignored exception", failure=failure)
                yield d
 
    def remote_register(self, app):
        log.info(f"Got registration request for {app}")
        self.app = app
        self.run()

    def disconnect(self):
        self.app = None

class ProcessProtocol(protocol.ProcessProtocol):

    def __init__(self, bot, broker_factory):
        self.bot = bot
        self.logs = []
        self.broker = broker_factory.buildProtocol(None)

    def makeConnection(self, transport):
        self.broker.makeConnection(transport)

    def outReceived(self, data):
        self.broker.dataReceived(data)

    def processExited(self, status):
        log.info(f"Process exited with status code {status}")
        log.info(b"".join(self.logs))
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
        f = open(self.core_config["log_file"], "a")
        globalLogPublisher.addObserver(textFileLogObserver(f))
        self.api = ApiProxy(self._reactor)
        self.server_factory = pb.PBServerFactory(self.api)

    def run(self):
        d = self.reconnect_app()
        d.addCallback(lambda _: self._init_connections())

    def _init_connections(self):
        log.info("Setting up networks")
        for network_config in self.config['networks']:
            network = ServerConnection(reactor=self._reactor,
                                       network_config=network_config,
                                       bot=self)
            self.connections[network.name] = network
            network.connect()

    def reconnect_app(self):
        log.info("App start requested")
        if not self.exiting:
            self.api.disconnect()
            return task.deferLater(self._reactor, 1, self._do_reconnect)

    def _do_reconnect(self):
        log.info("Starting app logic layer and telling it to connect")
        self._proc = self._reactor.spawnProcess(ProcessProtocol(self,
                                                                self.server_factory),
                                                sys.executable,
                                                args=[sys.executable, "-u",
                                                      "app.py"],
                                                env={"CONFIG": "config.json"})

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

    def shutdown(self):
        self.exiting = True
        if self._proc:
            self._proc.signalProcess('KILL')


def main():
    from twisted.internet import reactor
    nanobot = NanoBot(reactor, "config.json")
    reactor.callWhenRunning(nanobot.run)
    reactor.addSystemEventTrigger("before", "shutdown", nanobot.shutdown)
    reactor.run()

if __name__ == '__main__':
    main()
