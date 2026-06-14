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

    def test_variableDefinition_hexValue(self):
        ast = parser.parse("int foo = 0x12AB;")
        self.assertEqual(ast[0], VariableDefinition("int", "foo", Constant("int", 0x12AB)))

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
    # Casting
    #
    def test_cast(self):
        ast = parser.parse("a=(char*)42;");
        self.assertEqual(ast[0],
                         VariableAssignment(Variable("a"),
                                            Cast("char*", Constant("char", 42))))

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
    # typedef
    #
    def test_typedef(self):
        ast = parser.parse("typedef char MyType;MyType myvar;")
        self.assertEqual(ast[0],
                         TypeDef("MyType", "char"))
        self.assertEqual(ast[1],
                         VariableDefinition("MyType", "myvar"))

    #
    # struct
    #
    def test_defineStruct(self):
        ast = parser.parse("struct mystruct { char foo; int bar; };")
        self.assertEqual(ast[0],
                         StructDefinition("mystruct",
                                          ( VariableDefinition("char", "foo"),
                                           VariableDefinition("int", "bar"))))

    def test_structVariable(self):
        self.maxDiff = None
        ast = parser.parse("struct mystruct { char foo; }; struct mystruct s;")
        self.assertEqual(ast[0],
                         StructDefinition("mystruct",
                                          ( VariableDefinition("char", "foo"), )))
        self.assertEqual(ast[1],
                         VariableDefinition(StructType("mystruct", ()), "s"))


    #
    # Function declaration
    #
    def test_functionDeclaration(self):
        ast = parser.parse("void foo(char a, int b);")
        blockFactory = BlockFactory()
        context = ASTContext(blockFactory)
        ast[0].visit(context)
        foo = context.symbolTable.lookUp("foo")
        self.assertEqual(foo, FunctionDeclaration("void", "foo", (Argument("char", "a"),
                                                                  Argument("int", "b"))))

    #
    # Function definition
    #
    def test_function_noStackFrame(self):
        ast = parser.parse("char foo() { return 0; }")
        blockFactory = BlockFactory()
        context = ASTContext(blockFactory)
        ast[0].visit(context)
        blocks = blockFactory.blocks()
        block = blocks["foo_0000"]
        self.assertIsInstance(ast[0], FunctionDefinition)
        self.assertEqual(ast[0].frameSize, 0)
        self.assertTrue(isinstance(block.statements[0], IRDefFun))
        self.assertEqual(block.statements[1], IRReturn("char", Constant("char", 0), "foo"))
        self.assertTrue(isinstance(block.statements[2], IRFunExit))

    def test_function_stackFrame(self):
        ast = parser.parse("char foo(char arg) { int i; }")
        blockFactory = BlockFactory()
        context = ASTContext(blockFactory)
        ast[0].visit(context)
        blocks = blockFactory.blocks()
        block = blocks["foo_0000"]
        self.assertEqual(ast[0].frameSize, 2)
        self.assertTrue(isinstance(block.statements[0], IRDefFun))
        self.assertTrue(isinstance(block.statements[1], IRFunExit))

    def test_function_mapSymbols_byteArgs(self):
        ast = parser.parse("char foo(char arg1, char arg2) { int iVar; char cVar; }")
        blockFactory = BlockFactory()
        context = ASTContext(blockFactory)
        symbolTable = ast[0].visit(context)
        self.assertEqual(symbolTable["arg1"].impl.offset, +5) # byte args are pushed as ints in the UPPER byte
        self.assertEqual(symbolTable["arg2"].impl.offset, +7)
        self.assertEqual(symbolTable["iVar"].impl.offset, -2) # (ix-2, ix-1)
        self.assertEqual(symbolTable["cVar"].impl.offset, -3) # (ix-3)

    def test_function_mapSymbols_mixedArgs(self):
        ast = parser.parse("char foo(int arg1, char arg2) { char cVar; int iVar; }")
        blockFactory = BlockFactory()
        context = ASTContext(blockFactory)
        symbolTable = ast[0].visit(context)
        self.assertEqual(symbolTable["arg1"].impl.offset, +4) # First int arg at ix+4, ix+5
        self.assertEqual(symbolTable["arg2"].impl.offset, +7) # second arg sent as ix+6, ix+7 with the value in IX+7
        self.assertEqual(symbolTable["cVar"].impl.offset, -1) # (ix-1)
        self.assertEqual(symbolTable["iVar"].impl.offset, -3) # (ix-3, ix-2)

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
        # self.assertTrue(False)
        
    #
    # Arithmetics
    #
    def test_addition(self):
        ast = parser.parse("a=b+c;");
        self.assertEqual(ast[0],
                         VariableAssignment(Variable("a"),
                                            Add(Variable("b"),
                                                Variable("c"))))

    def test_subtraction(self):
        ast = parser.parse("a=b-c;");
        self.assertEqual(ast[0],
                         VariableAssignment(Variable("a"),
                                            Subtraction(Variable("b"),
                                                        Variable("c"))))
