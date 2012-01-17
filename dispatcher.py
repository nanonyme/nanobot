import twisted.python
import http_client
from zope.interface import implements
from twisted.application import service
from twisted.python import modules
from twisted.internet import defer
from twisted.python import log
from twisted.python import rebuild
import yaml
from collections import defaultdict

plugins = modules.getModule('plugins')
def plugin_method(priority):
    def wrapper(function):
        return(plugins.load().PluginMethod(function=function,
                                           priority=priority))
    return wrapper

class Dispatcher(object):
    implements(service.IServiceCollection)
    def __init__(self, reactor, bot):
        self._reactor = reactor
        self._bot = bot
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
    def cmd_rehash(self, command, parameters, user, channel):
        return self._rehash()

    def _rehash(self):
        log.msg("Beginning rehash")
        _service = service
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
        return "Succesfully rehashed"

    @defer.inlineCallbacks
    def __call__(self, result, **kwargs):
        try:
            plugin_method = getattr(self, result)
        except AttributeError:
            pass
        else:
            if plugin_method is PluginMethod:
                yield defer.maybeDeferred(plugin_method(**kwargs))
        for plugin_method in sorted(self.command_table,
                                    cmp=plugins.compare_plugin_methods):
            yield defer.maybeDeferred(plugin_method(**kwargs))


    def privmsg(self, user, channel, message, d=None):
        cmd = False
        if message.startswith(context['nickname']):
            cmd = True
            pattern = r'(%s[^\w]+)' % context['nickname']
            message = re.sub(pattern, '', message)
            if cmd or context['channel'] == instance.nickname:
                admins = self.config['core'].get('admins', None)
                is_admin = False
                if not admins:
                    return d.callback({'message': "I'm free, I've no masters",
                                       'command': True})
                for admin in admins:
                    if re.match(admin, user):
                        is_admin = True
                        break
            if not is_admin:
                return d.callback({'message':'You are not an admin',
                                   'command':True})
            message = message.lower()
            command, _, parameters = message.partition(" ")
            ret = defer.Deferred()
            message = "cmd_" + command
            ret.addCallback((lambda result, message: message), message)
            #ret.addCallback(self.dispatch, user,
            self.delegate(instance, "cmd_" + command, user, channel,
                          parameters)
