from twisted.internet import reactor, defer
import urlparse
from base_plugin import BasePlugin, plugin_method

class URLFinder(BasePlugin):
    schemes = ['http://', 'https://']
    @plugin_method
    def privmsg(self, message, user, channel):
        for scheme in self.schemes:
            try:
                start = message.index(scheme)
            except ValueError:
                continue
            try:
                end = message.index(' ', start)
            except ValueError:
                url = message[start:]
                _, host, _, _, _, _ = urlparse.urlparse(url)
                start = len(message) - 1
            else:
                url = message[start:end]
                _, host, _, _, _, _ = urlparse.urlparse(url)
                start = end
            host, _, tld = host.rpartition('.')
            subdomain, _, domain = host.rpartition('.')
            reactor.callLater(0, self.parent.dispatch, 'handle_url', url)

class GenericHandler(BasePlugin):
    @plugin_method("low")
    def handle_url(self, url):
        result  = defer.waitForDeferred(self.parent.fetch_url(url))
        return result

