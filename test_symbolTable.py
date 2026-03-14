import unittest
from symbolTable import *

class TestSymbolTable(unittest.TestCase):
    def test_singleFrame(self):
        addSymbol("char", "char", "a")
        print(ENV)
        self.assertEqual(lookup("a").type, "char")

    def test_replaceWithLocal(self):
        addSymbol("char", "char", "a")
        pushFrame();
        addSymbol("int", "int", "a")
        print(ENV)
        self.assertEqual(lookup("a").type, "int")

    def test_inOuterFrame(self):
        addSymbol("char", "char", "a")
        pushFrame();
        addSymbol("int", "int", "b")
        print(ENV)
        self.assertEqual(lookup("a").type, "char")
        self.assertEqual(lookup("b").type, "int")
