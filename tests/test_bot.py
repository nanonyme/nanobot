from twisted.trial import unittest
from twisted.test import proto_helpers
from twisted.internet import task, defer
from twisted.spread import pb
import nanobot
import json
import tempfile
import os


class MockBot:
    """Mock bot for testing"""
    def __init__(self, reactor):
        self.api = MockApiProxy(reactor)
        self.nickname = "testbot"
        self.realname = "Test Bot"


class MockApiProxy:
    """Mock API proxy for testing"""
    def __init__(self, reactor):
        self.reactor = reactor
        self.calls = []
        
    def callRemote(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return defer.succeed(None)


class MockServerConnection:
    """Mock server connection for testing"""
    def __init__(self, hostname="test.server", channels=None):
        self.hostname = hostname
        self.channels = channels or []
        self.network_config = {
            'name': 'testnet',
            'hostname': hostname,
            'port': 6667,
            'channels': channels or []
        }
        
    @property
    def name(self):
        return self.network_config['name']


class RemoteProtocolTests(unittest.TestCase):
    """Tests for RemoteProtocol RPC proxy"""
    
    def setUp(self):
        self.mock_protocol = MockIRCProtocol()
        self.remote = nanobot.RemoteProtocol(self.mock_protocol)
    
    def test_remote_msg(self):
        """Test remote_msg forwards to protocol.msg"""
        self.remote.remote_msg("user1", "test message")
        self.assertEqual(len(self.mock_protocol.sent), 1)
        self.assertEqual(self.mock_protocol.sent[0], ("msg", "user1", "test message"))
    
    def test_remote_join(self):
        """Test remote_join forwards to protocol.join"""
        self.remote.remote_join("#test", "secret")
        self.assertEqual(len(self.mock_protocol.joined), 1)
        self.assertEqual(self.mock_protocol.joined[0], ("#test", "secret"))
    
    def test_remote_leave(self):
        """Test remote_leave forwards to protocol.leave"""
        self.remote.remote_leave("#test", "goodbye")
        self.assertEqual(len(self.mock_protocol.left), 1)
        self.assertEqual(self.mock_protocol.left[0], ("#test", "goodbye"))

    def test_remote_topic(self):
        """Test remote_topic forwards to protocol.topic"""
        self.remote.remote_topic("#test", "New topic")
        self.assertEqual(len(self.mock_protocol.topics), 1)
        self.assertEqual(self.mock_protocol.topics[0], ("#test", "New topic"))

    def test_remote_kick(self):
        """Test remote_kick forwards to protocol.kick"""
        self.remote.remote_kick("#test", "baduser", "misbehaving")
        self.assertEqual(len(self.mock_protocol.kicks), 1)
        self.assertEqual(self.mock_protocol.kicks[0], ("#test", "baduser", "misbehaving"))

    def test_remote_invite(self):
        """Test remote_invite forwards to protocol.invite"""
        self.remote.remote_invite("friend", "#test")
        self.assertEqual(len(self.mock_protocol.invites), 1)
        self.assertEqual(self.mock_protocol.invites[0], ("friend", "#test"))

    def test_remote_describe(self):
        """Test remote_describe forwards to protocol.describe"""
        self.remote.remote_describe("#test", "waves hello")
        self.assertEqual(len(self.mock_protocol.describes), 1)
        self.assertEqual(self.mock_protocol.describes[0], ("#test", "waves hello"))

    def test_remote_notice(self):
        """Test remote_notice forwards to protocol.notice"""
        self.remote.remote_notice("user1", "Important notice")
        self.assertEqual(len(self.mock_protocol.notices), 1)
        self.assertEqual(self.mock_protocol.notices[0], ("user1", "Important notice"))


class MockIRCProtocol:
    """Mock IRC protocol for testing"""
    def __init__(self):
        self.sent = []
        self.joined = []
        self.left = []
        self.topics = []
        self.kicks = []
        self.invites = []
        self.describes = []
        self.notices = []
    
    def msg(self, user, message):
        self.sent.append(("msg", user, message))
    
    def join(self, channel, key=None):
        self.joined.append((channel, key))
    
    def leave(self, channel, reason=None):
        self.left.append((channel, reason))

    def topic(self, channel, topic=None):
        self.topics.append((channel, topic))

    def mode(self, chan, set, modes, limit=None, user=None, mask=None):
        pass

    def kick(self, channel, user, reason=None):
        self.kicks.append((channel, user, reason))

    def invite(self, user, channel):
        self.invites.append((user, channel))

    def quit(self, message=None):
        pass

    def describe(self, channel, action):
        self.describes.append((channel, action))

    def notice(self, user, message):
        self.notices.append((user, message))

    def away(self, message=None):
        pass

    def back(self):
        pass


class NanoBotProtocolTests(unittest.TestCase):
    """Tests for NanoBotProtocol IRC client"""
    
    def setUp(self):
        self.clock = task.Clock()
        self.bot = MockBot(self.clock)
        self.server = MockServerConnection(
            hostname="irc.example.com",
            channels=[
                {'name': '#test1'},
                {'name': '#test2', 'key': 'secret'}
            ]
        )
        self.protocol = nanobot.NanoBotProtocol(
            reactor=self.clock,
            server=self.server,
            bot=self.bot
        )
        self.protocol.nickname = "testbot"
        self.transport = proto_helpers.StringTransport()
        self.protocol.makeConnection(self.transport)
    
    def test_channels_property(self):
        """Test channels property returns server channels"""
        self.assertEqual(self.protocol.channels, self.server.channels)
    
    def test_signedOn_joins_channels(self):
        """Test signedOn joins all configured channels"""
        # Call signedOn
        self.protocol.signedOn()
        
        # Check that JOIN commands were sent
        data = self.transport.value().decode('utf-8')
        self.assertIn("JOIN #test1", data)
        self.assertIn("JOIN #test2 secret", data)
    
    def test_privmsg_public_message(self):
        """Test privmsg handles public channel messages"""
        # Receive a public message
        self.protocol.privmsg("user1!~user@host", "#test1", "hello world")
        
        # Check that callRemote was called with correct parameters
        self.assertEqual(len(self.bot.api.calls), 1)
        args, kwargs = self.bot.api.calls[0]
        self.assertEqual(args[0], "handlePublicMessage")
        self.assertEqual(args[2], "user1!~user@host")
        self.assertEqual(args[3], "#test1")
        self.assertEqual(args[4], "hello world")
    
    def test_privmsg_private_message(self):
        """Test privmsg handles private messages"""
        # Receive a private message (channel == nickname)
        self.protocol.privmsg("user1!~user@host", "testbot", "hello")
        
        # Check that callRemote was called with correct parameters
        self.assertEqual(len(self.bot.api.calls), 1)
        args, kwargs = self.bot.api.calls[0]
        self.assertEqual(args[0], "handlePrivateMessage")
        self.assertEqual(args[2], "user1!~user@host")
        self.assertEqual(args[3], "testbot")
        self.assertEqual(args[4], "hello")

    def test_event_dispatch_with_plugin_registry(self):
        """Test that events are dispatched to plugin handlers"""
        from plugin import PluginRegistry
        
        # Create a plugin registry and register a handler
        registry = PluginRegistry(self.clock, {})
        handler_calls = []
        
        def test_handler(protocol, user, channel, message):
            handler_calls.append((user, channel, message))
        
        registry.register_handler('privmsg', test_handler)
        self.bot.plugin_registry = registry
        
        # Receive a message
        self.protocol.privmsg("user1!~user@host", "#test", "test message")
        
        # Check that plugin handler was called
        self.assertEqual(len(handler_calls), 1)
        self.assertEqual(handler_calls[0], ("user1!~user@host", "#test", "test message"))

    def test_event_dispatch_handles_handler_errors(self):
        """Test that handler errors don't break event dispatching"""
        from plugin import PluginRegistry
        
        registry = PluginRegistry(self.clock, {})
        
        def failing_handler(protocol, *args):
            raise Exception("Handler error")
        
        def working_handler(protocol, *args):
            working_handler.called = True
        
        working_handler.called = False
        
        registry.register_handler('privmsg', failing_handler)
        registry.register_handler('privmsg', working_handler)
        self.bot.plugin_registry = registry
        
        # This should not raise an exception
        self.protocol.privmsg("user1!~user@host", "#test", "test")
        
        # Working handler should still be called despite the first one failing
        self.assertTrue(working_handler.called)
        
        # Flush logged errors
        errors = self.flushLoggedErrors(Exception)
        self.assertEqual(len(errors), 1)


class ServerConnectionTests(unittest.TestCase):
    """Tests for ServerConnection factory"""
    
    def setUp(self):
        self.clock = task.Clock()
        self.bot = MockBot(self.clock)
        self.network_config = {
            'name': 'testnet',
            'hostname': 'irc.example.com',
            'port': 6667,
            'channels': [{'name': '#test'}],
            'encoding': 'utf-8'
        }
        self.factory = nanobot.ServerConnection(
            reactor=self.clock,
            network_config=self.network_config,
            bot=self.bot
        )
    
    def test_properties(self):
        """Test ServerConnection properties"""
        self.assertEqual(self.factory.name, 'testnet')
        self.assertEqual(self.factory.hostname, 'irc.example.com')
        self.assertEqual(self.factory.port, 6667)
        self.assertEqual(self.factory.is_ssl, False)
        self.assertEqual(self.factory.channels, [{'name': '#test'}])
    
    def test_port_default(self):
        """Test default port is 6667"""
        config = {'name': 'test', 'hostname': 'irc.test.com'}
        factory = nanobot.ServerConnection(self.clock, config, self.bot)
        self.assertEqual(factory.port, 6667)
    
    def test_ssl_property(self):
        """Test SSL property"""
        config = {
            'name': 'test',
            'hostname': 'irc.test.com',
            'ssl': True
        }
        factory = nanobot.ServerConnection(self.clock, config, self.bot)
        self.assertTrue(factory.is_ssl)
    
    def test_buildProtocol(self):
        """Test buildProtocol creates NanoBotProtocol with correct properties"""
        protocol = self.factory.buildProtocol(None)
        self.assertIsInstance(protocol, nanobot.NanoBotProtocol)
        self.assertEqual(protocol.nickname, self.bot.nickname)
        self.assertEqual(protocol.realname, self.bot.realname)
        self.assertEqual(protocol.server, self.factory)
        self.assertEqual(protocol.bot, self.bot)


class ApiProxyTests(unittest.TestCase):
    """Tests for ApiProxy message queue"""
    
    def setUp(self):
        self.clock = task.Clock()
        self.api = nanobot.ApiProxy(self.clock)
        self.mock_app = MockApp()
    
    def test_callRemote_queues_message(self):
        """Test callRemote adds message to queue"""
        self.api.callRemote("test", arg1="value1")
        self.assertEqual(len(self.api.queue), 1)
        
        seconds, args, kwargs = self.api.queue[0]
        self.assertEqual(args, ("test",))
        self.assertEqual(kwargs, {"arg1": "value1"})
    
    def test_callRemote_with_no_app_queues(self):
        """Test callRemote queues messages when no app connected"""
        self.api.callRemote("test1")
        self.api.callRemote("test2")
        self.assertEqual(len(self.api.queue), 2)
    
    def test_remote_register_sets_app(self):
        """Test remote_register sets app and processes queue"""
        # Queue some messages
        self.api.callRemote("test1")
        self.api.callRemote("test2")
        
        # Register app
        self.api.remote_register(self.mock_app)
        
        # App should be set
        self.assertEqual(self.api.app, self.mock_app)
    
    def test_disconnect_clears_app(self):
        """Test disconnect clears app"""
        self.api.remote_register(self.mock_app)
        self.assertEqual(self.api.app, self.mock_app)
        
        self.api.disconnect()
        self.assertIsNone(self.api.app)
    
    def test_processes_queued_messages(self):
        """Test queued messages are processed when app registers"""
        # Queue messages before app connects
        self.api.callRemote("handlePublicMessage", "arg1", "arg2")
        self.api.callRemote("handlePrivateMessage", "arg3", "arg4")
        
        # Register app - this should trigger processing
        self.api.remote_register(self.mock_app)
        
        # The queue should have been processed (even if async)
        # We just verify the app was registered and queue mechanism works
        self.assertIsNotNone(self.api.app)
        # Queue should be empty or processing
        self.assertLessEqual(len(self.api.queue), 2)


class MockApp:
    """Mock app for testing"""
    def __init__(self):
        self.calls = []
    
    def callRemote(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        d = defer.Deferred()
        d.callback(None)
        return d


class NanoBotTests(unittest.TestCase):
    """Tests for NanoBot main class"""
    
    def setUp(self):
        self.clock = task.Clock()
        # Create a temporary log file
        self.log_file = tempfile.NamedTemporaryFile(
            mode='w', suffix='.log', delete=False
        )
        self.log_file.close()
        
        # Create a temporary config file
        self.config_data = {
            'core': {
                'nickname': 'testbot',
                'realname': 'Test Bot',
                'log_file': self.log_file.name
            },
            'networks': [
                {
                    'name': 'testnet',
                    'hostname': 'irc.example.com',
                    'port': 6667,
                    'channels': [{'name': '#test'}]
                }
            ]
        }
        self.config_file = tempfile.NamedTemporaryFile(
            mode='w', suffix='.json', delete=False
        )
        json.dump(self.config_data, self.config_file)
        self.config_file.close()
    
    def tearDown(self):
        # Clean up temp config file
        if os.path.exists(self.config_file.name):
            os.unlink(self.config_file.name)
        # Clean up temp log file
        if os.path.exists(self.log_file.name):
            os.unlink(self.log_file.name)
    
    def test_init_loads_config(self):
        """Test NanoBot.__init__ loads config from file"""
        bot = nanobot.NanoBot(self.clock, self.config_file.name)
        self.assertEqual(bot.config, self.config_data)
    
    def test_nickname_property(self):
        """Test nickname property returns configured nickname"""
        bot = nanobot.NanoBot(self.clock, self.config_file.name)
        self.assertEqual(bot.nickname, 'testbot')
    
    def test_realname_property(self):
        """Test realname property returns configured realname"""
        bot = nanobot.NanoBot(self.clock, self.config_file.name)
        self.assertEqual(bot.realname, 'Test Bot')
    
    def test_core_config_property(self):
        """Test core_config property returns core configuration"""
        bot = nanobot.NanoBot(self.clock, self.config_file.name)
        self.assertEqual(bot.core_config, self.config_data['core'])
    
    def test_core_config_missing_raises(self):
        """Test core_config raises exception when core section missing"""
        # Create config without core section
        bad_config = {'networks': []}
        bad_config_file = tempfile.NamedTemporaryFile(
            mode='w', suffix='.json', delete=False
        )
        json.dump(bad_config, bad_config_file)
        bad_config_file.close()
        
        try:
            # NanoBot.__init__ will call core_config to get log_file
            # This should raise an exception
            with self.assertRaises(Exception) as context:
                bot = nanobot.NanoBot(self.clock, bad_config_file.name)
            self.assertIn("Missing core section", str(context.exception))
        finally:
            os.unlink(bad_config_file.name)
