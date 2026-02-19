# -*- coding: utf-8 -*-
from twisted.spread import pb
from twisted.internet import endpoints
from os import environ
import functools
import json
import sqlite3
import simple_eval
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
        try:
            callback = functools.partial(
                protocol.callRemote, "msg", channel)
            roles = resolveRoles(user)
            if "ignored" in roles:
                return
            if message.startswith("!"):
                return handleCommand(protocol, user, roles, channel, message[1:],
                                     max_line_length, callback)
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


def resolveRoles(user):
    with sqlite3.connect(config["core"]["db"]) as conn:
        cur = conn.cursor()
        res = cur.execute(user_query, (user,))
        return [role[0] for role in res.fetchmany()]


def handleCommand(protocol, user, roles, channel, message, max_line_length,
                  callback):
    command, _, suffix = message.partition(" ")
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
