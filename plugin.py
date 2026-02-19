# -*- coding: utf-8 -*-
"""
Plugin system for nanobot.

This module provides a plugin registry and base plugin class for extending
nanobot functionality. Plugins can register handlers for IRC events and
provide custom behavior.
"""
from twisted.logger import Logger
from typing import Callable, Dict, List, Optional, Any
from abc import ABC, abstractmethod

log = Logger()


class PluginRegistry:
    """
    Registry for managing plugins and their event handlers.
    
    The registry maintains a list of loaded plugins and maps event types
    to their registered handlers.
    """
    
    def __init__(self, reactor, config: Optional[Dict] = None):
        """
        Initialize the plugin registry.
        
        Args:
            reactor: Twisted reactor instance
            config: Configuration dictionary for plugins
        """
        self.reactor = reactor
        self.config = config or {}
        self.plugins: Dict[str, 'Plugin'] = {}
        self.handlers: Dict[str, List[Callable]] = {}
        
    def register_plugin(self, plugin: 'Plugin') -> None:
        """
        Register a plugin with the registry.
        
        Args:
            plugin: Plugin instance to register
        """
        name = plugin.name
        if name in self.plugins:
            log.warn(f"Plugin {name} already registered, replacing")
        self.plugins[name] = plugin
        log.info(f"Registered plugin: {name}")
        
    def register_handler(self, event_type: str, handler: Callable) -> None:
        """
        Register a handler for a specific event type.
        
        Args:
            event_type: Type of event to handle (e.g., 'privmsg', 'join', 'part')
            handler: Callable to invoke when event occurs
        """
        if event_type not in self.handlers:
            self.handlers[event_type] = []
        self.handlers[event_type].append(handler)
        log.debug(f"Registered handler for event: {event_type}")
        
    def unregister_handler(self, event_type: str, handler: Callable) -> None:
        """
        Unregister a handler for a specific event type.
        
        Args:
            event_type: Type of event
            handler: Handler to remove
        """
        if event_type in self.handlers:
            try:
                self.handlers[event_type].remove(handler)
                log.debug(f"Unregistered handler for event: {event_type}")
            except ValueError:
                log.warn(f"Handler not found for event: {event_type}")
                
    def get_handlers(self, event_type: str) -> List[Callable]:
        """
        Get all handlers registered for an event type.
        
        Args:
            event_type: Type of event
            
        Returns:
            List of handlers for the event type
        """
        return self.handlers.get(event_type, [])
        
    def load_plugins(self, plugin_configs: List[Dict]) -> None:
        """
        Load plugins based on configuration.
        
        Args:
            plugin_configs: List of plugin configuration dictionaries
        """
        for plugin_config in plugin_configs:
            plugin_name = plugin_config.get('name')
            plugin_module = plugin_config.get('module')
            plugin_enabled = plugin_config.get('enabled', True)
            
            if not plugin_enabled:
                log.info(f"Plugin {plugin_name} is disabled, skipping")
                continue
                
            if not plugin_module:
                log.error(f"Plugin {plugin_name} missing module path")
                continue
                
            try:
                # Dynamic import of plugin module
                module = __import__(plugin_module, fromlist=[''])
                if hasattr(module, 'load'):
                    plugin = module.load(self, plugin_config)
                    if plugin:
                        self.register_plugin(plugin)
                else:
                    log.error(f"Plugin module {plugin_module} has no load() function")
            except Exception as e:
                log.failure(f"Failed to load plugin {plugin_name}: {e}")
                
    def unload_plugin(self, plugin_name: str) -> None:
        """
        Unload a plugin by name.
        
        Args:
            plugin_name: Name of plugin to unload
        """
        if plugin_name in self.plugins:
            plugin = self.plugins[plugin_name]
            plugin.unload()
            del self.plugins[plugin_name]
            log.info(f"Unloaded plugin: {plugin_name}")
        else:
            log.warn(f"Plugin {plugin_name} not found")


class Plugin(ABC):
    """
    Base class for nanobot plugins.
    
    Plugins should inherit from this class and implement the load() method
    to register their handlers and initialize their state.
    """
    
    def __init__(self, name: str, registry: PluginRegistry, config: Optional[Dict] = None):
        """
        Initialize the plugin.
        
        Args:
            name: Unique name for the plugin
            registry: Plugin registry instance
            config: Plugin-specific configuration
        """
        self.name = name
        self.registry = registry
        self.config = config or {}
        self.reactor = registry.reactor
        
    @abstractmethod
    def load(self) -> None:
        """
        Load the plugin and register handlers.
        
        This method should register any event handlers the plugin needs
        using registry.register_handler().
        """
        pass
        
    def unload(self) -> None:
        """
        Unload the plugin and cleanup resources.
        
        Override this method to perform cleanup when the plugin is unloaded.
        """
        pass
        
    def register_handler(self, event_type: str, handler: Callable) -> None:
        """
        Convenience method to register a handler.
        
        Args:
            event_type: Type of event to handle
            handler: Callable to invoke when event occurs
        """
        self.registry.register_handler(event_type, handler)
