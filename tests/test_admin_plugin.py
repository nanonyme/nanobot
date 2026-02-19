# -*- coding: utf-8 -*-
"""Tests for the admin plugin."""
import sqlite3
import tempfile
import os
from twisted.trial import unittest
from twisted.internet import task
from plugin import PluginRegistry
from plugins.admin_plugin import AdminPlugin, load


class MockProcess:
    """Mock process transport for testing signalProcess."""

    def __init__(self):
        self.signals = []

    def signalProcess(self, signal):
        self.signals.append(signal)


class MockBot:
    """Mock bot for testing."""

    def __init__(self):
        self._proc = MockProcess()


class MockProtocol:
    """Mock IRC protocol for testing."""

    def __init__(self, nickname="testbot"):
        self.nickname = nickname
        self.joined = []
        self.left = []
        self.bot = MockBot()

    def join(self, channel, key=None):
        self.joined.append((channel, key))

    def leave(self, channel, reason=None):
        self.left.append((channel, reason))


def _make_db_with_superadmin(user_mask):
    """Create a temporary SQLite DB with a superadmin user."""
    db_file = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    db_file.close()
    schema = os.path.join(os.path.dirname(__file__), '..', 'create_db.sql')
    with sqlite3.connect(db_file.name) as conn:
        conn.executescript(open(schema).read())
        conn.execute("INSERT INTO Users (name) VALUES ('superuser')")
        conn.execute(
            "INSERT INTO Usermask (mask, uid) "
            "SELECT ?, Users.uid FROM Users WHERE name='superuser'",
            (user_mask,)
        )
        conn.execute("INSERT INTO Roles (name) VALUES ('superadmin')")
        conn.execute(
            "INSERT INTO UserRoles (uid, oid) "
            "SELECT Users.uid, Roles.oid FROM Users, Roles "
            "WHERE Users.name='superuser' AND Roles.name='superadmin'"
        )
    return db_file.name


class AdminPluginNoDbTests(unittest.TestCase):
    """Tests for AdminPlugin without a database configured."""

    def setUp(self):
        self.clock = task.Clock()
        self.registry = PluginRegistry(self.clock, {})
        self.plugin = AdminPlugin('admin', self.registry)
        self.plugin.load()
        self.protocol = MockProtocol()

    def test_load_registers_privmsg_handler(self):
        """Test that load registers a privmsg handler."""
        handlers = self.registry.get_handlers('privmsg')
        self.assertEqual(len(handlers), 1)

    def test_non_admin_command_ignored(self):
        """Test that non-admin commands are ignored."""
        self.plugin.on_privmsg(self.protocol, "user!u@h", "#chan", "!eval foo:foo")
        self.assertEqual(len(self.protocol.joined), 0)
        self.assertEqual(len(self.protocol.left), 0)

    def test_plain_message_ignored(self):
        """Test that plain messages are ignored."""
        self.plugin.on_privmsg(self.protocol, "user!u@h", "#chan", "hello world")
        self.assertEqual(len(self.protocol.joined), 0)

    def test_join_without_db_no_action(self):
        """Test !join without a DB configured does nothing (no roles)."""
        self.plugin.on_privmsg(
            self.protocol, "user!u@h", "#chan", "!join #newchan"
        )
        self.assertEqual(len(self.protocol.joined), 0)

    def test_leave_without_db_no_action(self):
        """Test !leave without a DB configured does nothing (no roles)."""
        self.plugin.on_privmsg(
            self.protocol, "user!u@h", "#chan", "!leave #chan"
        )
        self.assertEqual(len(self.protocol.left), 0)

    def test_reincarnate_without_db_no_action(self):
        """Test !reincarnate without a DB configured does nothing."""
        self.plugin.on_privmsg(
            self.protocol, "user!u@h", "#chan", "!reincarnate"
        )
        self.assertEqual(len(self.protocol.bot._proc.signals), 0)

    def test_load_function(self):
        """Test the module-level load() function creates an AdminPlugin."""
        registry = PluginRegistry(self.clock, {})
        plugin = load(registry, {'name': 'admin', 'config': {}})
        self.assertIsInstance(plugin, AdminPlugin)
        self.assertEqual(plugin.name, 'admin')


class AdminPluginWithDbTests(unittest.TestCase):
    """Tests for AdminPlugin with a real SQLite database."""

    def setUp(self):
        self.clock = task.Clock()
        self.superadmin_mask = "superuser!u@h"
        try:
            self.db_path = _make_db_with_superadmin(self.superadmin_mask)
        except Exception:
            self.db_path = None
            self.skipTest("Could not create test database")

        config = {'core': {'db': self.db_path}}
        self.registry = PluginRegistry(self.clock, config)
        self.plugin = AdminPlugin('admin', self.registry)
        self.plugin.load()
        self.protocol = MockProtocol()

    def tearDown(self):
        if self.db_path and os.path.exists(self.db_path):
            os.unlink(self.db_path)

    def test_join_as_superadmin(self):
        """Test !join executed by a superadmin joins the channel."""
        self.plugin.on_privmsg(
            self.protocol, self.superadmin_mask, "#chan", "!join #newchan"
        )
        self.assertEqual(len(self.protocol.joined), 1)
        self.assertEqual(self.protocol.joined[0], ("#newchan", None))

    def test_join_with_password_as_superadmin(self):
        """Test !join with password executed by a superadmin."""
        self.plugin.on_privmsg(
            self.protocol, self.superadmin_mask, "#chan", "!join #secret pass123"
        )
        self.assertEqual(len(self.protocol.joined), 1)
        self.assertEqual(self.protocol.joined[0], ("#secret", "pass123"))

    def test_leave_as_superadmin(self):
        """Test !leave executed by a superadmin leaves the channel."""
        self.plugin.on_privmsg(
            self.protocol, self.superadmin_mask, "#chan", "!leave #chan"
        )
        self.assertEqual(len(self.protocol.left), 1)
        self.assertEqual(self.protocol.left[0], ("#chan", None))

    def test_leave_with_reason_as_superadmin(self):
        """Test !leave with reason executed by a superadmin."""
        self.plugin.on_privmsg(
            self.protocol, self.superadmin_mask, "#chan", "!leave #chan goodbye"
        )
        self.assertEqual(len(self.protocol.left), 1)
        self.assertEqual(self.protocol.left[0], ("#chan", "goodbye"))

    def test_reincarnate_as_superadmin(self):
        """Test !reincarnate executed by a superadmin kills the app process."""
        self.plugin.on_privmsg(
            self.protocol, self.superadmin_mask, "#chan", "!reincarnate"
        )
        self.assertEqual(self.protocol.bot._proc.signals, ['KILL'])

    def test_join_as_non_superadmin(self):
        """Test !join executed by a non-admin does nothing."""
        self.plugin.on_privmsg(
            self.protocol, "nobody!u@h", "#chan", "!join #newchan"
        )
        self.assertEqual(len(self.protocol.joined), 0)

    def test_reincarnate_as_non_superadmin(self):
        """Test !reincarnate by a non-admin does not kill the process."""
        self.plugin.on_privmsg(
            self.protocol, "nobody!u@h", "#chan", "!reincarnate"
        )
        self.assertEqual(len(self.protocol.bot._proc.signals), 0)
