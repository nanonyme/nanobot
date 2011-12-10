from twisted.application import service
from twisted.internet import reactor
import urlparse, urllib
import BeautifulSoup

class URLFinder(service.Service):
    schemes = ['http://', 'https://']
    def privmsg(self, instance, user, channel, message, *args, **kwargs):
        d = None
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
            reactor.callLater(0, self.parent.delegate, instance,
                              'handle_url', url)

class GenericHandler(service.Service):
    def handle_url(self, instance, user, channel, *args, **kwargs):
        soup = BeautifulSoup.BeautifulSoup(self.parent.fetch_url(kwargs['url']))
        message = 'title: %s' % soup.title.string
        self.parent.reply(instance, user, channel, message)

