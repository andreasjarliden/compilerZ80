import unittest
from parser import parser
from astnodes import *
from address import Constant
from blocks import SingleBlockFactory

class TestParser(unittest.TestCase):
    #
    # VariableDefinition
    #
    def test_variableDefinition(self):
        ast = parser.parse("char foo;")
        self.assertEqual(ast[0], VariableDefinition("char", "foo"))

    def test_variableDefinition_pointer(self):
        ast = parser.parse("char* foo;")
        self.assertEqual(ast[0], VariableDefinition("*char", "foo"))
        self.assertEqual(ast[0].completeType, "*char")
        self.assertEqual(ast[0].type, "int")

    #
    # VariableAssignment
    #
    def test_variableAssignment(self):
        ast = parser.parse("a=42;");
        self.assertEqual(ast[0],
                         VariableAssignment(Variable("a"),
                                            Constant("char", 42)))
    #
    # Variable use
    #
    def test_variableUse(self):
        context = ASTContext(SingleBlockFactory())
        ast = parser.parse("char a;return a;");
        ast[0].visit(context)
        self.assertEqual(ast[1].expr.visit(context),
                         SymEntry("char", "char", "a"))

    # 
    # IF
    #
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
        self.assertEqual(ast[0].expr,
                         Relation("==",
                                  Add(Constant("char", 1), Constant("char", 2)),
                                  Add(Constant("char", 3), Constant("char", 4))))


