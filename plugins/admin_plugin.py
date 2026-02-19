# -*- coding: utf-8 -*-
"""
Admin plugin for nanobot.

Handles admin commands: !reincarnate, !join, !leave.
Role-based access is resolved via the configured SQLite database.
"""
import sqlite3
from plugin import Plugin
from twisted.logger import Logger

log = Logger()

_user_query = (
    "select roles.name from roles where roles.oid in "
    "(select userroles.oid from (users natural join usermask)"
    "natural join userroles where usermask.mask=?);"
)


class AdminPlugin(Plugin):
    """Plugin that handles admin commands with role-based access control."""

    def load(self):
        """Load the plugin and register handlers."""
        log.info(f"Loading {self.name} plugin")
        self._db = self.registry.config.get('core', {}).get('db')
        self.register_handler('privmsg', self.on_privmsg)
        log.info(f"{self.name} plugin loaded successfully")

    def _resolve_roles(self, user):
        """
        Resolve roles for a user from the database.

        Args:
            user: User mask (nick!user@host)

        Returns:
            List of role names for the user
        """
        if not self._db:
            return []
        with sqlite3.connect(self._db) as conn:
            cur = conn.cursor()
            res = cur.execute(_user_query, (user,))
            return [role[0] for role in res.fetchall()]

    def on_privmsg(self, protocol, user, channel, message):
        """
        Handle privmsg events, responding to admin commands.

        Args:
            protocol: NanoBotProtocol instance
            user: User who sent the message (nick!user@host)
            channel: Channel name or bot nickname (for private messages)
            message: Message text
        """
        if not message.startswith("!"):
            return

        command, _, suffix = message[1:].partition(" ")
        if command not in ("reincarnate", "join", "leave"):
            return

        roles = self._resolve_roles(user)
        if "ignored" in roles:
            return

        if command == "reincarnate":
            if "superadmin" in roles:
                log.info("Restarting app")
                if protocol.bot._proc:
                    protocol.bot._proc.signalProcess('KILL')
            else:
                log.info("User {user} tried to do code reload", user=user)
        elif command == "join":
            chan, _, password = suffix.partition(" ")
            if not password:
                password = None
            if "superadmin" in roles:
                if password:
                    log.info(f"Joining {chan} ({password})")
                else:
                    log.info(f"Joining {chan}")
                protocol.join(chan, password)
        elif command == "leave":
            chan, _, reason = suffix.partition(" ")
            if not reason:
                reason = None
            if "superadmin" in roles:
                if reason:
                    log.info("Leaving {channel} ({reason})",
                             channel=chan, reason=reason)
                else:
                    log.info(f"Leaving {chan}")
                protocol.leave(chan, reason)


def load(registry, config):
    """
    Plugin entry point called by PluginRegistry when loading the plugin.

    Args:
        registry: PluginRegistry instance
        config: Plugin configuration dictionary

    Returns:
        AdminPlugin instance
    """
    plugin_name = config.get('name', 'admin')
    plugin_config = config.get('config', {})
    plugin = AdminPlugin(plugin_name, registry, plugin_config)
    plugin.load()
    return plugin
