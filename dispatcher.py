import http_client
from zope.interface import implements
from twisted.application import service
from twisted.python import modules
from twisted.internet import defer
from twisted.python import log
from twisted.python import rebuild
import yaml
from collections import defaultdict
import re

plugins = modules.getModule('plugins')
def plugin_method(priority):
    def wrapper(function):
        return(plugins.load().PluginMethod(function=function,
                                           priority=priority))
    return wrapper

class Dispatcher(object):
    implements(service.IServiceCollection)
    def __init__(self, reactor, bot):
        self.reactor = reactor
        self.bot = bot
        self.cache = http_client.HTTPClient("cache")
        self._services = dict()
        self._config = dict()
        self._rehash()
        self.command_table = defaultdict(set)
    
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

    @plugin_method('high')
    def cmd_rehash(self, parameters, user, channel, d):
        return d.callback(self._rehash())

    def _rehash(self):
        log.msg("Beginning rehash")
        for plugin in list(self):
            plugin.disownServiceParent()
        with open('config.yaml') as f:
            self._config['plugins'] = yaml.load(f).get('plugins', [])
        rebuild.updateInstance(self.cache)
        rebuild.updateInstance(self)
        BasePlugin = plugins.load().BasePlugin
        for iterator in plugins.walkModules():
            plugin_module = iterator.load()
            prefix, _, name = plugin_module.__name__.partition('.')
            if name not in self._config['plugins']:
                continue
            for plugin_name in dir(plugin_module):
                plugin_class = getattr(plugin_module, plugin_name)
                if plugin_class is BasePlugin:
                    continue
                try:
                    if issubclass(plugin_class, BasePlugin):
                        plugin_class().setServiceParent(self)
                except TypeError:
                    continue
        log.msg("Rehash done")
        return "Rehashed"

    def __call__(self, result, **kwargs):
        _plugins = plugins.load()
        try:
            plugin_method = getattr(self, result)
        except AttributeError:
            pass
        else:
            d = plugin_method(**kwargs)
            if d is not None:
                return d
        plugin_methods = []
        for plugin_class in self:
            try:
                plugin_method = getattr(plugin_class, result)
            except AttributeError:
                pass
            else:
                plugin_methods.append(plugin_method)
        for plugin_method in sorted(plugin_methods,
                                    cmp=_plugins.order_plugin_methods):
            d = plugin_method(**kwargs)
            if d is not None:
                return d


    def privmsg(self, user, channel, message, protocol):
        cmd = False
        prefix = ""
        if channel == protocol.nickname:
            target, _, _ = user.partition("!")
        else:
            target = channel
            prefix, _, _ = user.partition("!")
        d = defer.Deferred()
        d.addCallback((lambda message, prefix: "%s, %s" % (prefix, message)), prefix)
        d.addCallback(protocol.reply, target)
        if message.startswith(protocol.nickname):
            cmd = True
            pattern = r'(%s[^\w]+)' % protocol.nickname
            message = re.sub(pattern, '', message)
            if cmd or channel == protocol.nickname:
                admins = self.bot.core_config.get('admins', [])
                is_admin = False
                if len(admins) == 0:
                    self.reactor.callLater(0, d.callback, "I have no masters")
                    return d
                for admin in admins:
                    admin = admin.replace(".", "\.")
                    admin = admin.replace("*", ".*")
                    if re.match(admin, user):
                        is_admin = True
                        break
            if not is_admin:
                self.reactor.callLater(0, d.callback, 'You are not an admin')
                return d
            ret = defer.Deferred()
            message = message.lower()
            command, _, parameters = message.partition(" ")
            ret.addCallback(self, parameters=parameters, user=user, channel=channel, d=d)
            self.reactor.callLater(0, ret.callback, "cmd_" + command)
            return ret
