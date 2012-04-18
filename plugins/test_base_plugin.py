from twisted.trial import unittest
from base_plugin import BasePlugin, plugin_method, PluginMethod, order_plugin_methods

class Normal(BasePlugin):
    @plugin_method
    def test_method(self):
        pass

class High(BasePlugin):
    @plugin_method("high")
    def test_method(self):
        pass

class Low(BasePlugin):
    @plugin_method("low")
    def test_method(self):
        pass

class TestInvalidPriority(unittest.TestCase):
    def test_invalid_priority(self):
        self.assertRaises(ValueError, PluginMethod, (lambda x:x), "foo")

class TestHighAndLow(unittest.TestCase):
    def setUp(self):
        self.high_method = High().test_method
        self.low_method = Low().test_method

    def test_ordering_high_first(self):
        self.assertEqual(order_plugin_methods(self.high_method, self.low_method), -1,
                         "high should be before low")


    def test_ordering_low_first(self):
        self.assertEqual(order_plugin_methods(self.low_method, self.high_method), 1,
                         "high should be before low")

class TestHighAndNormal(unittest.TestCase):
    def setUp(self):
        self.high_method = High().test_method
        self.normal_method = Normal().test_method
        

    def test_ordering_high_first(self):
        self.assertEqual(order_plugin_methods(self.high_method, self.normal_method), -1,
                         "high should be before normal")

    def test_ordering_normal_first(self):
        self.assertEqual(order_plugin_methods(self.normal_method, self.high_method), 1,
                         "high should be before normal")

class TestNormalLow(unittest.TestCase):
    def setUp(self):
        self.normal_method = Normal().test_method
        self.low_method = Low().test_method

    def test_ordering_normal_first(self):
        self.assertEqual(order_plugin_methods(self.normal_method, self.low_method), -1,
                         "normal should be before low")

    def test_ordering_low_first(self):
        self.assertEqual(order_plugin_methods(self.low_method, self.normal_method), 1,
                         "normal should be before low")


class TestTwoSame(unittest.TestCase):
    def test_two_high(self):
        self.validate(High().test_method, High().test_method)

    def test_two_normal(self):
        self.validate(Normal().test_method, Normal().test_method)

    def test_two_low(self):
        self.validate(Low().test_method, Low().test_method)

    def validate(self, first, second):
        if id(first) < id(second):
            self.assertEqual(order_plugin_methods(first, second), -1,
                             "sorting by id() failed")
            self.assertEqual(order_plugin_methods(second, first), 1,
                             "sorting by id() failed")
        else:
            self.assertEqual(order_plugin_methods(first, second), 1,
                             "sorting by id() failed")
            self.assertEqual(order_plugin_methods(second, first), -1,
                             "sorting by id() failed")
