from twisted.trial import unittest
from twisted.internet import task
from plugin import PluginRegistry, Plugin


class TestPlugin(Plugin):
    """Test plugin for unit tests"""
    
    def __init__(self, name, registry, config=None):
        super().__init__(name, registry, config)
        self.loaded = False
        self.unloaded = False
        self.handler_calls = []
        
    def load(self):
        """Load the test plugin"""
        self.loaded = True
        # Register a test handler
        self.register_handler('test_event', self.test_handler)
        
    def unload(self):
        """Unload the test plugin"""
        self.unloaded = True
        
    def test_handler(self, protocol, *args, **kwargs):
        """Test event handler"""
        self.handler_calls.append((args, kwargs))


class PluginRegistryTests(unittest.TestCase):
    """Tests for PluginRegistry"""
    
    def setUp(self):
        self.clock = task.Clock()
        self.registry = PluginRegistry(self.clock, {})
    
    def test_register_plugin(self):
        """Test registering a plugin"""
        plugin = TestPlugin('test', self.registry)
        self.registry.register_plugin(plugin)
        
        self.assertIn('test', self.registry.plugins)
        self.assertEqual(self.registry.plugins['test'], plugin)
    
    def test_register_handler(self):
        """Test registering an event handler"""
        def handler(protocol, *args):
            pass
        
        self.registry.register_handler('privmsg', handler)
        
        handlers = self.registry.get_handlers('privmsg')
        self.assertEqual(len(handlers), 1)
        self.assertIn(handler, handlers)
    
    def test_register_multiple_handlers(self):
        """Test registering multiple handlers for same event"""
        def handler1(protocol, *args):
            pass
        
        def handler2(protocol, *args):
            pass
        
        self.registry.register_handler('privmsg', handler1)
        self.registry.register_handler('privmsg', handler2)
        
        handlers = self.registry.get_handlers('privmsg')
        self.assertEqual(len(handlers), 2)
        self.assertIn(handler1, handlers)
        self.assertIn(handler2, handlers)
    
    def test_unregister_handler(self):
        """Test unregistering an event handler"""
        def handler(protocol, *args):
            pass
        
        self.registry.register_handler('privmsg', handler)
        self.assertEqual(len(self.registry.get_handlers('privmsg')), 1)
        
        self.registry.unregister_handler('privmsg', handler)
        self.assertEqual(len(self.registry.get_handlers('privmsg')), 0)
    
    def test_get_handlers_empty(self):
        """Test getting handlers for unregistered event"""
        handlers = self.registry.get_handlers('nonexistent')
        self.assertEqual(handlers, [])
    
    def test_unload_plugin(self):
        """Test unloading a plugin"""
        plugin = TestPlugin('test', self.registry)
        plugin.load()
        self.registry.register_plugin(plugin)
        
        self.assertTrue(plugin.loaded)
        self.assertFalse(plugin.unloaded)
        
        self.registry.unload_plugin('test')
        
        self.assertTrue(plugin.unloaded)
        self.assertNotIn('test', self.registry.plugins)
    
    def test_replace_existing_plugin(self):
        """Test that registering a plugin with same name replaces it"""
        plugin1 = TestPlugin('test', self.registry)
        plugin2 = TestPlugin('test', self.registry)
        
        self.registry.register_plugin(plugin1)
        self.assertEqual(self.registry.plugins['test'], plugin1)
        
        self.registry.register_plugin(plugin2)
        self.assertEqual(self.registry.plugins['test'], plugin2)


class PluginTests(unittest.TestCase):
    """Tests for Plugin base class"""
    
    def setUp(self):
        self.clock = task.Clock()
        self.registry = PluginRegistry(self.clock, {})
    
    def test_plugin_initialization(self):
        """Test plugin initialization"""
        config = {'option1': 'value1'}
        plugin = TestPlugin('test', self.registry, config)
        
        self.assertEqual(plugin.name, 'test')
        self.assertEqual(plugin.registry, self.registry)
        self.assertEqual(plugin.config, config)
        self.assertEqual(plugin.reactor, self.clock)
    
    def test_plugin_load(self):
        """Test plugin load method"""
        plugin = TestPlugin('test', self.registry)
        self.assertFalse(plugin.loaded)
        
        plugin.load()
        
        self.assertTrue(plugin.loaded)
        # Handler should be registered
        handlers = self.registry.get_handlers('test_event')
        self.assertEqual(len(handlers), 1)
    
    def test_plugin_unload(self):
        """Test plugin unload method"""
        plugin = TestPlugin('test', self.registry)
        plugin.load()
        
        self.assertFalse(plugin.unloaded)
        plugin.unload()
        self.assertTrue(plugin.unloaded)
    
    def test_plugin_register_handler(self):
        """Test plugin register_handler convenience method"""
        plugin = TestPlugin('test', self.registry)
        
        def handler(protocol, *args):
            pass
        
        plugin.register_handler('custom_event', handler)
        
        handlers = self.registry.get_handlers('custom_event')
        self.assertIn(handler, handlers)
    
    def test_handler_invocation(self):
        """Test that registered handlers are invoked correctly"""
        plugin = TestPlugin('test', self.registry)
        plugin.load()
        
        # Simulate calling the handler
        handlers = self.registry.get_handlers('test_event')
        self.assertEqual(len(handlers), 1)
        
        # Mock protocol object
        class MockProtocol:
            pass
        
        protocol = MockProtocol()
        handlers[0](protocol, 'arg1', 'arg2', key='value')
        
        # Check that handler was called with correct arguments
        self.assertEqual(len(plugin.handler_calls), 1)
        args, kwargs = plugin.handler_calls[0]
        self.assertEqual(args, ('arg1', 'arg2'))
        self.assertEqual(kwargs, {'key': 'value'})
