import twisted.python
import http_client
from zope.interface import implements
from twisted.application import service
from twisted.python import modules
from twisted.internet import defer
from twisted.python import log
from twisted.python import rebuild
plugins = modules.getModule('plugins_enabled')
def plugin_method(priority):
    def wrapper(function):
        return(plugins.load().PluginMethod(function=function,
                                           priority=priority))
    return wrapper

class Dispatcher(object):
    implements(service.IServiceCollection)
    def __init__(self):
        self.cache = http_client.HTTPClient("cache")
        self._services = dict()
        self._rehash()
    
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
        rebuild.updateInstance(self.cache)
        rebuild.updateInstance(self)
        BasePlugin = plugins.load().BasePlugin
        for iterator in plugins.walkModules():
            plugin_module = iterator.load()
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
        pass
        try:
            plugin_method = getattr(self, result)
        except AttributeError:
            pass
        else:
            if plugin_method is PluginMethod:
                yield plugin_method(**kwargs)
        for plugin in self:
            try:
                plugin_method = getattr(plugin, result)
            except AttributeError:
                pass
            else:
                if plugin_method is PluginMethod:
                    yield plugin_method(**kwargs)



