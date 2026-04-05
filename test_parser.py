import unittest
from parser import parser
from astnodes import *
from address import Constant
from blocks import SingleBlockFactory, BlockFactory

class TestParser(unittest.TestCase):
    #
    # VariableDefinition
    #
    def test_variableDefinition(self):
        ast = parser.parse("char foo;")
        self.assertEqual(ast[0], VariableDefinition("char", "foo"))

    def test_variableDefinition_value(self):
        ast = parser.parse("char foo = 42;")
        self.assertEqual(ast[0], VariableDefinition("char", "foo", Constant("char", 42)))

    def test_variableDefinition_string(self):
        ast = parser.parse('char* foo = "foo";')
        self.assertEqual(ast[0].value, StringConstant(String("foo")))
        self.assertEqual(ast[0], VariableDefinition("char*", "foo", StringConstant(String("foo"))))

    def test_variableDefinition_pointer(self):
        ast = parser.parse("char* foo;")
        self.assertEqual(ast[0], VariableDefinition("char*", "foo"))
        self.assertEqual(ast[0].completeType, "char*")
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
        symbolTable = SymbolTable()
        context = ASTContext(SingleBlockFactory())
        ast = parser.parse("char a;return a;");
        ast[0].visit(context)
        self.assertTrue(ast[1].expr.visit(context).equalByValue(
            SymEntry("char", "a")))

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
        self.assertTrue(isinstance(ast[0], If))
        self.assertTrue(isinstance(ast[0].expr, Relation))
        self.assertEqual(ast[0].expr,
                         Relation("==",
                                  Add(Constant("char", 1), Constant("char", 2)),
                                  Add(Constant("char", 3), Constant("char", 4))))

    #
    # Function call
    #

    def test_funCall(self):
        ast = parser.parse("""foo(1, 2);""")
        self.assertEqual(ast[0],
                         FunctionCall("foo",
                                      [ Constant("char", 1), Constant("char", 2)]))

    def test_funCallString(self):
        ast = parser.parse("""foo("hello");""")
        self.assertEqual(ast[0],
                         FunctionCall("foo",
                                      [ StringConstant(String("hello"))]))


    #
    # Function
    #
    def test_function_noStackFrame(self):
        ast = parser.parse("char foo() { return 0; }")
        blockFactory = BlockFactory()
        context = ASTContext(blockFactory)
        ast[0].visit(context)
        blocks = blockFactory.blocks()
        block = blocks["foo_0000"]
        self.assertTrue(isinstance(block.statements[0], IRDefFun))
        self.assertEqual(block.statements[1], IRReturn("char", Constant("char", 0), "foo"))
        self.assertTrue(isinstance(block.statements[2], IRFunExit))
        self.assertEqual(block.statements[2].hasStackFrame, False)

    def test_function_stackFrame(self):
        ast = parser.parse("char foo() { int a; }")
        blockFactory = BlockFactory()
        context = ASTContext(blockFactory)
        ast[0].visit(context)
        blocks = blockFactory.blocks()
        block = blocks["foo_0000"]
        self.assertTrue(isinstance(block.statements[0], IRDefFun))
        self.assertTrue(isinstance(block.statements[1], IRFunExit))
        self.assertEqual(block.statements[1].hasStackFrame, True)

    #
    # while
    #
    def test_while(self):
        ast = parser.parse("""char main() {
                                  char a=0;
                                  while (a<5) {
                                      a = a + 1;
                                  }
                              }
                            """)
        iast = ast[0].statements
        self.assertTrue(isinstance(iast[1], While))
        self.assertTrue(isinstance(iast[1].expr, Relation))
        context = ASTContext()
        ast[0].visit(context)
        blocks = context.blockFactory.blocks()
        block = blocks["main_0000"]
        print(block)
        # self.assertTrue(False)


