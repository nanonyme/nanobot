# -*- coding: utf-8 -*-
from twisted.trial import unittest
from twisted.internet import task
from plugin import PluginRegistry
import sys
import os

# Make plugins directory importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from plugins.example_plugin import ExamplePlugin, load


class MockProtocol:
    """Mock IRC protocol for testing plugin interactions."""
    def __init__(self):
        self.sent = []

    def msg(self, channel, message):
        self.sent.append((channel, message))


class ExamplePluginTests(unittest.TestCase):
    """Tests for the ExamplePlugin shipped plugin."""

    def setUp(self):
        self.clock = task.Clock()
        self.registry = PluginRegistry(self.clock, {})
        self.protocol = MockProtocol()

    def test_load_registers_privmsg_handler(self):
        """Test that load() registers a privmsg handler."""
        plugin = ExamplePlugin('example', self.registry, {})
        plugin.load()
        handlers = self.registry.get_handlers('privmsg')
        self.assertIn(plugin.on_privmsg, handlers)

    def test_load_registers_user_joined_handler(self):
        """Test that load() registers a user_joined handler."""
        plugin = ExamplePlugin('example', self.registry, {})
        plugin.load()
        handlers = self.registry.get_handlers('user_joined')
        self.assertIn(plugin.on_user_joined, handlers)

    def test_load_registers_signed_on_handler(self):
        """Test that load() registers a signed_on handler."""
        plugin = ExamplePlugin('example', self.registry, {})
        plugin.load()
        handlers = self.registry.get_handlers('signed_on')
        self.assertIn(plugin.on_signed_on, handlers)

    def test_on_user_joined_greets_when_enabled(self):
        """Test on_user_joined sends greeting when greet_users is True."""
        config = {'greet_users': True, 'greeting': 'Hello!'}
        plugin = ExamplePlugin('example', self.registry, config)
        plugin.on_user_joined(self.protocol, 'nick!user@host', '#test')
        self.assertEqual(len(self.protocol.sent), 1)
        channel, message = self.protocol.sent[0]
        self.assertEqual(channel, '#test')
        self.assertIn('nick', message)
        self.assertIn('Hello!', message)

    def test_on_user_joined_default_greeting(self):
        """Test on_user_joined uses default greeting when none configured."""
        config = {'greet_users': True}
        plugin = ExamplePlugin('example', self.registry, config)
        plugin.on_user_joined(self.protocol, 'nick!user@host', '#test')
        self.assertEqual(len(self.protocol.sent), 1)
        channel, message = self.protocol.sent[0]
        self.assertIn('Welcome!', message)

    def test_on_user_joined_no_greet_when_disabled(self):
        """Test on_user_joined does not greet when greet_users is False."""
        config = {'greet_users': False}
        plugin = ExamplePlugin('example', self.registry, config)
        plugin.on_user_joined(self.protocol, 'nick!user@host', '#test')
        self.assertEqual(len(self.protocol.sent), 0)

    def test_on_user_joined_no_greet_by_default(self):
        """Test on_user_joined does not greet by default."""
        plugin = ExamplePlugin('example', self.registry, {})
        plugin.on_user_joined(self.protocol, 'nick!user@host', '#test')
        self.assertEqual(len(self.protocol.sent), 0)

    def test_on_privmsg_responds_to_keyword(self):
        """Test on_privmsg responds when a keyword is found in the message."""
        config = {'keywords': ['hello'], 'response': 'Hey!'}
        plugin = ExamplePlugin('example', self.registry, config)
        plugin.on_privmsg(self.protocol, 'nick!user@host', '#test', 'hello world')
        self.assertEqual(len(self.protocol.sent), 1)
        channel, message = self.protocol.sent[0]
        self.assertEqual(channel, '#test')
        self.assertIn('nick', message)
        self.assertIn('Hey!', message)

    def test_on_privmsg_keyword_case_insensitive(self):
        """Test on_privmsg keyword matching is case-insensitive."""
        config = {'keywords': ['hello'], 'response': 'Hey!'}
        plugin = ExamplePlugin('example', self.registry, config)
        plugin.on_privmsg(self.protocol, 'nick!user@host', '#test', 'HELLO there')
        self.assertEqual(len(self.protocol.sent), 1)

    def test_on_privmsg_no_response_without_keyword(self):
        """Test on_privmsg does not respond when no keyword matches."""
        config = {'keywords': ['hello']}
        plugin = ExamplePlugin('example', self.registry, config)
        plugin.on_privmsg(self.protocol, 'nick!user@host', '#test', 'goodbye world')
        self.assertEqual(len(self.protocol.sent), 0)

    def test_on_privmsg_no_response_without_keywords_config(self):
        """Test on_privmsg does not respond when no keywords are configured."""
        plugin = ExamplePlugin('example', self.registry, {})
        plugin.on_privmsg(self.protocol, 'nick!user@host', '#test', 'hello world')
        self.assertEqual(len(self.protocol.sent), 0)

    def test_on_privmsg_default_response(self):
        """Test on_privmsg uses default response when none configured."""
        config = {'keywords': ['hello']}
        plugin = ExamplePlugin('example', self.registry, config)
        plugin.on_privmsg(self.protocol, 'nick!user@host', '#test', 'hello')
        self.assertEqual(len(self.protocol.sent), 1)
        _, message = self.protocol.sent[0]
        self.assertIn('I heard that!', message)

    def test_on_privmsg_only_responds_once_per_message(self):
        """Test on_privmsg only responds once even if multiple keywords match."""
        config = {'keywords': ['hello', 'world'], 'response': 'Hey!'}
        plugin = ExamplePlugin('example', self.registry, config)
        plugin.on_privmsg(self.protocol, 'nick!user@host', '#test', 'hello world')
        self.assertEqual(len(self.protocol.sent), 1)

    def test_module_load_function(self):
        """Test the module-level load() function creates and loads the plugin."""
        config = {
            'name': 'myplugin',
            'config': {'greet_users': True}
        }
        plugin = load(self.registry, config)
        self.assertIsInstance(plugin, ExamplePlugin)
        self.assertEqual(plugin.name, 'myplugin')
        self.assertEqual(plugin.config, {'greet_users': True})
        # Verify handlers were registered
        self.assertIn(plugin.on_privmsg, self.registry.get_handlers('privmsg'))

    def test_module_load_function_default_name(self):
        """Test the module-level load() function uses default name when not provided."""
        plugin = load(self.registry, {})
        self.assertEqual(plugin.name, 'example')

    def test_unload(self):
        """Test that unload() can be called without error."""
        plugin = ExamplePlugin('example', self.registry, {})
        plugin.load()
        plugin.unload()  # Should not raise
