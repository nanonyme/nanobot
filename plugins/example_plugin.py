# -*- coding: utf-8 -*-
"""
Example plugin for nanobot demonstrating the plugin API.

This plugin shows how to:
1. Register for IRC events
2. Respond to messages
3. Use the RemoteProtocol API
"""
from plugin import Plugin
from twisted.logger import Logger

log = Logger()


class ExamplePlugin(Plugin):
    """
    Example plugin that demonstrates basic plugin functionality.
    
    This plugin responds to messages containing certain keywords
    and demonstrates event handling.
    """
    
    def load(self):
        """Load the plugin and register handlers."""
        log.info(f"Loading {self.name} plugin")
        
        # Register for privmsg events
        self.register_handler('privmsg', self.on_privmsg)
        
        # Register for user join events
        self.register_handler('user_joined', self.on_user_joined)
        
        # Register for signed_on event
        self.register_handler('signed_on', self.on_signed_on)
        
        log.info(f"{self.name} plugin loaded successfully")
        
    def unload(self):
        """Unload the plugin and cleanup."""
        log.info(f"Unloading {self.name} plugin")
        
    def on_signed_on(self, protocol):
        """
        Called when the bot successfully signs on to IRC.
        
        Args:
            protocol: NanoBotProtocol instance
        """
        log.info(f"Bot signed on to {protocol.server.hostname}")
        
    def on_user_joined(self, protocol, user, channel):
        """
        Called when a user joins a channel.
        
        Args:
            protocol: NanoBotProtocol instance
            user: User who joined (nick!user@host)
            channel: Channel name
        """
        # Get greeting message from config, or use default
        greeting = self.config.get('greeting', 'Welcome!')
        
        # Extract nickname from user string
        nick = user.split('!')[0]
        
        log.info(f"{nick} joined {channel}")
        
        # Send greeting if enabled in config
        if self.config.get('greet_users', False):
            protocol.msg(channel, f"{greeting} {nick}")
        
    def on_privmsg(self, protocol, user, channel, message):
        """
        Called when a message is received.
        
        Args:
            protocol: NanoBotProtocol instance
            user: User who sent the message (nick!user@host)
            channel: Channel or nickname (for private messages)
            message: Message text
        """
        # Extract nickname from user string
        nick = user.split('!')[0]
        
        log.debug(f"Message from {nick} in {channel}: {message}")
        
        # Check for keyword triggers
        keywords = self.config.get('keywords', [])
        for keyword in keywords:
            if keyword.lower() in message.lower():
                response = self.config.get('response', 'I heard that!')
                protocol.msg(channel, f"{nick}: {response}")
                break


def load(registry, config):
    """
    Plugin entry point.
    
    This function is called by the PluginRegistry when loading the plugin.
    
    Args:
        registry: PluginRegistry instance
        config: Plugin configuration dictionary
        
    Returns:
        Plugin instance
    """
    plugin_name = config.get('name', 'example')
    plugin_config = config.get('config', {})
    
    plugin = ExamplePlugin(plugin_name, registry, plugin_config)
    plugin.load()
    
    return plugin
