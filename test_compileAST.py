import unittest
from testutilities import compileBlockToIR, compileToBlocks, compile
from symbolTable import SymbolTable
from astnodes import *


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
        self.assertEqual(ctx.exception.message, "Attempting to call unknown foo") 

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

    #
    # Assignments
    #

    def test_conflictingTypes(self):
        with self.assertRaises(CompileError) as cts:
            compileBlockToIR("""char a;
                    int *p;
                    p = a;""")
        self.assertEqual(cts.exception.message, "Can't convert char to int* in assignment")
        self.assertEqual(cts.exception.location.line, 3)

    def test_charToIntPromotion(self):
        irs = compileBlockToIR("int i; char c; i = c;")
        self.assertIsInstance(irs[0], IRPromote)
        self.assertIsInstance(irs[1], IRAssign)
        self.assertEqual(irs[1].lhsAddr, irs[0].resultAddr) 





