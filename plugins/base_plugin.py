from twisted.application import service
from functools import wraps
import types

class BasePlugin(object, service.Service):
    def setServiceParent(self, parent):
        try:
            setUp = getattr(self, 'setUp')
        except AttributeError:
            pass
        else:
            if callable(setUp):
                setUp()
        return service.Service.setServiceParent(self, parent)
        
    def disownServiceParent(self):
        try:
            tearDown = getattr(self, 'tearDown')
        except AttributeError:
            pass
        else:
            if callable(tearDown):
                tearDown()
        return service.Service.disownServiceParent(self)

def plugin_method(arg=None):
    if callable(arg):
        return PluginMethod(function=arg)
    def wrapper(function):
        if arg is not None:
            return PluginMethod(function=function, priority=arg)
        else:
            return PluginMethod(function=function)
    return wrapper

def order_plugin_methods(method1, method2):
    priority1 = PluginMethod.priority_mapping[method1.priority]
    priority2 = PluginMethod.priority_mapping[method2.priority]
    if priority1 < priority2:
        return -1
    elif priority1 > priority2:
        return 1
    return cmp(id(method1), id(method2))


class PluginMethod(object):
    priority_mapping = {'high':0, 'normal':1, 'low':2}
    def __init__(self, function, priority='normal'):
        if priority not in self.priority_mapping:
            raise ValueError("%s is not an accepted priority" % priority)
        self.function = function
        self.priority = priority
        super(PluginMethod, self).__init__()
        
    def __call__(self, *args, **kwargs):
        return self.function(*args, **kwargs)

    def __get__(self, obj, objtype=None):
         "Simulate func_descr_get() in Objects/funcobject.c"
         return types.MethodType(self, obj, objtype)

