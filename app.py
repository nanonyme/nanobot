# -*- coding: utf-8 -*-
from twisted.spread import pb
from twisted.internet import endpoints
from os import environ
import json
from twisted.logger import textFileLogObserver, globalLogPublisher, Logger

log = Logger()

config = {}


class API(pb.Referenceable):
    STALENESS_LIMIT = 24*60*60

    def __init__(self, reactor):
        self.reactor = reactor

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

    def remote_handlePrivateMessage(self, protocol, user, channel, message,
                                    max_line_length, timestamp):
        if self._staleness_check(timestamp):
            return


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
