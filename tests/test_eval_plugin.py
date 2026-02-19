# -*- coding: utf-8 -*-
"""Tests for the eval plugin."""
from twisted.trial import unittest
from twisted.internet import task
from plugin import PluginRegistry
from plugins.eval_plugin import EvalPlugin, load


class MockProtocol:
    """Mock IRC protocol for testing."""

    def __init__(self, nickname="testbot"):
        self.nickname = nickname
        self.sent = []

    def msg(self, target, text):
        self.sent.append((target, text))


class EvalPluginTests(unittest.TestCase):
    """Tests for EvalPlugin."""

    def setUp(self):
        self.clock = task.Clock()
        self.registry = PluginRegistry(self.clock, {})
        self.plugin = EvalPlugin('eval', self.registry)
        self.plugin.load()
        self.protocol = MockProtocol()

    def test_load_registers_privmsg_handler(self):
        """Test that load registers a privmsg handler."""
        handlers = self.registry.get_handlers('privmsg')
        self.assertEqual(len(handlers), 1)

    def test_eval_true_result(self):
        """Test !eval with a true boolean expression."""
        self.plugin.on_privmsg(self.protocol, "user!u@h", "#chan", "!eval foo:foo")
        self.assertEqual(len(self.protocol.sent), 1)
        target, text = self.protocol.sent[0]
        self.assertEqual(target, "#chan")
        self.assertIn("True", text)

    def test_eval_false_result(self):
        """Test !eval with a false boolean expression."""
        self.plugin.on_privmsg(self.protocol, "user!u@h", "#chan", "!eval bar:foo")
        self.assertEqual(len(self.protocol.sent), 1)
        target, text = self.protocol.sent[0]
        self.assertEqual(target, "#chan")
        self.assertIn("False", text)

    def test_eval_multiple_truths(self):
        """Test !eval with a comma-separated truth list."""
        self.plugin.on_privmsg(
            self.protocol, "user!u@h", "#chan", "!eval foo, bar:foo & bar"
        )
        self.assertEqual(len(self.protocol.sent), 1)
        _, text = self.protocol.sent[0]
        self.assertIn("True", text)

    def test_eval_invalid_expression(self):
        """Test !eval with an invalid expression returns an error message."""
        self.plugin.on_privmsg(self.protocol, "user!u@h", "#chan", "!eval :a&&b")
        self.assertEqual(len(self.protocol.sent), 1)
        _, text = self.protocol.sent[0]
        self.assertIn("Invalid token", text)

    def test_eval_private_message_replies_to_nick(self):
        """Test that !eval in a private message replies to the sender nick."""
        self.plugin.on_privmsg(
            self.protocol, "user!u@h", "testbot", "!eval foo:foo"
        )
        self.assertEqual(len(self.protocol.sent), 1)
        target, _ = self.protocol.sent[0]
        self.assertEqual(target, "user")

    def test_non_eval_command_ignored(self):
        """Test that non-!eval messages are ignored."""
        self.plugin.on_privmsg(self.protocol, "user!u@h", "#chan", "!join #other")
        self.assertEqual(len(self.protocol.sent), 0)

    def test_plain_message_ignored(self):
        """Test that plain messages (no command) are ignored."""
        self.plugin.on_privmsg(self.protocol, "user!u@h", "#chan", "hello world")
        self.assertEqual(len(self.protocol.sent), 0)

    def test_load_function(self):
        """Test the module-level load() function creates an EvalPlugin."""
        registry = PluginRegistry(self.clock, {})
        plugin = load(registry, {'name': 'eval', 'config': {}})
        self.assertIsInstance(plugin, EvalPlugin)
        self.assertEqual(plugin.name, 'eval')
