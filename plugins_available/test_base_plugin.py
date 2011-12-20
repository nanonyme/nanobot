from twisted.trial import unittest
from twisted.internet import defer, reactor
import base_plugin

class Normal(base_plugin.BasePlugin):
    def test_method(self):
        pass

class SecondNormal(base_plugin.BasePlugin):
    def test_method(self):
        pass


class High(base_plugin.BasePlugin):
    @base_plugin.PluginWrapper("high")
    def test_method(self):
        pass

class SecondHigh(base_plugin.BasePlugin):
    @base_plugin.PluginWrapper("high")
    def test_method(self):
        pass


class Low(base_plugin.BasePlugin):
    @base_plugin.PluginWrapper("low")
    def test_method(self):
        pass

class SecondLow(base_plugin.BasePlugin):
    @base_plugin.PluginWrapper("low")
    def test_method(self):
        pass

def delayed_test(func, cmp, a, b):
    d = defer.Deferred()
    d.addCallback(func)
    reactor.callLater(0, d.callback, cmp(a, b))
    return d

def passthrough():
    pass

class TestInvalidPriority(unittest.TestCase):
    def test_invalid_priority(self):
        w = base_plugin.PluginWrapper("foo")
        self.assertRaises(ValueError, w, passthrough)

class TestHighAndLow(unittest.TestCase):
    def setUp(self):
        self.high_method = High().test_method
        self.low_method = Low().test_method

    def test_high_lt_low(self):
        return delayed_test(self.assertTrue, lambda a, b : a < b,
                            self.high_method, self.low_method)

    def test_high_le_low(self):
        return delayed_test(self.assertTrue, lambda a, b : a <= b,
                            self.high_method, self.low_method)

    def test_not_low_lt_high(self):
        return delayed_test(self.assertFalse, lambda a, b : a < b,
                            self.low_method, self.high_method)

    def test_not_low_le_high(self):
        return delayed_test(self.assertFalse, lambda a, b : a <= b,
                            self.low_method, self.high_method)

    def test_low_gt_high(self):
        return delayed_test(self.assertTrue, lambda a, b : a > b,
                            self.low_method, self.high_method)

    def test_low_ge_high(self):
        return delayed_test(self.assertTrue, lambda a, b : a >= b,
                            self.low_method, self.high_method)

    def test_not_high_gt_low(self):
        return delayed_test(self.assertFalse, lambda a, b : a > b,
                            self.high_method, self.low_method)

    def test_not_high_ge_low(self):
        return delayed_test(self.assertFalse, lambda a, b : a >= b,
                            self.high_method, self.low_method)

    def test_low_ne_high(self):
        return delayed_test(self.assertTrue, lambda a, b : a != b,
                            self.low_method, self.high_method)

    def test_high_ne_low(self):
        return delayed_test(self.assertTrue, lambda a, b : a != b,
                            self.high_method, self.low_method)

    def test_not_low_eq_high(self):
        return delayed_test(self.assertFalse, lambda a, b : a == b,
                            self.low_method, self.high_method)

    def test_not_high_eq_low(self):
        return delayed_test(self.assertFalse, lambda a, b : a == b,
                            self.high_method, self.low_method)

class TestHighAndNormal(unittest.TestCase):
    def setUp(self):
        self.high_method = High().test_method
        self.normal_method = Normal().test_method

    def test_high_lt_normal(self):
        return delayed_test(self.assertTrue, lambda a, b : a < b,
                            self.high_method, self.normal_method)

    def test_high_le_normal(self):
        return delayed_test(self.assertTrue, lambda a, b : a <= b,
                            self.high_method, self.normal_method)

    def test_not_normal_lt_high(self):
        return delayed_test(self.assertFalse, lambda a, b : a < b,
                            self.normal_method, self.high_method)

    def test_not_normal_le_high(self):
        return delayed_test(self.assertFalse, lambda a, b : a <= b,
                            self.normal_method, self.high_method)

    def test_normal_gt_high(self):
        return delayed_test(self.assertTrue, lambda a, b : a > b,
                            self.normal_method, self.high_method)

    def test_normal_ge_high(self):
        return delayed_test(self.assertTrue, lambda a, b : a >= b,
                            self.normal_method, self.high_method)

    def test_not_high_gt_normal(self):
        return delayed_test(self.assertFalse, lambda a, b : a > b,
                            self.high_method, self.normal_method)

    def test_not_high_ge_normal(self):
        return delayed_test(self.assertFalse, lambda a, b : a >= b,
                            self.high_method, self.normal_method)

    def test_normal_ne_high(self):
        return delayed_test(self.assertTrue, lambda a, b : a != b,
                            self.normal_method, self.high_method)

    def test_high_ne_normal(self):
        return delayed_test(self.assertTrue, lambda a, b : a != b,
                            self.high_method, self.normal_method)

    def test_not_normal_eq_high(self):
        return delayed_test(self.assertFalse, lambda a, b : a == b,
                            self.normal_method, self.high_method)

    def test_not_high_eq_normal(self):
        return delayed_test(self.assertFalse, lambda a, b : a == b,
                            self.high_method, self.normal_method)

