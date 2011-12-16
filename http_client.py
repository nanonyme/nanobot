from twisted.web import http, client
from twisted.internet import reactor, defer, protocol
import os, time
from collections import defaultdict
from urlparse import urlunparse

class ConnectionAborted(object):
    pass

class CacheItem(defer.DeferredLock):
    def __init__(self):
        defer.DeferredLock.__init__(self)
        self.path = None
        self.timestamp = None
        self.url = None

    def update(self, path, url):
        self.path = path
        self.url = url
        self.timestamp = time.time()

class CachePrinter(protocol.Protocol):
    def __init__(self, path, limit, finish):
        self.path = path
        self.f = open(self.path, "w")
        self.limit = limit
        self.finish = finish

    def dataReceived(self, bytes):
        len_bytes = len(bytes)
        if self.limit - len_bytes >= 0:
            self.f.write(bytes)
            self.limit -= len_bytes
        elif self.limit > 0:
            self.f.write(bytes[:self.limit])
            self.limit = 0
        else:
            raise ConnectionAborted("File size safety limit reached")

    def connectionLost(self, reason):
        self.f.close()
        self.finish.callback(None)
    

def create_path(prefix, s):
    s = str(hash(s)).encode("base64").rstrip()
    return os.path.join(prefix, s)

def valid_item(item, url):
    if item.timestamp is None or time.time() - lock.timestamp > 5*60:
        return False
    elif item.url is None or item.url != url:
        return False
    else:
        return True


class HTTPClient(object):
    version = 'Nanobot'
    limit = 5*1024**2
    def __init__(self, cache_path):
        self.cache_path = cache_path
        if not os.path.isdir(self.cache_path):
            os.makedirs(self.cache_path)
        self.cache = defaultdict(CacheItem)
        self.agent = client.Agent(reactor)

    @defer.inlineCallbacks
    def fetch_url(self, url):
        # Juggle around removing stuff from URL that we don't want
        scheme, netloc, path, _, query, _ = http.urlparse(url)
        url = urlunparse((scheme, netloc, path, '', query, ''))
        lock = self.cache[url]
        yield lock.acquire()
        path = create_path(self.cache_path, url)
        if not valid_item(lock, url):
            d = self.agent.request('GET', url,
                                   http.Headers({'User-Agent': [self.version]}),
                                   None)
            d.addCallback(self._trigger_fetch, path, self.limit, lock)
            yield d
            yield defer.returnValue(d.result)
            lock.update(path, url)
        else:
            yield defer.returnValue(self._cache_fetch(None, path, lock))


    def _trigger_fetch(self, result, path, limit, lock):
        d = defer.Deferred()
        result.deliverBody(CachePrinter(path, limit, d))
        d.addCallback(self._cache_fetch, path, lock)
        return d

    def _cache_fetch(self, result, path, lock):
        with open(path) as f:
            s = f.read()
            lock.release()
            return s
        

