from twisted.web import http, client
from twisted.internet import reactor, defer, protocol
import os, time
from collections import defaultdict
from urlparse import urlunparse
import StringIO

class ConnectionAborted(IOError):
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
                self.f.flush()
                raise ConnectionAborted("Error, maximum download limit %d" % self.limit)
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

    def fetch_url(self, url, limit=None):
        if not limit:
            limit = self.limit
        # Juggle around removing stuff from URL that we don't want
        scheme, netloc, path, _, query, _ = http.urlparse(url)
        url = urlunparse((scheme, netloc, path, '', query, ''))
        lock = self.cache[url]
        l = lock.acquire()
        d = defer.Deferred()
        path = create_path(self.cache_path, url)
        l.addCallback(self._start_download, url, path, limit, d)
        return d

    def _start_download(self, lock, url, path, limit, d):
        if not valid_item(lock, url):
            f = SizeLimitedFile(path, limit)
            dl = client.downloadPage(url, f,
                                    headers={'User-Agent': [self.version]})
            dl.addCallbacks(callback=self._cache_fetch,
                            callbackArgs=(path, lock, d),
                            errback=self._handle_error)
            dl.chainDeferred(d)
            lock.update(path, url)
        else:
           d.callback(self._cache_fetch(None, path, lock))

    def _handle_error(self, result):
        e = result.trap(ConnectionAborted)
        return "<html><head><title>%s</title></head></html>" % result.getErrorMessage()

    def _cache_fetch(self, result, path, lock, d):
        with open(path) as f:
            s = f.read()
            lock.release()
            return s
        

