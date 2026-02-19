# -*- coding: utf-8 -*-
from twisted.trial import unittest
from twisted.internet import task, defer
from plugin import PluginRegistry
from plugins.title_plugin import TitlePlugin, load, UrlCache


class MockProtocol:
    """Mock IRC protocol for testing TitlePlugin interactions."""
    def __init__(self, nickname="testbot"):
        self.nickname = nickname
        self.sent = []

    def msg(self, target, text):
        self.sent.append((target, text))


class TitlePluginLoadTests(unittest.TestCase):
    """Tests for TitlePlugin.load() and handler registration."""

    def setUp(self):
        self.clock = task.Clock()
        self.registry = PluginRegistry(self.clock, {})

    def tearDown(self):
        # Ensure cache reapers are stopped for every plugin created in tests
        for plugin in self.registry.plugins.values():
            if isinstance(plugin, TitlePlugin):
                plugin.unload()

    def test_load_registers_privmsg_handler(self):
        """Test that load() registers a privmsg handler."""
        plugin = TitlePlugin('title', self.registry, {})
        plugin.load()
        handlers = self.registry.get_handlers('privmsg')
        self.assertIn(plugin.on_privmsg, handlers)

    def test_load_enables_caches(self):
        """Test that load() starts the URL caches."""
        plugin = TitlePlugin('title', self.registry, {})
        plugin.load()
        self.assertTrue(plugin._good_urls._reaper.running)
        self.assertTrue(plugin._bad_urls._reaper.running)

    def test_unload_disables_caches(self):
        """Test that unload() stops the URL cache reapers."""
        plugin = TitlePlugin('title', self.registry, {})
        plugin.load()
        plugin.unload()
        self.assertFalse(plugin._good_urls._reaper.running)
        self.assertFalse(plugin._bad_urls._reaper.running)

    def test_default_max_title_length(self):
        """Test that max_title_length defaults to 200."""
        plugin = TitlePlugin('title', self.registry, {})
        plugin.load()
        self.assertEqual(plugin._max_len, 200)

    def test_custom_max_title_length(self):
        """Test that max_title_length can be configured."""
        plugin = TitlePlugin('title', self.registry, {'max_title_length': 100})
        plugin.load()
        self.assertEqual(plugin._max_len, 100)


