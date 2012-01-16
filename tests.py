import http_client
from twisted.trial import unittest
import StringIO

class TestSizeLimiter(unittest.TestCase):
    def setUp(self):
        self.f = StringIO.StringIO()
        self.s = " ".join("foo" for _ in range(20))
        
    def test_all_data_written_without_limit(self):
        limited_file = http_client.SizeLimitedFile(self.f)
        limited_file.write(self.s)
        self.assertEqual(self.f.getvalue(), self.s)

    def test_size_limit(self):
        limited_file = http_client.SizeLimitedFile(self.f,
                                                   10)
        self.failUnlessRaises(http_client.ConnectionAborted,
                              limited_file.write, self.s)
