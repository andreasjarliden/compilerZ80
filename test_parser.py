import unittest
from parser import parser
from lexer import lexer
from astnodes import *
from blocks import SingleBlockFactory, BlockFactory
from type_defs import PointerType
from pprint import pprint

class TestParser(unittest.TestCase):
    def setUp(self):
        lexer.lineno = 1

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
        self.assertEqual(ast[0].value, StringConstant("foo"))
        self.assertEqual(ast[0], VariableDefinition(PointerType("char"), "foo", StringConstant("foo")))

    def test_variableDefinition_charLiteral(self):
        ast = parser.parse("'a';")
        self.assertEqual(ast[0], Constant("char", 97))
        ast = parser.parse("'\\t';")
        self.assertEqual(ast[0], Constant("char", 9))
        ast = parser.parse("'\\n';")
        self.assertEqual(ast[0], Constant("char", 10))
        with self.assertRaises(CompileError) as cts:
            parser.parse("'aa';")
        self.assertIn("Character littera longer than one character 'aa'", cts.exception.message)
        self.assertEqual(cts.exception.location.line, 1)

    def test_variableDefinition_pointer(self):
        ast = parser.parse("char* foo;")
        self.assertEqual(ast[0], VariableDefinition(PointerType("char"), "foo"))
        self.assertEqual(ast[0].completeType, PointerType("char"))
        self.assertEqual(ast[0].type, "int")

    #
    # VariableAssignment
    #
    def test_variableAssignment(self):
        ast = parser.parse("a=42;");
        self.assertEqual(ast[0],
                         VariableAssignment(Variable("a"),
                                            Constant("char", 42)))

    def test_assignmentAsExpression(self):
        ast = parser.parse("*(a=42);");
        self.assertEqual(ast[0],
                         Dereference(VariableAssignment(Variable("a"),
                                                        Constant("char", 42))))

    def test_derefAssignment(self):
        ast = parser.parse("*a=42;");
        self.assertEqual(ast[0],
                         VariableAssignment(Dereference(Variable("a")),
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
            SymbolOperand("char", "a")))

    #
    # Casting
    #
    def test_cast(self):
        ast = parser.parse("a=(char*)42;");
        self.assertEqual(ast[0],
                         VariableAssignment(Variable("a"),
                                            Cast(PointerType("char"), Constant("char", 42))))
        ast = parser.parse("a=(char**)42;");
        self.assertEqual(ast[0],
                         VariableAssignment(Variable("a"),
                                            Cast(PointerType(PointerType("char")), Constant("char", 42))))

    #
    # Address of
    #
    def test_addressOf(self):
        ast = parser.parse("c=&foo;");
        self.assertEqual(ast[0],
                         VariableAssignment(Variable("c"),
                                            AddressOf(Variable("foo"))))

    #
    # sizeof
    #
    def test_sizeof_intPointer(self):
        ast = parser.parse("c=sizeof(int*);");
        self.assertEqual(ast[0],
                         VariableAssignment(Variable("c"),
                                            SizeOf(PointerType("int"))))

    def test_sizeof_variable(self):
        ast = parser.parse("c=sizeof(a);");
        self.assertEqual(ast[0],
                         VariableAssignment(Variable("c"),
                                            SizeOf(Variable("a"))))


    def test_sizeof_expression(self):
        ast = parser.parse("c=sizeof(a+1);");
        self.assertEqual(ast[0],
                         VariableAssignment(Variable("c"),
                                            SizeOf(Add(Variable("a"),
                                                       Constant("char", 1)))))

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

    def test_if_else_simple(self):
        ast = parser.parse("""
            if (1) 
                return 42;
            else 
                return 24;
            """)
        self.assertEqual(ast[0], If(Constant("char", 1),
                                    [ Return(Constant("char", 42)) ],
                                    [ Return(Constant("char", 24)) ]))

    def test_if_else_dangling(self):
        # else should belong to the nearest if
        ast = parser.parse("""
            if (1) 
                if (2)
                    return 42;
                else 
                    return 24;
            """)
        self.assertEqual(ast[0], If(Constant("char", 1),
                                    [ If(Constant("char", 2),
                                        [ Return(Constant("char", 42)) ],
                                        [ Return(Constant("char", 24)) ])
                                     ]))

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
                                      [ StringConstant("hello")]))

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
        ast = parser.parse("struct mystruct { char foo; int bar; char* ptr; };")
        self.assertEqual(ast[0],
                         StructDefinition("mystruct",
                                          ( VariableDefinition("char", "foo"),
                                           VariableDefinition("int", "bar"),
                                           VariableDefinition(PointerType("char"), "ptr"))))

    def test_structVariable(self):
        ast = parser.parse("struct mystruct { char foo; }; struct mystruct s;")
        self.assertEqual(ast[0],
                         StructDefinition("mystruct",
                                          ( VariableDefinition("char", "foo"), )))
        self.assertEqual(ast[1],
                         VariableDefinition(Struct("mystruct"), "s"))

    def test_structFieldReference(self):
        ast = parser.parse("""struct mystruct { char foo; };
            void main() {
                struct mystruct s;
                s.foo = 42;
            }
            """)
        funAst = ast[1].statements
        self.assertEqual(funAst[1],
                         VariableAssignment(StructFieldReference(Variable("s"),
                                                                 "foo"),
                                            Constant("char", 42)))

    def test_nextedStructFieldReference(self):
        ast = parser.parse("""
            struct Foo { char a; char b; };
            struct Bar { int a; struct Foo foo; };
            void main() {
                struct Bar bar;
                bar.foo.b = 42;
            }
            """)
        funAst = ast[2].statements
        self.assertEqual(funAst[1],
                         VariableAssignment(StructFieldReference(StructFieldReference(Variable("bar"),
                                                                                      "foo"),
                                                                 "b"),
                                            Constant("char", 42)))

    def test_structInitializer(self):
        ast = parser.parse("""
            struct Foo { char a; char b; };
            struct Foo foo = { 42, 24 };
            """)
        self.assertEqual(ast[1],
                         VariableDefinition(Struct("Foo"),
                                            "foo",
                                            StructInitialization([Constant("char", 42),
                                                                  Constant("char", 24)])))

    def test_structInitializer_named(self):
        ast = parser.parse("""
            struct Foo { char a; char b; };
            struct Foo foo = { .b = 42, .a = 24 };
            """)
        self.assertEqual(ast[1],
                         VariableDefinition(Struct("Foo"),
                                            "foo",
                                            StructInitialization([("b", Constant("char", 42)),
                                                                  ("a", Constant("char", 24))])))

    def test_structInitializer_mixed(self):
        ast = parser.parse("""
            struct Foo { char a; char b; char c;};
            struct Foo foo = { .b = 42, 24 };
            """)
        self.assertEqual(ast[1],
                         VariableDefinition(Struct("Foo"),
                                            "foo",
                                            StructInitialization([("b", Constant("char", 42)),
                                                                  Constant("char", 24)])))

    def test_structInitializer_nested(self):
        ast = parser.parse("""
            struct Foo { char a; char b; };
            struct Bar { char c; struct Foo foo; };
            struct Bar bar = { 1, { 2, 3 } };
            """)
        self.assertEqual(ast[2],
                         VariableDefinition(Struct("Bar"),
                                            "bar",
                                            StructInitialization([Constant("char", 1),
                                                                  StructInitialization([Constant("char", 2),
                                                                                        Constant("char", 3)])])))


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
        self.assertFalse(ast[0].isVarArg)
        self.assertFalse(ast[0].isVarArg)
        self.assertEqual(ast[0].frameSize, 0)
        self.assertTrue(isinstance(block.statements[0], IRDefFun))
        self.assertEqual(block.statements[1], IRReturn("char", ConstantOperand("char", 0), "foo"))
        self.assertTrue(isinstance(block.statements[2], IRFunExit))

    def test_function_varArg(self):
        ast = parser.parse("void foo(int arg1, ...) { return 0; }")
        blockFactory = BlockFactory()
        context = ASTContext(blockFactory)
        symbolTable = ast[0].visit(context)
        self.assertIsInstance(ast[0], FunctionDefinition)
        self.assertTrue(ast[0].isVarArg)
        self.assertEqual(symbolTable["arg1"].impl.offset, +4) # First int arg at ix+4, ix+5

    def test_function_stackFrame(self):
        ast = parser.parse("char foo(char arg) { int i; }")
        blockFactory = BlockFactory()
        context = ASTContext(blockFactory)
        ast[0].visit(context)
        blocks = blockFactory.blocks()
        block = blocks["foo_0000"]
        self.assertEqual(ast[0].frameSize, 2)
        self.assertTrue(isinstance(block.statements[0], IRDefFun))
        self.assertFalse(ast[0].isVarArg)
        self.assertTrue(isinstance(block.statements[1], IRFunExit))

    def test_function_stackLayout_byteArgs(self):
        ast = parser.parse("char foo(char arg1, char arg2) { int iVar; char cVar; }")
        blockFactory = BlockFactory()
        context = ASTContext(blockFactory)
        symbolTable = ast[0].visit(context)
        self.assertEqual(symbolTable["arg1"].impl.offset, +5) # byte args are pushed as ints in the UPPER byte
        self.assertEqual(symbolTable["arg2"].impl.offset, +7)
        self.assertEqual(symbolTable["iVar"].impl.offset, -2) # (ix-2, ix-1)
        self.assertEqual(symbolTable["cVar"].impl.offset, -3) # (ix-3)

    def test_function_stackLayout_mixedArgs(self):
        ast = parser.parse("char foo(int arg1, char arg2) { char cVar; int iVar; }")
        blockFactory = BlockFactory()
        context = ASTContext(blockFactory)
        symbolTable = ast[0].visit(context)
        self.assertEqual(symbolTable["arg1"].impl.offset, +4) # First int arg at ix+4, ix+5
        self.assertEqual(symbolTable["arg2"].impl.offset, +7) # second arg sent as ix+6, ix+7 with the value in IX+7
        self.assertEqual(symbolTable["cVar"].impl.offset, -1) # (ix-1)
        self.assertEqual(symbolTable["iVar"].impl.offset, -3) # (ix-3, ix-2)

    def test_function_stackLayout_temps(self):
        # Reset for predictable test
        Temporary.NUM_TEMPS=0
        ast = parser.parse("void foo() { char a; char b = a + 1; }")
        blockFactory = BlockFactory()
        context = ASTContext(blockFactory)
        symbolTable = ast[0].visit(context)
        self.assertEqual(symbolTable["temp0"].impl, StackAddress(-3))

    def test_stackLayout_nestedStruct(self):
        ast = parser.parse("""
            struct Foo {
                char a;
                char b;
            };
            struct Bar {
                char c;
                struct Foo f;
            };
            void foo() {
               struct Bar bar;
               bar.f.b = 42;
            }""")
        blockFactory = BlockFactory()
        context = ASTContext(blockFactory)
        ast[0].visit(context)
        ast[1].visit(context)
        symbolTable = ast[2].visit(context)
        self.assertEqual(symbolTable["bar.f.b"].impl.offset, -1)

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

    def test_multiplication(self):
        ast = parser.parse("a=b*c;");
        self.assertEqual(ast[0],
                         VariableAssignment(Variable("a"),
                                            Mul(Variable("b"),
                                                Variable("c"))))

    def test_multiplication2(self):
        ast = parser.parse("a=b+c*d;");
        self.assertEqual(ast[0],
                         VariableAssignment(Variable("a"),
                                            Add(Variable("b"),
                                                Mul(Variable("c"),
                                                    Variable("d")))))
    def test_or(self):
        ast = parser.parse("a=b|c;");
        self.assertEqual(ast[0],
                         VariableAssignment(Variable("a"),
                                            BitwiseOr(Variable("b"),
                                                      Variable("c"))))

    def test_paranthesis(self):
        ast = parser.parse("a=b-(c+d);");
        self.assertEqual(ast[0],
                         VariableAssignment(Variable("a"),
                                            Subtraction(Variable("b"),
                                                                 Add(Variable("c"),
                                                                     Variable("d")))))

    #
    # bitwise closer than comparison
    #
    def test_priority1(self):
        ast = parser.parse("return a & b != c;")
        self.assertEqual(ast[0],
                         Return(Relation("!=",
                                         BitwiseAnd(Variable("a"),
                                                    Variable("b")),
                                         Variable("c"))))

    #
    # Control flow
    #
    def test_continue(self):
        ast = parser.parse("continue;")
        self.assertEqual(ast[0], Continue())