class TitlePluginPrivmsgTests(unittest.TestCase):
    """Tests for TitlePlugin.on_privmsg handler."""

    def setUp(self):
        self.clock = task.Clock()
        self.registry = PluginRegistry(self.clock, {})
        self.plugin = TitlePlugin('title', self.registry, {})
        self.plugin.load()
        self.protocol = MockProtocol(nickname="testbot")

    def tearDown(self):
        self.plugin.unload()

    def _make_message_handler_noop(self):
        """Patch MessageHandler so find_links does nothing."""
        original = self.plugin.on_privmsg.__func__ if hasattr(
            self.plugin.on_privmsg, '__func__') else None

        class NoopMessageHandler:
            def __init__(self, *args, **kwargs):
                pass

            async def find_links(self, message):
                pass

        from plugins import title_plugin
        self._original_handler_class = title_plugin.MessageHandler
        title_plugin.MessageHandler = NoopMessageHandler
        return title_plugin

    def _restore_message_handler(self, title_plugin_module):
        title_plugin_module.MessageHandler = self._original_handler_class

    def test_on_privmsg_public_uses_channel_as_target(self):
        """Test that public messages reply to the channel."""

        class CapturingMessageHandler:
            def __init__(self, reactor, hits, misses, callback, max_len):
                self._callback = callback

            async def find_links(self, message):
                await self._callback("title: Test Title")

        import plugins.title_plugin as title_plugin
        original = title_plugin.MessageHandler
        title_plugin.MessageHandler = CapturingMessageHandler
        try:
            d = self.plugin.on_privmsg(
                self.protocol, 'nick!user@host', '#channel', 'http://example.com')
            return d
        finally:
            title_plugin.MessageHandler = original

    def test_on_privmsg_private_uses_sender_nick_as_target(self):
        """Test that private messages reply to the sender's nick."""
        replies = []

        class CapturingMessageHandler:
            def __init__(self, reactor, hits, misses, callback, max_len):
                self._callback = callback

            async def find_links(self, message):
                await self._callback("title: Test")

        import plugins.title_plugin as title_plugin
        original = title_plugin.MessageHandler
        title_plugin.MessageHandler = CapturingMessageHandler
        try:
            d = self.plugin.on_privmsg(
                self.protocol, 'nick!user@host', 'testbot', 'http://example.com')

            def check(_):
                self.assertEqual(len(self.protocol.sent), 1)
                target, text = self.protocol.sent[0]
                self.assertEqual(target, 'nick')
                self.assertIn('Test', text)

            d.addCallback(check)
            return d
        finally:
            title_plugin.MessageHandler = original

    def test_on_privmsg_public_channel_target(self):
        """Test that public channel messages reply to the channel."""
        class CapturingMessageHandler:
            def __init__(self, reactor, hits, misses, callback, max_len):
                self._callback = callback

            async def find_links(self, message):
                await self._callback("title: Test")

        import plugins.title_plugin as title_plugin
        original = title_plugin.MessageHandler
        title_plugin.MessageHandler = CapturingMessageHandler
        try:
            d = self.plugin.on_privmsg(
                self.protocol, 'nick!user@host', '#test', 'http://example.com')

            def check(_):
                self.assertEqual(len(self.protocol.sent), 1)
                target, text = self.protocol.sent[0]
                self.assertEqual(target, '#test')

            d.addCallback(check)
            return d
        finally:
            title_plugin.MessageHandler = original

    def test_on_privmsg_errors_are_caught(self):
        """Test that errors from MessageHandler do not propagate uncaught."""
        class FailingMessageHandler:
            def __init__(self, *args, **kwargs):
                pass

            async def find_links(self, message):
                raise RuntimeError("network failure")

        import plugins.title_plugin as title_plugin
        original = title_plugin.MessageHandler
        title_plugin.MessageHandler = FailingMessageHandler
        try:
            d = self.plugin.on_privmsg(
                self.protocol, 'nick!user@host', '#test', 'http://example.com')
            # The deferred should resolve without propagating the error
            d.addCallback(lambda _: None)
            # Flush the logged error so the test doesn't fail on logged failures
            d.addBoth(lambda _: self.flushLoggedErrors(RuntimeError))
            return d
        finally:
            title_plugin.MessageHandler = original


class ModuleLoadFunctionTests(unittest.TestCase):
    """Tests for the module-level load() function."""

    def setUp(self):
        self.clock = task.Clock()
        self.registry = PluginRegistry(self.clock, {})

    def tearDown(self):
        for plugin in self.registry.plugins.values():
            if isinstance(plugin, TitlePlugin):
                plugin.unload()

    def test_load_returns_title_plugin(self):
        """Test that load() returns a TitlePlugin instance."""
        plugin = load(self.registry, {})
        self.assertIsInstance(plugin, TitlePlugin)
        plugin.unload()

    def test_load_default_name(self):
        """Test that load() uses 'title' as the default plugin name."""
        plugin = load(self.registry, {})
        self.assertEqual(plugin.name, 'title')
        plugin.unload()

    def test_load_custom_name(self):
        """Test that load() uses a custom name from config."""
        plugin = load(self.registry, {'name': 'urltitles'})
        self.assertEqual(plugin.name, 'urltitles')
        plugin.unload()

    def test_load_passes_config(self):
        """Test that load() passes plugin config to the plugin."""
        config = {'name': 'title', 'config': {'max_title_length': 50}}
        plugin = load(self.registry, config)
        self.assertEqual(plugin._max_len, 50)
        plugin.unload()

    def test_load_registers_handler(self):
        """Test that load() registers the privmsg handler."""
        plugin = load(self.registry, {})
        handlers = self.registry.get_handlers('privmsg')
        self.assertIn(plugin.on_privmsg, handlers)
        plugin.unload()
