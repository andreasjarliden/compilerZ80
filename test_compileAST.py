import unittest
from testutilities import compileBlockToIR, compileToBlocks, compile
from symbolTable import SymbolTable
from astnodes import *
from promotion import isConvertableTo, promotedType
from pprint import pprint

class TestConversion(unittest.TestCase):
    def testIsConvertableTo(self):
        self.assertTrue(isConvertableTo("char", "char"))
        self.assertTrue(isConvertableTo("int", "int"))
        self.assertTrue(isConvertableTo("char", "int"))
        self.assertFalse(isConvertableTo("int", "char"))
        self.assertTrue(isConvertableTo(PointerType("void"), PointerType("char")))
        self.assertTrue(isConvertableTo(PointerType("char"), PointerType("void")))
        self.assertFalse(isConvertableTo(PointerType("void"), "char"))
        self.assertFalse(isConvertableTo(PointerType("char"), PointerType("int")))
        self.assertFalse(isConvertableTo(PointerType("int"), PointerType("char")))

    def testPromotedType(self):
        self.assertEqual(promotedType("char", "char", "char", "char"), ("char", "char"))
        self.assertEqual(promotedType("int", PointerType("int"), "int", "int"), ("int", PointerType("int")))
        self.assertEqual(promotedType("int", PointerType("int"), "char", "char"), ("int", PointerType("int")))
        self.assertEqual(promotedType("char", "char", "int", PointerType("void")), ("int", PointerType("void")))

# TODO live should describe the liveness AT the instruction, so we now if it is
# free to spill
class TestLiveness(unittest.TestCase):
    def setUp(self):
        self.symbolTable = SymbolTable()
        self.typeEnv = TypeEnv()

    def compileBlockToIR(self, code):
        return compileBlockToIR(code, symbolTable = self.symbolTable, typeEnv = self.typeEnv)

    def isLive(self, irs, v):
        return irs.live[self.symbolTable.lookUp(v)]

    def test_1(self):
        irs = self.compileBlockToIR("""
char A;
char B;
A=1;
A=B; // A is dead, free to spill A
B=A+1;""")
        self.assertEqual(type(irs[0]), IRAssign)
        self.assertEqual(type(irs[1]), IRAssign)
        self.assertEqual(type(irs[2]), IRAdd)
        self.assertEqual(type(irs[3]), IRAssign)
        self.assertFalse(self.isLive(irs[0], "A")) # A=1
        self.assertFalse(self.isLive(irs[1], "A")) # A=2
        self.assertTrue(self.isLive(irs[3], "A")) # B=A+1

    def test_2(self):
        irs = self.compileBlockToIR("""
char A;
char B;
A=1;
B=A+1; // B becomes live afterwards but no next use (within block)
A=2;""")
        self.assertEqual(type(irs[0]), IRAssign)
        self.assertEqual(type(irs[1]), IRAdd)
        self.assertEqual(type(irs[2]), IRAssign)
        self.assertEqual(type(irs[3]), IRAssign)
        self.assertFalse(self.isLive(irs[0], "A")) # A=1
        self.assertTrue(self.isLive(irs[1], "A")) # A+1
        self.assertFalse(self.isLive(irs[2], "A")) # B=A+1
        self.assertFalse(self.isLive(irs[3], "A")) # A=2
        self.assertTrue(self.isLive(irs[3], "B")) # A=2

    def test_assignToPointer(self):
        blocks = compileToBlocks("""
        void main() {
            int tag = 0x8000;
            int* pChunkStart = (int*)42;
            *pChunkStart = tag;
            pChunkStart = (int*)0;
        }""", symbolTable = self.symbolTable)
        irs = blocks["main_0000"].statements
        self.assertIsInstance(irs[1], IRAssign)
        self.assertIsInstance(irs[2], IRAssign)
        self.assertIsInstance(irs[3], IRDereference)
        self.assertIsInstance(irs[4], IRAssignToPointer)
        # pCunkStart value 42 should be live at *pChunkStart = tag line as we are USING pChunkStart, not assigning it.
        self.assertEqual(irs[3].live[irs[2].resultAddr], True) 
        self.assertEqual(irs[4].live[irs[2].resultAddr], True) 

