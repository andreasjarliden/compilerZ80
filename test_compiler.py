import unittest
import compiler
from blocks import BasicBlock, SingleBlockFactory
from parser import *
from pprint import *


# TODO live should describe the liveness AT the instruction, so we now if it is
# free to spill
class TestLiveness(unittest.TestCase):
    def setUp(self):
        self.symbolTable = SymbolTable()

    def compileBlockToIR(self, code):
        ast = parser.parse(code)
        blockFactory = SingleBlockFactory()
        blocks, _ = compiler.astToThreeCode(ast, blockFactory, self.symbolTable)
        blocks["block"].symbolTable = self.symbolTable.allSymbols()
        compiler.updateLive(blocks)
        bb = blocks["block"]
        return bb.statements

    def isLive(self, irs, v):
        return irs.live[self.symbolTable.lookUp(v)]

    def test_1(self):
        irs = self.compileBlockToIR("""
int A;
int B;
A=1;
A=B; // A is dead, free to spill A
B=A+1;""")
        self.assertEqual(type(irs[0]), IRAssign)
        self.assertEqual(type(irs[1]), IRAssign)
        self.assertEqual(type(irs[2]), IRAdd)
        self.assertEqual(type(irs[3]), IRAssign)
        self.assertFalse(self.isLive(irs[0], "A")) # A=1
        self.assertFalse(self.isLive(irs[1], "A")) # A=2
        pprint(irs)
        self.assertTrue(self.isLive(irs[3], "A")) # B=A+1

    def test_2(self):
        irs = self.compileBlockToIR("""
int A;
int B;
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
