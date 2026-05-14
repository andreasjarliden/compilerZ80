import unittest
from testutilities import compileBlockToIR, compile
from symbolTable import SymbolTable
from astnodes import *


# TODO live should describe the liveness AT the instruction, so we now if it is
# free to spill
class TestLiveness(unittest.TestCase):
    def setUp(self):
        self.symbolTable = SymbolTable()

    def compileBlockToIR(self, code):
        return compileBlockToIR(code, self.symbolTable)

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





