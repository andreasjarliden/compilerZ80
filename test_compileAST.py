import unittest
from testutilities import compileBlockToIR, compileToBlocks, compile
from symbolTable import SymbolTable
from astnodes import *
from pprint import pprint

class TestConversion(unittest.TestCase):
    def testIsConvertableTo(self):
        self.assertTrue(isConvertableTo("char", "char"))
        self.assertTrue(isConvertableTo("int", "int"))
        self.assertTrue(isConvertableTo("char", "int"))
        self.assertFalse(isConvertableTo("int", "char"))
        self.assertTrue(isConvertableTo("void*", "char*"))
        self.assertTrue(isConvertableTo("char*", "void*"))
        self.assertFalse(isConvertableTo("void*", "char"))
        self.assertFalse(isConvertableTo("char*", "int*"))
        self.assertFalse(isConvertableTo("int*", "char*"))

    def testPromotedType(self):
        self.assertEqual(promotedType("char", "char", "char", "char"), ("char", "char"))
        self.assertEqual(promotedType("int", "int*", "int", "int"), ("int", "int*"))
        self.assertEqual(promotedType("int", "int*", "char", "char"), ("int", "int*"))
        self.assertEqual(promotedType("char", "char", "int", "void*"), ("int", "void*"))

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
    # Variable definition
    #
    def test_vardef_unknownType(self):
        with self.assertRaises(CompileError) as cts:
            compileBlockToIR("""int b;
                            chur a;""")
        self.assertEqual(cts.exception.message, "Unknown type chur")
        self.assertEqual(cts.exception.location.line, 2)

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
        self.assertIsInstance(irs[0], IRPromote)
        self.assertIsInstance(irs[1], IRArgument)
        self.assertEqual(irs[1].lhsAddr, irs[0].resultAddr) 

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
        self.assertEqual(irs[0].lhsAddr.completeType, "int*")

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
        self.assertEqual(irs[1].rhsAddr, Constant("char*", 1))
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
        self.assertEqual(irs[1].rhsAddr, Constant("int*", 2))
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
        self.assertEqual(irs[0].rhsAddr, Constant("char*", 1))

        irs = compileBlockToIR("int* p;p=p+1;")
        self.assertIsInstance(irs[0], IRAdd)
        self.assertEqual(irs[0].rhsAddr, Constant("int*", 2))

        irs = compileBlockToIR("int* p;p=2+p;")
        self.assertIsInstance(irs[0], IRAdd)
        self.assertEqual(irs[0].lhsAddr, Constant("int*", 4))

        irs = compileBlockToIR("void* p;p=p+1;")
        self.assertIsInstance(irs[0], IRAdd)
        self.assertEqual(irs[0].rhsAddr, Constant("void*", 1))

    def test_pointerConstantArithmeticsSub(self):
        irs = compileBlockToIR("char* p;p=p-1;")
        self.assertIsInstance(irs[0], IRSub)
        self.assertEqual(irs[0].rhsAddr, Constant("char*", 1))

        irs = compileBlockToIR("int* p;p=p-1;")
        self.assertIsInstance(irs[0], IRSub)
        self.assertEqual(irs[0].rhsAddr, Constant("int*", 2))

        irs = compileBlockToIR("int* p;p=2-p;")
        self.assertIsInstance(irs[0], IRSub)
        self.assertEqual(irs[0].lhsAddr, Constant("int*", 4))

        irs = compileBlockToIR("void* p;p=p-1;")
        self.assertIsInstance(irs[0], IRSub)
        self.assertEqual(irs[0].rhsAddr, Constant("void*", 1))





