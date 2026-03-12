import unittest
from parser import parser, If, Relation, Add
from address import Constant

class TestParser(unittest.TestCase):
    def test_if_equality(self):
        ast = parser.parse("""if (1 + 2 == 3 + 4) { return 0; }""")
        print(ast)
        self.assertTrue(isinstance(ast[0], If))
        self.assertTrue(isinstance(ast[0].expr, Relation))
        self.assertEqual(ast[0].expr.lhs.lhs, Constant("char", 1))
        self.assertEqual(ast[0].expr.lhs, Add(Constant("char", 1), Constant("char", 2)))
        self.assertEqual(ast[0].expr.rhs, Add(Constant("char", 3), Constant("char", 4)))

    # TODO: Doesn't handle empty {}
    # def test_if_simple(self):
    #     ast = parser.parse("""if (1) { }""")
