import unittest
from symbolTable import *
from symEntry import *
from address import StringConstant
from astnodes import ASTContext, StringTable

class TestStringTable(unittest.TestCase):
    def test(self):
        st = StringTable()
        name1 = st.addString("foo")
        self.assertEqual(name1, "__str0")
        name2 = st.addString("bar")
        self.assertEqual(name2, "__str1")
        name3 = st.addString("foo")
        self.assertEqual(name3, "__str0")

class TestStringConstant(unittest.TestCase):
    def test_stringConstant(self):
        c = StringConstant("foo")
        self.assertEqual(c.completeType, "char*")
        self.assertEqual(c._value, "foo")

    def test_stringConstant_visitAddsToDataSegment(self):
        c = StringConstant("foo")
        context = ASTContext()
        c.visit(context)
        print(context.dataSegment)
        self.assertEqual(len(context.dataSegment), 1)
        self.assertEqual(list(context.dataSegment.values()), ["foo"])

    def test_stringConstant_identicalStringsAddedOnce(self):
        c1 = StringConstant("foo")
        c2 = StringConstant("foo")
        context = ASTContext()
        c1.visit(context)
        c2.visit(context)
        print(context.dataSegment)
        self.assertEqual(len(context.dataSegment), 1)
        self.assertEqual(list(context.dataSegment.values()), ["foo"])


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

