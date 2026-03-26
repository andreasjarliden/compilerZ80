import unittest
from symbolTable import *
from symEntry import *


class TestSymEntry(unittest.TestCase):
    def test_isObject(self):
        s1 = SymEntry("int", "foo");
        s1.impl = StackAddress(42)
        s2 = SymEntry("int", "foo");
        s2.impl = PointerAddress(123);
        self.assertNotEqual(s1, s2)

    def test_compareByValue(self):
        s1 = SymEntry("int", "foo");
        s1.impl = StackAddress(42) # equalByValue should ignore impl
        s2 = SymEntry("int", "foo");
        s2.impl = PointerAddress(123);
        self.assertTrue(s1.equalByValue(s2))


class TestSymbolTable(unittest.TestCase):
    def setUp(self):
        self.symbolTable = SymbolTable()
    
    def test_singleFrame(self):
        self.symbolTable.addSymbol("char", "a")
        self.assertEqual(self.symbolTable.lookUp("a").type, "char")

    def test_replaceWithLocal(self):
        self.symbolTable.addSymbol("char", "a")
        self.symbolTable.pushFrame();
        self.symbolTable.addSymbol("int", "a")
        self.assertEqual(self.symbolTable.lookUp("a").type, "int")

    def test_inOuterFrame(self):
        self.symbolTable.addSymbol("char", "a")
        self.symbolTable.pushFrame();
        self.symbolTable.addSymbol("int", "b")
        self.assertEqual(self.symbolTable.lookUp("a").type, "char")
        self.assertEqual(self.symbolTable.lookUp("b").type, "int")

    def test_allSymbols(self):
        aOuter = SymEntry("char", "a")
        aInner = SymEntry("int", "a")
        self.symbolTable.addSymbolEntry("a", aOuter)
        self.symbolTable.pushFrame();
        self.symbolTable.addSymbolEntry("a", aInner)
        self.assertEqual(self.symbolTable.allSymbols(), { aOuter, aInner })

