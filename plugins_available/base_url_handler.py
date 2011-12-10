from twisted.application import service
from twisted.internet import reactor
import urlparse, urllib
import BeautifulSoup

class URLFinder(object, service.Service):
    schemes = ['http://', 'https://']
    def privmsg(self, instance, user, channel, message):
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
                              'handle_url', user, channel, url)

class GenericHandler(service.Service):
    def handle_url(self, instance, user, channel, url):
        soup = BeautifulSoup.BeautifulSoup(self.parent.fetch_url(url))
        message = 'title: %s' % soup.title.string
        self.parent.reply(instance, user, channel, message, direct=False)

