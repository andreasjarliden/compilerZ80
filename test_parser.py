import unittest
from parser import parser, If, Relation, Add, Return
from address import Constant

class TestParser(unittest.TestCase):

    # IF

    def test_if_simple(self):
        ast = parser.parse("""if (1) { }""")
        self.assertEqual(ast[0], If(Constant("char", 1), []))

    def test_if_single_statement(self):
        ast = parser.parse("""if (1) return 42;""")
        self.assertEqual(ast[0], If(Constant("char", 1),
                                    [ Return(Constant("char", 42)) ] ))

    def test_if_equality(self):
        ast = parser.parse("""if (1 + 2 == 3 + 4) return 0;""")
        print(ast)
        self.assertTrue(isinstance(ast[0], If))
        self.assertTrue(isinstance(ast[0].expr, Relation))
        self.assertEqual(ast[0].expr, Relation("==",
                                               Add(Constant("char", 1), Constant("char", 2)),
                                               Add(Constant("char", 3), Constant("char", 4))))


