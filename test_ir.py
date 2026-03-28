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
        self.bar.impl = StackAddress(2)
        self.baz.impl = StackAddress(3)
        self.ptr.impl = StackAddress(4)
        self.derefPtr.impl = PointerAddress(self.ptr)
        self.asmWriter = asmWriter.AsmWriter(StringIO())
        registerAllocator.RA = registerAllocator.Z80RegisterAllocator(self.asmWriter)

    # IRAssign

    def test_IRAssign_constant8(self):
        ira = ir.IRAssign(self.foo, Constant("char", 42))
        ira.live[self.foo] = True
        ira.genCode(self.asmWriter)

        self.asmWriter.seek(0)
        output = self.asmWriter.read()
        self.assertRegex(output, "\tld\t., 42\n")
        self.assertTrue(registerAllocator.RA.isInRegister(self.foo))

    def test_IRAssign_constant16(self):
        ira = ir.IRAssign(self.foo16, Constant("int", 0x1234))
        ira.live[self.foo16] = True
        ira.genCode(self.asmWriter)

        self.asmWriter.seek(0)
        output = self.asmWriter.read()
        self.assertRegex(output, f"\tld\t.., {0x1234}\n")
        self.assertTrue(registerAllocator.RA.isInRegister(self.foo16))

    def test_IRAssign_stackVariable(self):
        ira = ir.IRAssign(self.foo, self.bar)
        ira.live[self.foo] = True
        ira.live[self.bar] = True
        ira.genCode(self.asmWriter)

        self.asmWriter.seek(0)
        output = self.asmWriter.read()
        self.assertRegex(output, r"\tld\t., \(ix \+ 2\)")
        self.assertTrue(registerAllocator.RA.isInRegister(self.foo))

    # IRAdd

    def test_IRAdd_bothAlreadyInRegisters(self):
        registerAllocator.RA.loadSymbolInRegister(self.bar, "a")
        registerAllocator.RA.loadSymbolInRegister(self.baz, "b")

        # foo = bar + baz
        ira = ir.IRAdd(self.foo, self.bar, self.baz)
        ira.live[self.foo] = True
        ira.live[self.bar] = False # Not necessary to spill bar
        ira.live[self.baz] = True
        registerAllocator.RA.currentInstruction = ira
        print(registerAllocator.RA)
        ira.genCode(self.asmWriter)

        self.asmWriter.seek(0)
        output = self.asmWriter.read()
        self.assertEqual(output, "\tadd\ta, b\n")
        self.assertEqual(registerAllocator.RA.isInRegister(self.foo), "a")
        self.assertFalse(registerAllocator.RA.isInRegister(self.bar))
        self.assertEqual(registerAllocator.RA.isInRegister(self.baz), "b")

    def test_IRAdd_swapsIfRhsInA(self):
        registerAllocator.RA.loadSymbolInRegister(self.bar, "b")
        registerAllocator.RA.loadSymbolInRegister(self.baz, "a")

        # foo = bar + baz
        ira = ir.IRAdd(self.foo, self.bar, self.baz)
        ira.live[self.foo] = True
        ira.live[self.bar] = True 
        ira.live[self.baz] = False # Not necessary to spill
        registerAllocator.RA.currentInstruction = ira
        ira.genCode(self.asmWriter)

        self.asmWriter.seek(0)
        output = self.asmWriter.read()
        self.assertEqual(output, "\tadd\ta, b\n")
        self.assertEqual(registerAllocator.RA.isInRegister(self.foo), "a")
        self.assertEqual(registerAllocator.RA.isInRegister(self.bar), "b")
        self.assertFalse(registerAllocator.RA.isInRegister(self.baz))

    # Load the rhs directly from memory, not via a register
    def test_IRAdd_rhsDirectlyFromMemory(self):
        # foo = bar + baz
        ira = ir.IRAdd(self.foo, self.bar, self.baz)
        ira.live[self.foo] = True
        ira.live[self.bar] = False # Not necessary to spill bar
        ira.live[self.baz] = False # No more use for the rhs
        registerAllocator.RA.currentInstruction = ira
        ira.genCode(self.asmWriter)

        self.asmWriter.seek(0)
        output = self.asmWriter.read()
        self.assertEqual(output, "\tld\ta, (ix + 2)\n\tadd\ta, (ix + 3)\n")
        self.assertEqual(registerAllocator.RA.isInRegister(self.foo), "a")
        self.assertFalse(registerAllocator.RA.isInRegister(self.bar))
        self.assertFalse(registerAllocator.RA.isInRegister(self.baz))

    # Load the rhs via register from memory as the rhs will be used again
    def test_IRAdd_rhsViaRegister(self):
        # foo = bar + baz
        ira = ir.IRAdd(self.foo, self.bar, self.baz)
        ira.live[self.foo] = True
        ira.live[self.bar] = False # Not necessary to spill bar
        ira.live[self.baz] = True # bas will be used later so makes sense to load in register
        registerAllocator.RA.currentInstruction = ira
        ira.genCode(self.asmWriter)

        self.asmWriter.seek(0)
        output = self.asmWriter.read()
        self.assertIn("\tld\ta, (ix + 2)", output)
        self.assertRegex(output, r"ld\t., \(ix \+ 3\)")
        self.assertEqual(registerAllocator.RA.isInRegister(self.foo), "a")
        self.assertFalse(registerAllocator.RA.isInRegister(self.bar))
        self.assertTrue(registerAllocator.RA.isInRegister(self.baz))

    # lhs is in another register, rhs is a constant
    def test_IRAdd_rhsIsConstant(self):
        registerAllocator.RA.loadSymbolInRegister(self.bar, "b")

        # foo = bar + 42
        ira = ir.IRAdd(self.foo, self.bar, Constant("char", 42))
        ira.live[self.foo] = True
        ira.live[self.bar] = False # Not necessary to spill bar
        registerAllocator.RA.currentInstruction = ira
        ira.genCode(self.asmWriter)

        self.asmWriter.seek(0)
        output = self.asmWriter.read()
        self.assertEqual(output, "\tld\ta, b\n\tadd\ta, 42\n")
        self.assertEqual(registerAllocator.RA.isInRegister(self.foo), "a")
        self.assertEqual(registerAllocator.RA.isInRegister(self.bar), "b")

    # Load rhs via pointer already in hl register
    def test_IRAdd_rhsIsPointerInHL(self):
        registerAllocator.RA.loadSymbolInRegister(self.bar, "a")
        registerAllocator.RA.loadSymbolInRegister(self.ptr, "hl")

        # foo = bar + 42
        ira = ir.IRAdd(self.foo, self.bar, self.derefPtr)
        ira.live[self.foo] = True
        ira.live[self.bar] = False # Not necessary to spill bar
        ira.live[self.ptr] = False # No more use for ptr
        registerAllocator.RA.currentInstruction = ira
        ira.genCode(self.asmWriter)

        self.asmWriter.seek(0)
        output = self.asmWriter.read()
        self.assertEqual(output, "\tadd\ta, (hl)\n")
        self.assertEqual(registerAllocator.RA.isInRegister(self.foo), "a")
        self.assertEqual(registerAllocator.RA.isInRegister(self.ptr), "hl")

    # Load rhs via pointer already in other register
    def test_IRAdd_rhsIsPointerInOtherRegister(self):
        registerAllocator.RA.loadSymbolInRegister(self.bar, "a")
        registerAllocator.RA.loadSymbolInRegister(self.ptr, "de")

        # foo = bar + 42
        ira = ir.IRAdd(self.foo, self.bar, self.derefPtr)
        ira.live[self.foo] = True
        ira.live[self.bar] = False # Not necessary to spill bar
        ira.live[self.ptr] = False # No more use for ptr
        registerAllocator.RA.currentInstruction = ira
        ira.genCode(self.asmWriter)

        self.asmWriter.seek(0)
        output = self.asmWriter.read()
        self.assertIn("\tld\th, d\n", output)
        self.assertIn("\tld\tl, e\n", output)
        self.assertIn("\tadd\ta, (hl)\n", output)
        self.assertEqual(registerAllocator.RA.isInRegister(self.foo), "a")
        self.assertEqual(registerAllocator.RA.symbols[self.ptr], {self.ptr, "hl", "de"})

    # Load rhs via pointer that must be loaded from memory
    def test_IRAdd_rhsIsPointerFromMemory(self):
        registerAllocator.RA.loadSymbolInRegister(self.bar, "a")

        # foo = bar + 42
        ira = ir.IRAdd(self.foo, self.bar, self.derefPtr)
        ira.live[self.foo] = True
        ira.live[self.bar] = False # Not necessary to spill bar
        ira.live[self.ptr] = False # No more use for ptr
        registerAllocator.RA.currentInstruction = ira
        ira.genCode(self.asmWriter)

        self.asmWriter.seek(0)
        output = self.asmWriter.read()
        self.assertIn("\tld\th, (ix + 5)\n", output)
        self.assertIn("\tld\tl, (ix + 4)\n", output)
        self.assertIn("\tadd\ta, (hl)\n", output)
        self.assertEqual(registerAllocator.RA.isInRegister(self.foo), "a")
        self.assertEqual(registerAllocator.RA.symbols[self.ptr], {self.ptr, "hl"})




