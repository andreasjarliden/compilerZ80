import unittest
from io import StringIO
from symEntry import *
import address
import ir
import registerAllocator

class TestIR(unittest.TestCase):
    def setUp(self):
        self.foo = SymEntry("char", "char", "foo")
        self.bar = SymEntry("char", "char", "bar")
        self.baz = SymEntry("char", "char", "baz")
        symbolTable = { self.foo.name: self.foo,
                       self.bar.name: self.bar,
                       self.baz.name: self.baz
                       }
        self.bar.impl = StackAddress(2)
        stringIO = StringIO()
        ir.asmFile = stringIO
        ir.asmWriter = ir.asmFile
        registerAllocator.RA = registerAllocator.Z80RegisterAllocator(ir.asmFile, symbolTable)

    # IRAssign

    def test_IRAssign_constant(self):
        ira = ir.IRAssign(self.foo, address.Constant("char", 42))
        ira.live[self.foo.name] = True
        ira.genCode()

        ir.asmFile.seek(0)
        output = ir.asmFile.read()
        self.assertRegex(output, "\tld\t., 42\n")
        self.assertTrue(registerAllocator.RA.isInRegister("foo"))

    def test_IRAssign_stackVariable(self):
        ira = ir.IRAssign(self.foo, self.bar)
        ira.live[self.foo.name] = True
        ira.live[self.bar.name] = True
        ira.genCode()

        ir.asmFile.seek(0)
        output = ir.asmFile.read()
        self.assertRegex(output, r"\tld\t., \(ix \+ 2\)")
        self.assertTrue(registerAllocator.RA.isInRegister("foo"))

    # IRAdd

    def test_IRAdd_bothAlreadyInRegisters(self):
        registerAllocator.RA.loadNameInRegister("bar", "a")
        registerAllocator.RA.loadNameInRegister("baz", "b")

        # foo = bar + baz
        ira = ir.IRAdd(self.foo, self.bar, self.baz)
        ira.live[self.foo.name] = True
        ira.live[self.bar.name] = False # Not necessary to spill bar
        ira.live[self.baz.name] = True
        registerAllocator.RA.currentInstruction = ira
        ira.genCode()

        ir.asmFile.seek(0)
        output = ir.asmFile.read()
        print(registerAllocator.RA)
        self.assertEqual(output, "\tadd\ta, b\n")
        self.assertEqual(registerAllocator.RA.isInRegister("foo"), "a")
        self.assertFalse(registerAllocator.RA.isInRegister("bar"))
        self.assertEqual(registerAllocator.RA.isInRegister("baz"), "b")

    def test_IRAdd_swapsIfRhsInA(self):
        registerAllocator.RA.loadNameInRegister("bar", "b")
        registerAllocator.RA.loadNameInRegister("baz", "a")

        # foo = bar + baz
        ira = ir.IRAdd(self.foo, self.bar, self.baz)
        ira.live[self.foo.name] = True
        ira.live[self.bar.name] = True 
        ira.live[self.baz.name] = False # Not necessary to spill
        registerAllocator.RA.currentInstruction = ira
        print(f"before genCode() {ira.live}")
        ira.genCode()

        ir.asmFile.seek(0)
        output = ir.asmFile.read()
        print(registerAllocator.RA)
        self.assertEqual(output, "\tadd\ta, b\n")
        self.assertEqual(registerAllocator.RA.isInRegister("foo"), "a")
        self.assertEqual(registerAllocator.RA.isInRegister("bar"), "b")
        self.assertFalse(registerAllocator.RA.isInRegister("baz"))