class TestErrorHandling(unittest.TestCase):
    # TODO duplication with above
    def setUp(self):
        self.symbolTable = SymbolTable()
        self.typeEnv = TypeEnv()

    def compileBlockToIR(self, code):
        return compileBlockToIR(code, symbolTable = self.symbolTable, typeEnv = self.typeEnv)

    #
    # Syntax error
    #
    def test_syntaxError(self):
        with self.assertRaises(CompileError) as cts:
            compileBlockToIR("""// comment
            =;""")
        self.assertIn("Syntax error", cts.exception.message)
        self.assertEqual(cts.exception.location.line, 2)

    def test_UnexpectedEnd(self):
        with self.assertRaises(CompileError) as cts:
            compileBlockToIR("""// line 1
            // line 2
            void foo(""")
        self.assertIn("Unexpected end of file", cts.exception.message)
        self.assertEqual(cts.exception.location.line, 3)

    #
    # Functions
    # 

    def test_missingFunction(self):
        with self.assertRaises(CompileError) as ctx:
            output = compile("""char main() {
                                foo();
                                return 0;
                              }""")
        self.assertEqual(ctx.exception.location.line, 2) 
        self.assertEqual(ctx.exception.message, "Attempting to call unknown function foo") 

    def test_callingNonFunction(self):
        with self.assertRaises(CompileError) as ctx:
            output = compile("""void main() {
                                    char foo;
                                    foo();
                              }""")
        self.assertEqual(ctx.exception.location.line, 3) 
        self.assertEqual(ctx.exception.message, "Attempting to call non-function foo") 

    def test_callingWrongNumberOfArguments(self):
        with self.assertRaises(CompileError) as ctx:
            output = compile("""void foo(char a, char b);
                                void main() {
                                    foo(1);
                              }""")
        self.assertEqual(ctx.exception.location.line, 3) 
        self.assertEqual(ctx.exception.message, "Attempting to call function foo with 1 arguments but expected 2") 

    def test_functionWithUnknownArgumentType1(self):
        with self.assertRaises(CompileError) as ctx:
            output = compile("""char foo(chur a) {
                                    return 0;
                                }
                                void main() {
                                    foo(1);
                              }""")
        self.assertEqual(ctx.exception.message, "Unknown type chur") 
        self.assertEqual(ctx.exception.location.line, 1) 

    def test_functionWithUnknownArgumentType2(self):
        with self.assertRaises(CompileError) as ctx:
            output = compile("""char foo(chur a);
                                void main() {
                                    foo(1);
                              }""")
        self.assertEqual(ctx.exception.message, "Unknown type chur") 
        self.assertEqual(ctx.exception.location.line, 1) 

    def test_functionWithUnknownReturnType1(self):
        with self.assertRaises(CompileError) as ctx:
            output = compile("""chur foo();
                                void main() {
                                    foo();
                              }""")
        self.assertEqual(ctx.exception.message, "Unknown type chur") 
        self.assertEqual(ctx.exception.location.line, 1) 

    def test_functionWithUnknownReturnType2(self):
        with self.assertRaises(CompileError) as ctx:
            output = compile("""chur foo() { return 0; }
                                void main() {
                                    foo();
                              }""")
        self.assertEqual(ctx.exception.message, "Unknown type chur") 
        self.assertEqual(ctx.exception.location.line, 1) 

    def test_function_redefine(self):
        with self.assertRaises(CompileError) as ctx:
            output = compile("""char foo() { return 0; }
                                char foo() { return 0; }
                              """)
        self.assertEqual(ctx.exception.message, "Redefinition of foo")
        self.assertEqual(ctx.exception.location.line, 2) 
        # This is allowed however
        compile("""char foo();
                   char foo() { return 0; }
                """)
        # TODO test conflicting function declarations

    def test_function_redefine2(self):
        with self.assertRaises(CompileError) as ctx:
            output = compile("""char foo;
                                char foo() { return 0; }
                              """)
        self.assertEqual(ctx.exception.message, "Redefinition of foo")
        self.assertEqual(ctx.exception.location.line, 2) 

    def test_function_redefine3(self):
        with self.assertRaises(CompileError) as ctx:
            output = compile("""char foo();
                                char foo() { return 0; }
                                char foo() { return 0; }
                              """)
        self.assertEqual(ctx.exception.message, "Redefinition of foo")
        self.assertEqual(ctx.exception.location.line, 3) 

    def test_callingVarArgFunction(self):
        blocks = compileToBlocks("""
            void printf(char* format, ...);
            void main() {
                printf("foo %d", (int)42);
            }""")
        irs = blocks["main_0000"].statements
        pprint(irs)
        self.assertIsInstance(irs[0], IRDefFun)
        self.assertIsInstance(irs[1], IRArgument)
        self.assertEqual(irs[1].lhsAddr.completeType, "int")
        self.assertIsInstance(irs[2], IRArgument)
        self.assertEqual(irs[2].lhsAddr.completeType, PointerType("char"))
        self.assertIsInstance(irs[3], IRFunCall)

    def test_functionFrameSize(self):
        blocks = compileToBlocks("""void main() {
                                        char c;
                                        while (1) {
                                            int i;
                                        }
                                        while (1) {
                                            int i;
                                        }
                                      }""")
        irs = blocks["main_0000"].statements
        self.assertEqual(irs[0].function.frameSize, 5);


    #
    # Variable reference
    #
    def test_undefinedVariable(self):
        with self.assertRaises(CompileError) as cts:
            compile("""char main() {
                         return 1 + a;
                       }""")
        self.assertEqual(cts.exception.message, "Attempting to reference unknown a")
        self.assertEqual(cts.exception.location.line, 2)

    def test_ifLocalScope(self):
        with self.assertRaises(CompileError) as cts:
            compile("""void main() {
                            if (1) {
                                int a;
                            }
                            int b = a;
                       }""")
        self.assertEqual(cts.exception.message, "Attempting to reference unknown a")
        self.assertEqual(cts.exception.location.line, 5)

    def test_whileLocalScope(self):
        with self.assertRaises(CompileError) as cts:
            compile("""void main() {
                            int t;
                            while (t) {
                                int a;
                            }
                            int b = a;
                       }""")
        self.assertEqual(cts.exception.message, "Attempting to reference unknown a")
        self.assertEqual(cts.exception.location.line, 6)

    #
    # If
    #
    def test_if(self):
        blocks = compileToBlocks("""
            void main() {
                char i;
                if (i == 0)
                    i=42;
                i=24;
            }""")
        irs = blocks["main_0000"].statements
        self.assertIsInstance(irs[1], IRIfRelation)
        elseLabel = irs[1].elseLabel
        irs = blocks["main_0001"].statements
        self.assertIsInstance(irs[0], IRAssign)
        self.assertEqual(irs[0].exprAddr, Constant("char", 42))
        self.assertIsInstance(irs[1], IRSpillAll)
        self.assertEqual(len(irs), 2)
        irs = blocks["main_0002"].statements
        self.assertIsInstance(irs[0], IRLabel)
        self.assertEqual(irs[0].label, elseLabel)
        self.assertIsInstance(irs[1], IRAssign)
        self.assertEqual(irs[1].exprAddr, Constant("char", 24))

    def test_if_else(self):
        blocks = compileToBlocks("""
            void main() {
                char i;
                if (i == 0)
                    i=42;
                else
                    i=11;
                i=24;
            }""")
        irs = blocks["main_0000"].statements
        self.assertIsInstance(irs[1], IRIfRelation)
        elseLabel = irs[1].elseLabel
        irs = blocks["main_0001"].statements
        self.assertIsInstance(irs[0], IRAssign)
        self.assertEqual(irs[0].exprAddr, Constant("char", 42))
        self.assertIsInstance(irs[1], IRSpillAll)
        self.assertIsInstance(irs[2], IRJump)
        afterLabel = irs[2].label
        self.assertEqual(len(irs), 3)
        irs = blocks["main_0002"].statements
        self.assertIsInstance(irs[0], IRLabel)
        self.assertEqual(irs[0].label, elseLabel)
        self.assertIsInstance(irs[1], IRAssign)
        self.assertEqual(irs[1].exprAddr, Constant("char", 11))
        self.assertIsInstance(irs[2], IRSpillAll)
        self.assertEqual(len(irs), 3)

        irs = blocks["main_0003"].statements
        self.assertIsInstance(irs[0], IRLabel)
        self.assertEqual(irs[0].label, afterLabel)
        self.assertIsInstance(irs[1], IRAssign)
        self.assertEqual(irs[1].exprAddr, Constant("char", 24))


    #
    # While
    #
    def test_while_int_char(self):
        blocks = compileToBlocks("""
            void main() {
                int i;
                while(i != 0) {
                    i = i - 1;
                }
            }""")
        irs = blocks["main_0001"].statements
        self.assertIsInstance(irs[1], IRIfRelation)
        self.assertEqual(irs[1].lhsAddr.type, "int")
        self.assertEqual(irs[1].rhsAddr.type, "int")

    #
    # Continue
    #
    def test_while_continue(self):
        blocks = compileToBlocks("""
            void main() {
                char a;
                while(1) {
                    a = 42; 
                    continue;
                    a = 24;
                }
            }""")
        irs = blocks["main_0001"].statements
        self.assertIsInstance(irs[0], IRLabel)
        loopLabel = irs[0].label
        irs = blocks["main_0002"].statements
        self.assertIsInstance(irs[0], IRAssign)
        self.assertEqual(irs[0].exprAddr, Constant("char", 42))
        self.assertIsInstance(irs[1], IRSpillAll)
        self.assertIsInstance(irs[2], IRJump)
        self.assertEqual(irs[2].label, loopLabel)

    def test_nestedWhile_continue(self):
        blocks = compileToBlocks("""
            void main() {
                char a;
                while(1) {
                    while (2) {
                        continue;
                        a=24;
                    }
                    continue;
                    a = 42; 
                }
            }""")
        irs = blocks["main_0001"].statements
        self.assertIsInstance(irs[0], IRLabel)
        outerLoopLabel = irs[0].label
        irs = blocks["main_0003"].statements
        self.assertIsInstance(irs[0], IRLabel)
        innerLoopLabel = irs[0].label

        # Inner block
        irs = blocks["main_0004"].statements
        self.assertIsInstance(irs[0], IRSpillAll)
        self.assertIsInstance(irs[1], IRJump)
        self.assertEqual(irs[1].label, innerLoopLabel)
        self.assertIsInstance(irs[2], IRAssign)
        self.assertEqual(irs[2].exprAddr, Constant("char", 24))

        # Outer block
        irs = blocks["main_0005"].statements
        self.assertIsInstance(irs[0], IRLabel)
        self.assertIsInstance(irs[1], IRSpillAll)
        self.assertIsInstance(irs[2], IRJump)
        self.assertEqual(irs[2].label, outerLoopLabel)
        self.assertIsInstance(irs[3], IRAssign)
        self.assertEqual(irs[3].exprAddr, Constant("char", 42))


    def test_while_continueOutisdeLoop(self):
        with self.assertRaises(CompileError) as cts:
          compileToBlocks("""
            void main() {
                char a;
                while(1) {
                    a = 42; 
                }
                continue;
            }""")
        self.assertEqual(cts.exception.message, "Continue outside loop")
        self.assertEqual(cts.exception.location.line, 7)

    #
    # Variable definition
    #
    def test_vardef_unknownType(self):
        with self.assertRaises(CompileError) as cts:
            compileBlockToIR("""int b;
                            chur a;""")
        self.assertEqual(cts.exception.message, "Unknown type chur")
        self.assertEqual(cts.exception.location.line, 2)

    def test_vardef_alreadyDefined(self):
        with self.assertRaises(CompileError) as cts:
            compileBlockToIR("""int a;
                            int a;""")
        self.assertEqual(cts.exception.message, "Attempt to define already defined a")
        self.assertEqual(cts.exception.location.line, 2)

        # Allowed
        compile("""
            int a;
            void main() {
                int a;
            }""")

        # Allowed
        compile("""
            void main() {
                int a;
                while (1 == 1) {
                    int a;
                }
            }""")

    #
    # Structs
    #
    def test_struct_known(self):
        self.compileBlockToIR("struct foo { char a; }; struct foo s;");
        self.assertEqual(self.typeEnv.lookupStructName("foo"), StructType("foo", { "a": StructField("char", "a", 0)}))

    def test_struct_unknown(self):
        with self.assertRaises(CompileError) as cts:
            compileBlockToIR("struct missing s;");
        self.assertEqual(cts.exception.message, "Unknown struct missing")
        self.assertEqual(cts.exception.location.line, 1)

    def test_struct_redefine(self):
        with self.assertRaises(CompileError) as cts:
            compileBlockToIR("struct foo { char a; }; struct foo { char b; };")
        self.assertEqual(cts.exception.message, "Redefinition of struct foo")
        self.assertEqual(cts.exception.location.line, 1)

    def test_struct_localToScope(self):
        with self.assertRaises(CompileError) as cts:
            compile("""
                void foo() {
                    struct foo { char a; };
                }
                void bar() {
                    struct foo s;
                }""")
        self.assertEqual(cts.exception.message, "Unknown struct foo")
        self.assertEqual(cts.exception.location.line, 6)

    def test_struct_assignField(self):
        blocks = compileToBlocks("""
            struct myStruct{ char a; char b; };
            char main() {
                char a;
                struct myStruct s;
                char c;
                a = 0;
                s.a = 1;
                s.b = 2;
                c = 3;
            }""")
        irs = blocks["main_0000"].statements
        self.assertIsInstance(irs[1], IRAssign)
        self.assertEqual(irs[1].resultAddr.impl, StackAddress(-1))
        self.assertEqual(irs[1].lhsAddr, Constant("char", 0))
        self.assertIsInstance(irs[2], IRAssign)
        self.assertEqual(irs[2].resultAddr.impl, StackAddress(-3))
        self.assertEqual(irs[2].lhsAddr, Constant("char", 1))
        self.assertIsInstance(irs[3], IRAssign)
        self.assertEqual(irs[3].resultAddr.impl, StackAddress(-2))
        self.assertEqual(irs[3].lhsAddr, Constant("char", 2))
        self.assertIsInstance(irs[4], IRAssign)
        self.assertEqual(irs[4].resultAddr.impl, StackAddress(-4))
        self.assertEqual(irs[4].lhsAddr, Constant("char", 3))

    def test_globalStruct_assignField(self):
        blocks = compileToBlocks("""
            struct myStruct{ int a; char b; };
            struct myStruct s;
            char main() {
                s.a = (int)1;
                s.b = 2;
            }""")
        irs = blocks["main_0000"].statements
        self.assertIsInstance(irs[1], IRAssign)
        self.assertEqual(irs[1].lhsAddr, Constant("int", 1))
        self.assertEqual(irs[1].resultAddr.impl, GlobalAddress("s", 0))
        self.assertEqual(irs[2].lhsAddr, Constant("char", 2))
        self.assertEqual(irs[2].resultAddr.impl, GlobalAddress("s", 2))

    def test_struct_referenceField(self):
        blocks = compileToBlocks("""
            struct myStruct { char a; };
            char main() {
                char a;
                struct myStruct s;
                s.a = 1;
                a = s.a;
            }""")
        irs = blocks["main_0000"].statements
        # TODO

    def test_struct_initializer(self):
        blocks = compileToBlocks("""
            struct myStruct { char foo; char bar; };
            char main() {
                struct myStruct s = { 42, 24 };
            }""")
        irs = blocks["main_0000"].statements
        self.assertIsInstance(irs[1], IRAssign)
        self.assertEqual(irs[1].resultAddr.name, "s.foo")
        self.assertEqual(irs[1].resultAddr.impl, StackAddress(-2))
        self.assertEqual(irs[1].lhsAddr, Constant("char", 42))
        self.assertIsInstance(irs[2], IRAssign)
        self.assertEqual(irs[2].resultAddr.name, "s.bar")
        self.assertEqual(irs[2].resultAddr.impl, StackAddress(-1))
        self.assertEqual(irs[2].lhsAddr, Constant("char", 24))

    def test_struct_namedInitializer(self):
        blocks = compileToBlocks("""
            struct myStruct { char foo; char bar; };
            char main() {
                struct myStruct s = { .bar = 42, .foo = 24 };
            }""")
        irs = blocks["main_0000"].statements
        self.assertIsInstance(irs[1], IRAssign)
        self.assertEqual(irs[1].resultAddr.name, "s.bar")
        self.assertEqual(irs[1].resultAddr.impl, StackAddress(-1))
        self.assertEqual(irs[1].lhsAddr, Constant("char", 42))
        self.assertIsInstance(irs[2], IRAssign)
        self.assertEqual(irs[2].resultAddr.name, "s.foo")
        self.assertEqual(irs[2].resultAddr.impl, StackAddress(-2))
        self.assertEqual(irs[2].lhsAddr, Constant("char", 24))

    def test_struct_mixedInitializer(self):
        blocks = compileToBlocks("""
            struct myStruct { char foo; char bar; char baz; };
            char main() {
                struct myStruct s = { .bar = 42, 24 };
            }""")
        irs = blocks["main_0000"].statements
        self.assertIsInstance(irs[1], IRAssign)
        self.assertEqual(irs[1].resultAddr.name, "s.bar")
        self.assertEqual(irs[1].lhsAddr, Constant("char", 42))
        self.assertIsInstance(irs[2], IRAssign)
        self.assertEqual(irs[2].resultAddr.name, "s.baz")
        self.assertEqual(irs[2].lhsAddr, Constant("char", 24))

    def test_struct_recursiveInitializer(self):
        blocks = compileToBlocks("""
            struct Foo { char a; char b; };
            struct Bar { char c; struct Foo foo; };
            char main() {
                struct Bar s = { 'c', { 'a', 'b' } };
            }""")
        irs = blocks["main_0000"].statements
        pprint(irs)
        self.assertIsInstance(irs[1], IRAssign)
        self.assertEqual(irs[1].resultAddr.name, "s.c")
        self.assertEqual(irs[1].lhsAddr, Constant("char", ord("c")))
        self.assertIsInstance(irs[2], IRAssign)
        self.assertEqual(irs[2].resultAddr.name, "s.foo.a")
        self.assertEqual(irs[2].lhsAddr, Constant("char", ord("a")))
        self.assertIsInstance(irs[3], IRAssign)
        self.assertEqual(irs[3].resultAddr.name, "s.foo.b")
        self.assertEqual(irs[3].lhsAddr, Constant("char", ord("b")))

    # Test error conditations, wrong field name, too many initializers, not struct

    def test_structPointer_referenceField(self):
        blocks = compileToBlocks("""
            struct myStruct { int a; char b; };
            char main() {
                struct myStruct* s;
                s->b = 1;
            }""")
        irs = blocks["main_0000"].statements
        self.assertIsInstance(irs[1], IRDereference)
        self.assertIsInstance(irs[2], IRAdd)
        self.assertTrue(irs[1].resultAddr, irs[2].lhsAddr)
        self.assertEqual(irs[2].rhsAddr, Constant("int", 2))
        self.assertIsInstance(irs[3], IRAssignToPointer)
        self.assertTrue(irs[2].resultAddr, irs[3].lhsAddr)

    def test_structPointer_anonymousStruct(self):
        blocks = compileToBlocks("""
            struct myStruct { int a; char b; };
            char main() {
                ((struct myStruct*)0)->b = 42;
            }""")
        irs = blocks["main_0000"].statements
        pprint(irs)
        self.assertIsInstance(irs[1], IRDereference)
        self.assertIsInstance(irs[2], IRAssignToPointer)
        self.assertEqual(irs[2].lhsAddr, Constant(PointerType("char"), 2))
        self.assertEqual(irs[2].rhsAddr, Constant("char", 42))

    def test_structPointer_repeatedFieldReference(self):
        blocks = compileToBlocks("""
            struct myStruct { char a; };
            void main() {
                struct myStruct* s;
                char a = s->a;
                char b = s->a;
            }""")
        irs = blocks["main_0000"].statements
        pprint(irs)
        self.assertIsInstance(irs[1], IRDereference) # *s
        self.assertIsInstance(irs[2], IRAdd) # computing s->a
        self.assertIsInstance(irs[3], IRAssign)
        self.assertIsInstance(irs[4], IRDereference) # *s
        self.assertIsInstance(irs[5], IRDereference) # deref s-> pointer 
        self.assertIsInstance(irs[6], IRAssign) # re-uses s->a
        s_a_pointer = irs[3].lhsAddr.impl.pointer # pointer used for s->a
        self.assertTrue(irs[5].live[s_a_pointer]) # the pointer is used for the second s->a so must be live
        self.assertFalse(irs[6].live[s_a_pointer]) 

    def test_struct_missingField(self):
        with self.assertRaises(CompileError) as cts:
            blocks = compileToBlocks("""
                struct myStruct { char a; };
                char main() {
                    char a;
                    struct myStruct s;
                    s.b = 1;
                }""")
        self.assertEqual(cts.exception.message, "Unknown field b in struct myStruct")
        self.assertEqual(cts.exception.location.line, 6)

    def test_struct_unknownFieldType(self):
        with self.assertRaises(CompileError) as cts:
            blocks = compileToBlocks("""
                struct myStruct {
                    chur a;
                };
                char main() {
                    char a;
                    struct myStruct s;
                    s.b = 1;
                }""")
        self.assertEqual(cts.exception.message, "Unknown type chur")
        self.assertEqual(cts.exception.location.line, 3)

    def test_recursiveStruct(self):
        typeEnv = TypeEnv()
        irs = compileBlockToIR("""
            struct myStruct {
                struct myStruct* pMyStruct;
            };
            """, typeEnv=typeEnv)
        pprint(typeEnv)
        self.assertEqual(typeEnv.lookupStructName("myStruct").fields["pMyStruct"].completeType, PointerType(StructType("myStruct", ())))

    def test_struct_nestedStruct(self):
        blocks = compileToBlocks("""
            struct Foo {
                char a;
                char b;
            };
            struct Bar {
                char c;
                struct Foo f;
            };
            void main() {
               struct Bar bar;
               bar.f.b = 42;
               bar.c = 24;
            }""")
        irs = blocks["main_0000"].statements
        self.assertIsInstance(irs[1], IRAssign)
        self.assertEqual(irs[1].resultAddr.impl, StackAddress(-1))
        self.assertIsInstance(irs[2], IRAssign)
        self.assertEqual(irs[2].resultAddr.impl, StackAddress(-3))

    #
    # Assignments
    #

    def test_assignmentAsExpression(self):
        blocks = compileToBlocks("""
            void main() {
                int* a;
                int b = *(a = (int*)42);
            }""")
        irs = blocks["main_0000"].statements
        self.assertIsInstance(irs[1], IRAssign)
        self.assertIsInstance(irs[2], IRDereference)
        self.assertEqual(irs[2].resultAddr.impl.pointer, irs[1].resultAddr)
        self.assertIsInstance(irs[3], IRAssign)
        self.assertEqual(irs[3].lhsAddr, irs[2].resultAddr)

    def test_assing_nonLValue(self):
        with self.assertRaises(CompileError) as cts:
            compileBlockToIR("""1 = 2;""")
        self.assertIn("Can't assign to non-lvalue", cts.exception.message)
        self.assertEqual(cts.exception.location.line, 1)

    def test_conflictingTypes(self):
        with self.assertRaises(CompileError) as cts:
            compileBlockToIR("""char a;
                    int *p;
                    p = a;""")
        self.assertEqual(cts.exception.message, "Can't convert char to int* in assignment")
        self.assertEqual(cts.exception.location.line, 3)

    def test_assignment_charToIntPromotion(self):
        irs = compileBlockToIR("int i; char c; i = c;")
        self.assertIsInstance(irs[0], IRPromote)
        self.assertIsInstance(irs[1], IRAssign)
        self.assertEqual(irs[1].lhsAddr, irs[0].resultAddr) 

    def test_assignment_narrowing(self):
        with self.assertRaises(CompileError) as cts:
            compileBlockToIR("""
            int i;
            char c;
            c = i;""")
        self.assertEqual(cts.exception.message, "Can't convert int to char in assignment")
        self.assertEqual(cts.exception.location.line, 4)

    def test_varDef_charToIntPromotion(self):
        blocks = compileToBlocks("void main() { char c;int i = c; }")
        irs = blocks["main_0000"].statements[1:]
        self.assertIsInstance(irs[0], IRPromote)
        self.assertIsInstance(irs[1], IRAssign)
        self.assertEqual(irs[1].lhsAddr, irs[0].resultAddr) 

    def test_varDef_narrowing(self):
        with self.assertRaises(CompileError) as cts:
            compileToBlocks("""void main() {
            int i;
            char c = i;
        }""");
        self.assertEqual(cts.exception.message, "Can't convert int to char in assignment")
        self.assertEqual(cts.exception.location.line, 3)

    def test_argPass_charToIntPromotion(self):
        blocks = compileToBlocks("""
            char f(int i) { return 0; } 
            void main() {
                f(42);
            }""")
        irs = blocks["main_0000"].statements[1:]
        print(irs)
        self.assertIsInstance(irs[0], IRArgument)
        self.assertEqual(irs[0].lhsAddr, Constant("int", 42))

    def test_argPass_narrowing(self):
        with self.assertRaises(CompileError) as cts:
            compileToBlocks("""
            char f(char c) { return 0; } 
            void main() {
                int i;
                f(i);
            }""");
        self.assertEqual(cts.exception.message, "Can't convert int to char in argument c")
        self.assertEqual(cts.exception.location.line, 5)

    def test_pointerWithAbsoluteValue(self):
        irs = compileBlockToIR("""int *p;
        p = (int*)0x8000;""")
        self.assertIsInstance(irs[0], IRAssign)
        self.assertIsInstance(irs[0].lhsAddr, Constant)
        self.assertEqual(irs[0].lhsAddr.completeType, PointerType("int"))

    def test_structPointer(self):
        blocks = compileToBlocks("""struct Foo { int a; int b; };
        void main() {
            struct Foo foo;
            struct Foo* pFoo = &foo;
        }""")
        irs = blocks["main_0000"].statements[1:]
        pprint(irs)
        self.assertIsInstance(irs[0], IRAddressOf)
        self.assertIsInstance(irs[1], IRAssign)
        self.assertEqual(irs[0].resultAddr.completeType, PointerType(StructType("Foo", ())))

    def test_pointerArithmeticDereference(self):
        blocks = compileToBlocks("""
            void main() {
                char *p = (char*)0x8000;
                char i = *(p+1);
            }""")
        irs = blocks["main_0000"].statements[1:]
        pprint(irs)
        self.assertIsInstance(irs[0], IRAssign)
        self.assertIsInstance(irs[1], IRAdd)
        self.assertEqual(irs[1].lhsAddr, irs[0].resultAddr)
        self.assertEqual(irs[1].rhsAddr, Constant(PointerType("char"), 1))
        self.assertIsInstance(irs[2], IRDereference)
        self.assertEqual(irs[2].lhsAddr, irs[1].resultAddr)

    def test_pointerArithmeticDereference2(self):
        blocks = compileToBlocks("""
            void main() {
                int *p = (int*)0x8000;
                *(p+1) = 42;
            }""")
        irs = blocks["main_0000"].statements[1:]
        pprint(irs)
        self.assertIsInstance(irs[0], IRAssign)
        self.assertIsInstance(irs[1], IRAdd)
        self.assertEqual(irs[1].lhsAddr, irs[0].resultAddr)
        self.assertEqual(irs[1].rhsAddr, Constant(PointerType("int"), 2))
        self.assertIsInstance(irs[2], IRDereference)
        self.assertEqual(irs[2].lhsAddr, irs[1].resultAddr)

    def test_dereferenceNonPointer(self):
        with self.assertRaises(CompileError) as cts:
            compileToBlocks("""
            char main() {
                char i;
                char t = *i;
            }""");
        self.assertEqual(cts.exception.message, "Attempt to dereference non-pointer i of type char")
        self.assertEqual(cts.exception.location.line, 4)

    def test_dereferenceVoidPointer(self):
        with self.assertRaises(CompileError) as cts:
            compileToBlocks("""
            char main() {
                void* p;
                char t = *p;
            }""");
        self.assertEqual(cts.exception.message, "Attempt to dereference void pointer p")
        self.assertEqual(cts.exception.location.line, 4)

    def test_pointerWithPointerArithmetics(self):
        with self.assertRaises(CompileError) as cts:
            compileToBlocks("""
            char main() {
                void* p1;
                void* p2;
                void* p3 = p1 + p2;
            }""");
        self.assertEqual(cts.exception.message, "Can't add void* and void*")
        self.assertEqual(cts.exception.location.line, 5)

    #
    # sizeof
    #
    def test_sizeof_types(self):
        blocks = compileToBlocks("""
            struct myStruct {
                int i;
                char c;
            };
            void main() {
                int sInt = sizeof(int);
                int sChar = sizeof(char);
                int sCharPointer = sizeof(char*);
                int sStruct = sizeof(struct myStruct);
                int sStringLiteral = sizeof("hello");
            }""")
        irs = blocks["main_0000"].statements[1:]
        pprint(irs)
        self.assertIsInstance(irs[0], IRAssign)
        self.assertEqual(irs[0].resultAddr.name, "sInt")
        self.assertEqual(irs[0].resultAddr.name, "sInt")
        self.assertIsInstance(irs[1], IRAssign)
        self.assertEqual(irs[1].resultAddr.name, "sChar")
        self.assertEqual(irs[1].exprAddr, Constant("int", 1))
        self.assertIsInstance(irs[2], IRAssign)
        self.assertEqual(irs[2].resultAddr.name, "sCharPointer")
        self.assertEqual(irs[2].exprAddr, Constant("int", 2))
        self.assertIsInstance(irs[3], IRAssign)
        self.assertEqual(irs[3].resultAddr.name, "sStruct")
        self.assertEqual(irs[3].exprAddr, Constant("int", 3))
        self.assertIsInstance(irs[4], IRAssign)
        self.assertEqual(irs[4].resultAddr.name, "sStringLiteral")
        self.assertEqual(irs[4].exprAddr, Constant("int", 6))

    def test_sizeof_expression(self):
        blocks = compileToBlocks("""
            void main() {
                char c;
                int sC = sizeof(c);
                int sExpr = sizeof(c+(int)1);
            }""")
        irs = blocks["main_0000"].statements[1:]
        self.assertIsInstance(irs[0], IRAssign)
        self.assertEqual(irs[0].resultAddr.name, "sC")
        self.assertEqual(irs[0].exprAddr, Constant("int", 1))
        # Note, this also ensures no code is generated for the addition
        self.assertIsInstance(irs[1], IRAssign)
        self.assertEqual(irs[1].resultAddr.name, "sExpr")
        self.assertEqual(irs[1].exprAddr, Constant("int", 2))

    def test_sizeof_missing(self):
        with self.assertRaises(CompileError) as cts:
            compileToBlocks("""
            char main() {
                int s = sizeof(foo);
            }""");
        self.assertEqual(cts.exception.message, "Attempting to reference unknown foo")
        self.assertEqual(cts.exception.location.line, 3)

    #
    # Arithmetics
    #
    def test_addChar(self):
        irs = compileBlockToIR("char a;char b;a=a+b;")
        self.assertIsInstance(irs[0], IRAdd)
        self.assertEqual(irs[0].lhsAddr.name, "a")
        self.assertEqual(irs[0].rhsAddr.name, "b")
        self.assertIsInstance(irs[1], IRAssign)
        self.assertEqual(irs[1].lhsAddr, irs[0].resultAddr) 

    def test_addCharAndInt(self):
        irs = compileBlockToIR("char c;int i;i=c+i;")
        self.assertIsInstance(irs[0], IRPromote)
        self.assertEqual(irs[0].lhsAddr.name, "c")
        self.assertIsInstance(irs[1], IRAdd)
        self.assertEqual(irs[1].lhsAddr, irs[0].resultAddr)
        self.assertEqual(irs[1].rhsAddr.name, "i")

    def test_addIntAndChar(self):
        irs = compileBlockToIR("char c;int i;i=i+c;")
        self.assertIsInstance(irs[0], IRPromote)
        self.assertEqual(irs[0].lhsAddr.name, "c")
        self.assertIsInstance(irs[1], IRAdd)
        self.assertEqual(irs[1].lhsAddr.name, "i")
        self.assertEqual(irs[1].rhsAddr, irs[0].resultAddr)

    def test_subChar(self):
        irs = compileBlockToIR("char a;char b;a=a-b;")
        self.assertIsInstance(irs[0], IRSub)
        self.assertEqual(irs[0].lhsAddr.name, "a")
        self.assertEqual(irs[0].rhsAddr.name, "b")
        self.assertIsInstance(irs[1], IRAssign)
        self.assertEqual(irs[1].lhsAddr, irs[0].resultAddr) 

    def test_mulIntAndConst(self):
        irs = compileBlockToIR("int i;i=i*3;")
        self.assertIsInstance(irs[0], IRMul)
        self.assertEqual(irs[0].lhsAddr.name, "i")
        self.assertEqual(irs[0].rhsAddr, Constant("char", 3))

    #
    # Pointer arithmetics
    #
    def test_pointerConstantArithmeticsAdd(self):
        irs = compileBlockToIR("char* p;p=p+1;")
        self.assertIsInstance(irs[0], IRAdd)
        self.assertEqual(irs[0].rhsAddr, Constant(PointerType("char"), 1))

        irs = compileBlockToIR("int* p;p=p+1;")
        self.assertIsInstance(irs[0], IRAdd)
        self.assertEqual(irs[0].rhsAddr, Constant(PointerType("int"), 2))

        irs = compileBlockToIR("int* p;p=2+p;")
        self.assertIsInstance(irs[0], IRAdd)
        self.assertEqual(irs[0].lhsAddr, Constant(PointerType("int"), 4))

        irs = compileBlockToIR("void* p;p=p+1;")
        self.assertIsInstance(irs[0], IRAdd)
        self.assertEqual(irs[0].rhsAddr, Constant(PointerType("void"), 1))

    def test_pointerConstantArithmeticsSub(self):
        irs = compileBlockToIR("char* p;p=p-1;")
        self.assertIsInstance(irs[0], IRSub)
        self.assertEqual(irs[0].rhsAddr, Constant(PointerType("char"), 1))

        irs = compileBlockToIR("int* p;p=p-1;")
        self.assertIsInstance(irs[0], IRSub)
        self.assertEqual(irs[0].rhsAddr, Constant(PointerType("int"), 2))

        irs = compileBlockToIR("int* p;p=2-p;")
        self.assertIsInstance(irs[0], IRSub)
        self.assertEqual(irs[0].lhsAddr, Constant(PointerType("int"), 4))

        irs = compileBlockToIR("void* p;p=p-1;")
        self.assertIsInstance(irs[0], IRSub)
        self.assertEqual(irs[0].rhsAddr, Constant(PointerType("void"), 1))


    #
    # Comparisons
    #
    def test_comparison_pointerAndNonPointer(self):
        with self.assertRaises(CompileError) as cts:
            compileToBlocks("""
            char main() {
                char* cp;
                char c;
                if (c == cp) {
                    c = 42;
                }
            }""");
        self.assertEqual(cts.exception.message, "Comparisson between pointer and non-pointer: char and char*")
        self.assertEqual(cts.exception.location.line, 5)

    def test_comparison_differentPointers(self):
        with self.assertRaises(CompileError) as cts:
            compileToBlocks("""
            char main() {
                char* cp;
                int* ip;
                if (ip == cp) {
                    c = 42;
                }
            }""");
        self.assertEqual(cts.exception.message, "Comparisson between different pointer types: int* and char*")
        self.assertEqual(cts.exception.location.line, 5)