class TestNormalAndLow(unittest.TestCase):
    def setUp(self):
        self.normal_method = Normal().test_method
        self.low_method = Low().test_method

    def test_normal_lt_low(self):
        return delayed_test(self.assertTrue, lambda a, b : a < b,
                            self.normal_method, self.low_method)

    def test_normal_le_low(self):
        return delayed_test(self.assertTrue, lambda a, b : a <= b,
                            self.normal_method, self.low_method)

    def test_not_low_lt_normal(self):
        return delayed_test(self.assertFalse, lambda a, b : a < b,
                            self.low_method, self.normal_method)

    def test_not_low_le_normal(self):
        return delayed_test(self.assertFalse, lambda a, b : a <= b,
                            self.low_method, self.normal_method)

    def test_low_gt_normal(self):
        return delayed_test(self.assertTrue, lambda a, b : a > b,
                            self.low_method, self.normal_method)

    def test_low_ge_normal(self):
        return delayed_test(self.assertTrue, lambda a, b : a >= b,
                            self.low_method, self.normal_method)

    def test_not_normal_gt_low(self):
        return delayed_test(self.assertFalse, lambda a, b : a > b,
                            self.normal_method, self.low_method)

    def test_not_normal_ge_low(self):
        return delayed_test(self.assertFalse, lambda a, b : a >= b,
                            self.normal_method, self.low_method)

    def test_low_ne_normal(self):
        return delayed_test(self.assertTrue, lambda a, b : a != b,
                            self.low_method, self.normal_method)

    def test_normal_ne_low(self):
        return delayed_test(self.assertTrue, lambda a, b : a != b,
                            self.normal_method, self.low_method)

    def test_not_low_eq_normal(self):
        return delayed_test(self.assertFalse, lambda a, b : a == b,
                            self.low_method, self.normal_method)

    def test_not_normal_eq_low(self):
        return delayed_test(self.assertFalse, lambda a, b : a == b,
                            self.normal_method, self.low_method)


class Foo:

    def test_normal_lt_low(self):
        reactor.callLater(0, self.d.callback,
                          self.normal.test_method < self.low.test_method)
        return self.d

    def test_normal_le_low(self):
        reactor.callLater(0, self.d.callback,
                          self.normal.test_method <= self.low.test_method)
        return self.d

    def test_low_lt_low(self):
        reactor.callLater(0, self.d.callback,
                          self.low.test_method < self.low.test_method)
        return self.d

    def test_low_le_low(self):
        reactor.callLater(0, self.d.callback,
                          self.low.test_method < self.low.test_method)
        return self.d


    def test_low_gt_normal(self):
        reactor.callLater(0, self.d.callback,
                          self.low.test_method > self.normal.test_method)
        return self.d

    def test_low_ge_normal(self):
        reactor.callLater(0, self.d.callback,
                          self.low.test_method >= self.normal.test_method)
        return self.d

    def test_low_gt_normal(self):
        reactor.callLater(0, self.d.callback,
                          self.low.test_method > self.normal.test_method)
        return self.d


    def test_low_gt_low(self):
        reactor.callLater(0, self.d.callback,
                          self.low.test_method > self.low.test_method)
        return self.d

    def test_low_ge_low(self):
        reactor.callLater(0, self.d.callback,
                          self.low.test_method >= self.low.test_method)
        return self.d

    def test_normal_ne_low(self):
        reactor.callLater(0, self.d.callback,
                          self.normal.test_method != self.low.test_method)
        return self.d

    def test_low_ne_normal(self):
        reactor.callLater(0, self.d.callback,
                          self.low.test_method != self.normal.test_method)
        return self.d


    def test_low_ne_low(self):
        reactor.callLater(0, self.d.callback,
                          self.low.test_method != self.low.test_method)
        return self.d

    def test_low_ne_low(self):
        reactor.callLater(0, self.d.callback,
                          self.low.test_method != self.low.test_method)
        return self.d


class TestNormalEqualities(unittest.TestCase):
    def setUp(self):

        self.first_method = Normal().test_method
        self.second_method = SecondNormal().test_method
        self.d = defer.Deferred()

    def test_first_normal_eq_second_normal_false(self):
        self.d.addCallback(self.assertFalse)
        reactor.callLater(0, self.d.callback,
                          self.first_method == self.second_method)
        return self.d

    def test_second_normal_eq_first_normal_false(self):
        self.d.addCallback(self.assertFalse)
        reactor.callLater(0, self.d.callback,
                          self.second_method == self.first_method)
        return self.d


    def test_first_normal_eq_first_normal(self):
        self.d.addCallback(self.assertTrue)
        reactor.callLater(0, self.d.callback,
                          self.first_method == self.first_method)
        return self.d

    def test_second_normal_eq_second_normal(self):
        self.d.addCallback(self.assertTrue)
        reactor.callLater(0, self.d.callback,
                          self.second_method == self.second_method)
        return self.d


class TestHighEqualities(unittest.TestCase):
    def setUp(self):

        self.first_method = High().test_method
        self.second_method = SecondHigh().test_method
        self.d = defer.Deferred()

    def test_first_low_eq_second_low_false(self):
        self.d.addCallback(self.assertFalse)
        reactor.callLater(0, self.d.callback,
                          self.first_method == self.second_method)
        return self.d

    def test_second_low_eq_first_low_false(self):
        self.d.addCallback(self.assertFalse)
        reactor.callLater(0, self.d.callback,
                          self.second_method == self.first_method)
        return self.d

    
    def test_first_low_eq_first_low(self):
        self.d.addCallback(self.assertTrue)
        reactor.callLater(0, self.d.callback,
                          self.first_method == self.first_method)
        return self.d

    def test_second_low_eq_second_low(self):
        self.d.addCallback(self.assertTrue)
        reactor.callLater(0, self.d.callback,
                          self.second_method == self.second_method)
        return self.d
                                                                                                                                
