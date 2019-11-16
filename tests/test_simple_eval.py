import unittest
import simple_eval

class TestTokenizer(unittest.TestCase):

    def case(self, input, output):
        self.assertEqual(list(simple_eval.tokenize(input,
            simple_eval.BOOL_SYNTAX, simple_eval.WHITESPACE)), 
            output)

    def test_chars(self):
        self.case("foo", [(0, "foo")])

    def test_and(self):
        self.case("foo & bar", [(0, "foo"), (4, "&"), (6, "bar")])

    def test_os(self):
        self.case("foo | bar", [(0, "foo"), (4, "|"), (6, "bar")])

    def test_negation(self):
        self.case("~foo", [(0, "~"), (1, "foo")])

    def test_parens(self):
        self.case("(a)", [(0, "("), (1, "a"), (2, ")")])
    
    def test_complex(self):
        self.case("~(x&y)|(~x&~y)", [
            (0, "~"), (1, "("), (2, "x"), (3, "&"), (4, "y"),
            (5, ")"), (6, "|"), (7, "("), (8, "~"), (9, "x"),
            (10, "&"), (11, "~"), (12, "y"), (13, ")")])

class TestBoolEval(unittest.TestCase):

    def test_simple_true(self):
        self.assertTrue(simple_eval.eval_bool("foo", ("foo",)))

    def test_simple_false(self):
        self.assertFalse(simple_eval.eval_bool("foo", ("bar",)))

    def test_true_and_True(self):
        self.assertFalse(simple_eval.eval_bool("foo&bar", ("foo",)))

    def test_true_and_true(self):
        self.assertTrue(simple_eval.eval_bool("foo&bar", ("foo", "bar")))

    def test_false_and_true(self):
        self.assertFalse(simple_eval.eval_bool("foo&bar", ("bar",)))

    def test_false_and_false(self):
        self.assertFalse(simple_eval.eval_bool("foo&bar", ()))

    def test_not_true(self):
        self.assertFalse(simple_eval.eval_bool("~foo", ("foo", )))

    def test_not_false(self):
        self.assertTrue(simple_eval.eval_bool("~foo", ()))

    def test_false_or_true(self):
        self.assertTrue(simple_eval.eval_bool("foo|bar", ("bar", )))

    def test_true_or_false(self):
        self.assertTrue(simple_eval.eval_bool("foo|bar", ("foo",)))

    def test_true_or_true(self):
        self.assertTrue(simple_eval.eval_bool("foo|bar", ("foo", "bar")))

    def test_false_or_false(self):
        self.assertFalse(simple_eval.eval_bool("foo|bar", ()))

    def test_demorgan(self):
        expr = "~(foo&bar)&~(~foo|~bar)"
        self.assertFalse(simple_eval.eval_bool(expr, 
                                               ("foo", "bar")
                                               )
                         )

    def test_bad_input_illegal(self):
        with self.assertRaisesRegex(ValueError, "Invalid token / at position 4"):
            simple_eval.eval_bool("aef&//&||", ())

    def test_bad_legal(self):
        with self.assertRaisesRegex(ValueError, "Invalid token & at position 2"):
            simple_eval.eval_bool("a&&b", ())
