from twisted.application import service
from functools import wraps

class BasePlugin(object, service.Service):
    def __init__(self):
        for key in dir(self):
            if key.startswith("__") and key.endswith("__"):
                continue
            item = getattr(self, key)
            if isinstance(item, PluginMethod):
                continue
            setattr(self, key, PluginMethod(item, 'normal'))

class PluginWrapper(object):
    def __init__(self, priority='normal'):
        self.priority = priority
        super(PluginWrapper, self).__init__()

    def __call__(self, function):
        return PluginMethod(function, self.priority)

class  PluginMethod(object):
    priority_mapping = {'high':0, 'normal':1, 'low':2}
    def __init__(self, function, priority):
        if priority not in self.priority_mapping:
            raise ValueError("%s is not an accepted priority" % priority)
        self.function = function
        self.priority = priority
        super(PluginMethod, self).__init__()
        
    @property
    def num_priority(self):
        return self.priority_mapping[self.priority]

    def __call__(self, *args, **kwargs):
        return self.function(*args, **kwargs)


    def __lt__(self, other):
        if self.num_priority < other.num_priority:
            return True
        return False

    def __eq__(self, other):
        if self.num_priority != other.num_priority:
            return False
        if str(self) != str(other):
            return False
        return True

    def __gt__(self, other):
        if self.num_priority > other.num_priority:
            return True
        return False

    def __le__(self, other):
        return self.__lt__(other) or self.__eq__(other)

    def __ge__(self, other):
        return self.__gt__(other) or self.__eq__(other)




