from twisted.web import http, client
from twisted.internet import reactor, defer, protocol
import os, time
from collections import defaultdict
from urlparse import urlunparse
import StringIO

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


class SizeLimitedFile(object):
    def __init__(self, path, limit=None):
        self.f = open(path, "w")
        self.written = 0
        self.limit = limit

    def write(self, data):
        if self.limit is not None:
            if len(data) <= self.limit - self.written:
                self.f.write(data)
                self.written += len(data)
            elif self.written != self.limit:
                self.f.write(data[0:self.limit])
                self.written = self.limit
            else:
                raise IOError(self.written)
        else:
            self.f.write(data)

    def close(self):
        if not self.f.closed:
            self.f.close()


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
    def fetch_url(self, url, limit=None):
        if not limit:
            limit = self.limit
        # Juggle around removing stuff from URL that we don't want
        scheme, netloc, path, _, query, _ = http.urlparse(url)
        url = urlunparse((scheme, netloc, path, '', query, ''))
        lock = self.cache[url]
        yield lock.acquire()
        path = create_path(self.cache_path, url)
        if not valid_item(lock, url):
            f = SizeLimitedFile(path, limit)
            d = client.downloadPage(url, f,
                                    headers={'User-Agent': [self.version]})
            d.addCallback(self._cache_fetch, path, lock)
            yield d
            yield defer.returnValue(d.result)
            lock.update(path, url)
        else:
            yield defer.returnValue(self._cache_fetch(None, path, lock))


    def _cache_fetch(self, result, path, lock):
        with open(path) as f:
            s = f.read()
            lock.release()
            return s
        

