import unittest
from io import StringIO
from symEntry import *
from address import Constant
import ir
import registerAllocator
import asmWriter

class TestIR(unittest.TestCase):
    def setUp(self):
        self.foo = SymEntry("char", "foo")
        self.foo16 = SymEntry("int", "foo")
        self.bar = SymEntry("char", "bar")
        self.baz = SymEntry("char", "baz")
        self.ptr = SymEntry("int*", "ptr")
        self.derefPtr = SymEntry("char", "derefPtr")
        symbolTable = { self.foo.name: self.foo,
                       self.bar.name: self.bar,
                       self.baz.name: self.baz,
                       self.ptr.name: self.ptr,
                       self.derefPtr.name: self.derefPtr
                       }
        self.bar.impl = StackAddress(2)
        self.baz.impl = StackAddress(3)
        self.ptr.impl = StackAddress(4)
        self.derefPtr.impl = PointerAddress(self.ptr)
        stringIO = StringIO()
        ir.asmFile = stringIO
        ir.asmWriter = asmWriter.AsmWriter(ir.asmFile)
        registerAllocator.RA = registerAllocator.Z80RegisterAllocator(ir.asmFile, symbolTable)

    # IRAssign

    def test_IRAssign_constant8(self):
        ira = ir.IRAssign(self.foo, Constant("char", 42))
        ira.live[self.foo.name] = True
        ira.genCode()

        ir.asmFile.seek(0)
        output = ir.asmFile.read()
        self.assertRegex(output, "\tld\t., 42\n")
        self.assertTrue(registerAllocator.RA.isInRegister("foo"))

    def test_IRAssign_constant16(self):
        ira = ir.IRAssign(self.foo16, Constant("int", 0x1234))
        ira.live[self.foo16.name] = True
        ira.genCode()

        ir.asmFile.seek(0)
        output = ir.asmFile.read()
        self.assertRegex(output, f"\tld\t.., {0x1234}\n")
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
        ira.genCode()

        ir.asmFile.seek(0)
        output = ir.asmFile.read()
        self.assertEqual(output, "\tadd\ta, b\n")
        self.assertEqual(registerAllocator.RA.isInRegister("foo"), "a")
        self.assertEqual(registerAllocator.RA.isInRegister("bar"), "b")
        self.assertFalse(registerAllocator.RA.isInRegister("baz"))

    # Load the rhs directly from memory, not via a register
    def test_IRAdd_rhsDirectlyFromMemory(self):
        # foo = bar + baz
        ira = ir.IRAdd(self.foo, self.bar, self.baz)
        ira.live[self.foo.name] = True
        ira.live[self.bar.name] = False # Not necessary to spill bar
        ira.live[self.baz.name] = False # No more use for the rhs
        registerAllocator.RA.currentInstruction = ira
        ira.genCode()

        ir.asmFile.seek(0)
        output = ir.asmFile.read()
        self.assertEqual(output, "\tld\ta, (ix + 2)\n\tadd\ta, (ix + 3)\n")
        self.assertEqual(registerAllocator.RA.isInRegister("foo"), "a")
        self.assertFalse(registerAllocator.RA.isInRegister("bar"))
        self.assertFalse(registerAllocator.RA.isInRegister("baz"))

    # Load the rhs via register from memory as the rhs will be used again
    def test_IRAdd_rhsViaRegister(self):
        # foo = bar + baz
        ira = ir.IRAdd(self.foo, self.bar, self.baz)
        ira.live[self.foo.name] = True
        ira.live[self.bar.name] = False # Not necessary to spill bar
        ira.live[self.baz.name] = True # bas will be used later so makes sense to load in register
        registerAllocator.RA.currentInstruction = ira
        ira.genCode()

        ir.asmFile.seek(0)
        output = ir.asmFile.read()
        self.assertIn("\tld\ta, (ix + 2)", output)
        self.assertRegex(output, r"ld\t., \(ix \+ 3\)")
        self.assertEqual(registerAllocator.RA.isInRegister("foo"), "a")
        self.assertFalse(registerAllocator.RA.isInRegister("bar"))
        self.assertTrue(registerAllocator.RA.isInRegister("baz"))

    # lhs is in another register, rhs is a constant
    def test_IRAdd_rhsIsConstant(self):
        registerAllocator.RA.loadNameInRegister("bar", "b")

        # foo = bar + 42
        ira = ir.IRAdd(self.foo, self.bar, Constant("char", 42))
        ira.live[self.foo.name] = True
        ira.live[self.bar.name] = False # Not necessary to spill bar
        registerAllocator.RA.currentInstruction = ira
        ira.genCode()

        ir.asmFile.seek(0)
        output = ir.asmFile.read()
        self.assertEqual(output, "\tld\ta, b\n\tadd\ta, 42\n")
        self.assertEqual(registerAllocator.RA.isInRegister("foo"), "a")
        self.assertEqual(registerAllocator.RA.isInRegister("bar"), "b")

    # Load rhs via pointer already in hl register
    def test_IRAdd_rhsIsPointerInHL(self):
        registerAllocator.RA.loadNameInRegister("bar", "a")
        registerAllocator.RA.loadNameInRegister("ptr", "hl")

        # foo = bar + 42
        ira = ir.IRAdd(self.foo, self.bar, self.derefPtr)
        ira.live["foo"] = True
        ira.live["bar"] = False # Not necessary to spill bar
        ira.live["ptr"] = False # No more use for ptr
        registerAllocator.RA.currentInstruction = ira
        ira.genCode()

        ir.asmFile.seek(0)
        output = ir.asmFile.read()
        self.assertEqual(output, "\tadd\ta, (hl)\n")
        self.assertEqual(registerAllocator.RA.isInRegister("foo"), "a")
        self.assertEqual(registerAllocator.RA.isInRegister("ptr"), "hl")

    # Load rhs via pointer already in other register
    def test_IRAdd_rhsIsPointerInOtherRegister(self):
        registerAllocator.RA.loadNameInRegister("bar", "a")
        registerAllocator.RA.loadNameInRegister("ptr", "de")

        # foo = bar + 42
        ira = ir.IRAdd(self.foo, self.bar, self.derefPtr)
        ira.live["foo"] = True
        ira.live["bar"] = False # Not necessary to spill bar
        ira.live["ptr"] = False # No more use for ptr
        registerAllocator.RA.currentInstruction = ira
        ira.genCode()

        ir.asmFile.seek(0)
        output = ir.asmFile.read()
        self.assertIn("\tld\th, d\n", output)
        self.assertIn("\tld\tl, e\n", output)
        self.assertIn("\tadd\ta, (hl)\n", output)
        self.assertEqual(registerAllocator.RA.isInRegister("foo"), "a")
        self.assertEqual(registerAllocator.RA.addresses["ptr"], {"ptr", "hl", "de"})

    # Load rhs via pointer that must be loaded from memory
    def test_IRAdd_rhsIsPointerFromMemory(self):
        registerAllocator.RA.loadNameInRegister("bar", "a")

        # foo = bar + 42
        ira = ir.IRAdd(self.foo, self.bar, self.derefPtr)
        ira.live[self.foo.name] = True
        ira.live[self.bar.name] = False # Not necessary to spill bar
        ira.live[self.ptr.name] = False # No more use for ptr
        registerAllocator.RA.currentInstruction = ira
        ira.genCode()

        ir.asmFile.seek(0)
        output = ir.asmFile.read()
        self.assertIn("\tld\th, (ix + 5)\n", output)
        self.assertIn("\tld\tl, (ix + 4)\n", output)
        self.assertIn("\tadd\ta, (hl)\n", output)
        self.assertEqual(registerAllocator.RA.isInRegister("foo"), "a")
        self.assertEqual(registerAllocator.RA.addresses["ptr"], {"ptr", "hl"})




