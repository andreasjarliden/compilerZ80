import unittest
from symbolTable import *

class TestSymbolTable(unittest.TestCase):
    def setUp(self):
        self.symbolTable = SymbolTable()
    
    def test_singleFrame(self):
        self.symbolTable.addSymbol("char", "a")
        self.assertEqual(self.symbolTable.lookup("a").type, "char")

    def test_replaceWithLocal(self):
        self.symbolTable.addSymbol("char", "a")
        self.symbolTable.pushFrame();
        self.symbolTable.addSymbol("int", "a")
        self.assertEqual(self.symbolTable.lookup("a").type, "int")

    def test_inOuterFrame(self):
        self.symbolTable.addSymbol("char", "a")
        self.symbolTable.pushFrame();
        self.symbolTable.addSymbol("int", "b")
        self.assertEqual(self.symbolTable.lookup("a").type, "char")
        self.assertEqual(self.symbolTable.lookup("b").type, "int")
