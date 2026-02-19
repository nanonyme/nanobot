# -*- coding: utf-8 -*-
"""
Eval plugin for nanobot.

Handles the !eval command for boolean expression evaluation.
"""
import simple_eval
from plugin import Plugin
from twisted.logger import Logger

log = Logger()


class EvalPlugin(Plugin):
    """Plugin that handles the !eval command for boolean expression evaluation."""

    def load(self):
        """Load the plugin and register handlers."""
        log.info(f"Loading {self.name} plugin")
        self.register_handler('privmsg', self.on_privmsg)
        log.info(f"{self.name} plugin loaded successfully")

    def on_privmsg(self, protocol, user, channel, message):
        """
        Handle privmsg events, responding to !eval commands.

        Args:
            protocol: NanoBotProtocol instance
            user: User who sent the message (nick!user@host)
            channel: Channel name or bot nickname (for private messages)
            message: Message text
        """
        if not message.startswith("!eval "):
            return

        suffix = message[len("!eval "):]
        if channel == protocol.nickname:
            target = user.split('!')[0]
        else:
            target = channel

        truth, _, expr = suffix.partition(":")
        truth = [s.strip() for s in truth.split(",")]
        try:
            ret = simple_eval.eval_bool(expr, truth)
        except simple_eval.EvalError as e:
            protocol.msg(target, str(e))
        else:
            protocol.msg(target, "Result: %s" % ret)


def load(registry, config):
    """
    Plugin entry point called by PluginRegistry when loading the plugin.

    Args:
        registry: PluginRegistry instance
        config: Plugin configuration dictionary

    Returns:
        EvalPlugin instance
    """
    plugin_name = config.get('name', 'eval')
    plugin_config = config.get('config', {})
    plugin = EvalPlugin(plugin_name, registry, plugin_config)
    plugin.load()
    return plugin
