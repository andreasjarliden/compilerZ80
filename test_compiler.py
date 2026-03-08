import unittest
import compiler
from parser import *

def compileBlockToIR(code):
    ast = parser.parse(code)
    enterBlock("dummyBlock", currentSymbolTable())
    compiler.astToThreeCode(ast)
    exitBlock()
    compiler.updateLive()
    bb = BASIC_BLOCKS["dummyBlock_0001"]
    return bb.statements

# TODO live should describe the liveness AT the instruction, so we now if it is
# free to spill
class TestLiveness(unittest.TestCase):
    def test_1(self):
        irs = compileBlockToIR("""
int A;
int B;
A=1;
A=B;
B=A+1;""")
        self.assertEqual(type(irs[0]), IRAssign)
        self.assertEqual(type(irs[1]), IRAssign)
        self.assertEqual(type(irs[2]), IRAdd)
        self.assertEqual(type(irs[3]), IRAssign)
        self.assertFalse(irs[0].live["A"]) # A=1
        self.assertFalse(irs[1].live["A"]) # A=2
        self.assertTrue(irs[3].live["A"]) # B=A+1

    def test_2(self):
        irs = compileBlockToIR("""
int A;
int B;
A=1;
B=A+1;
A=2;""")
        pprint(irs)
        self.assertEqual(type(irs[0]), IRAssign)
        self.assertEqual(type(irs[2]), IRAdd)
        self.assertEqual(type(irs[1]), IRAssign)
        self.assertEqual(type(irs[3]), IRAssign)
        self.assertFalse(irs[0].live["A"]) # A=1
        self.assertTrue(irs[1].live["A"]) # A+1
        self.assertFalse(irs[2].live["A"]) # B=A+1
        self.assertTrue(irs[3].live["A"]) # B=A+1




