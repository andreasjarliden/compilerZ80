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
        self.bar16 = SymEntry("int", "bar")
        self.baz = SymEntry("char", "baz")
        self.ptr = SymEntry("int*", "ptr")
        self.derefPtr = SymEntry("char", "derefPtr")
        self.foo.impl = StackAddress(1)
        self.foo16.impl = StackAddress(1)
        self.bar.impl = StackAddress(2)
        self.bar16.impl = StackAddress(3)
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

    #
    # IRAssignToPointer
    #
    def test_IRAssignToPointerViaHL(self):
        registerAllocator.RA.loadedSymbolInRegister(self.ptr, "hl")
        registerAllocator.RA.loadedSymbolInRegister(self.bar16, "de")
        ira = ir.IRAssignToPointer(self.ptr, self.bar16)
        ira.live[self.ptr] = True
        ira.live[self.bar16] = True
        registerAllocator.RA.currentInstruction = ira
        ira.genCode(self.asmWriter)

        self.asmWriter.seek(0)
        output = self.asmWriter.read()
        self.assertIn("\tld\t(hl), e\n\tinc\thl\n\tld\t(hl), d", output)

    def test_IRAssignToPointerViaBC(self):
        registerAllocator.RA.loadedSymbolInRegister(self.ptr, "bc")
        registerAllocator.RA.loadedSymbolInRegister(self.bar16, "de")
        ira = ir.IRAssignToPointer(self.ptr, self.bar16)
        ira.live[self.ptr] = True
        ira.live[self.bar16] = True
        registerAllocator.RA.currentInstruction = ira
        ira.genCode(self.asmWriter)

        self.asmWriter.seek(0)
        output = self.asmWriter.read()
        # Must load via a as no generic ld R, (BC/DE) only HL support that
        self.assertIn("\tld\ta, e\n\tld\t(bc), a\n\tinc\tbc\n\tld\ta, d\n\tld\t(bc), a", output)

    #
    # IRAdd
    #

    def test_IRAdd_bothAlreadyInRegisters(self):
        registerAllocator.RA.loadedSymbolInRegister(self.bar, "a")
        registerAllocator.RA.loadedSymbolInRegister(self.baz, "b")

        # foo = bar + baz
        ira = ir.IRAdd(self.foo, self.bar, self.baz)
        ira.live[self.foo] = True
        ira.live[self.bar] = False # Not necessary to spill bar
        ira.live[self.baz] = True
        registerAllocator.RA.currentInstruction = ira
        ira.genCode(self.asmWriter)

        self.asmWriter.seek(0)
        output = self.asmWriter.read()
        self.assertEqual(output, "\tadd\ta, b\n")
        self.assertEqual(registerAllocator.RA.isInRegister(self.foo), "a")
        self.assertNotIn(self.foo, registerAllocator.RA.symbols[self.foo]) # Not spilled yet
        self.assertFalse(registerAllocator.RA.isInRegister(self.bar))
        self.assertEqual(registerAllocator.RA.isInRegister(self.baz), "b")

    def test_IRAdd_swapsIfRhsInA(self):
        registerAllocator.RA.loadedSymbolInRegister(self.bar, "b")
        registerAllocator.RA.loadedSymbolInRegister(self.baz, "a")

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
        registerAllocator.RA.loadedSymbolInRegister(self.bar, "b")

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
        registerAllocator.RA.loadedSymbolInRegister(self.bar, "a")
        registerAllocator.RA.loadedSymbolInRegister(self.ptr, "hl")

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
        registerAllocator.RA.loadedSymbolInRegister(self.bar, "a")
        registerAllocator.RA.loadedSymbolInRegister(self.ptr, "de")

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
        registerAllocator.RA.loadedSymbolInRegister(self.bar, "a")

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

    # Load rhs via global address
    def test_IRAdd_rhsIsGlobalVariable(self):
        GLOBAL = SymEntry("char", "global")
        GLOBAL.impl = GlobalAddress("global")
        registerAllocator.RA.loadedSymbolInRegister(self.bar, "a")

        # foo = bar + GLOBAL
        ira = ir.IRAdd(self.foo, self.bar, GLOBAL)
        ira.live[self.foo] = True
        ira.live[self.bar] = True # Not necessary to spill bar
        ira.live[GLOBAL] = True 
        registerAllocator.RA.currentInstruction = ira
        ira.genCode(self.asmWriter)

        self.asmWriter.seek(0)
        output = self.asmWriter.read()
        # ld a, (global) # Must load (global) to A and transfer it
        # ld <reg>, a
        # add a, <reg>
        self.assertIn("\tld\ta, (global)", output)
        self.assertRegex(output, r"\tld\t., a")
        self.assertIn("\tld\ta, (ix + 2)", output)
        self.assertRegex(output, r"\tadd\ta, .")

    #
    # IRSub
    #

    def test_IRSubChar(self):
        registerAllocator.RA.loadedSymbolInRegister(self.bar, "a")
        registerAllocator.RA.loadedSymbolInRegister(self.baz, "b")

        # foo = bar - baz
        ira = ir.IRSub(self.foo, self.bar, self.baz)
        ira.live[self.foo] = True
        ira.live[self.bar] = False # Not necessary to spill bar
        ira.live[self.baz] = True
        registerAllocator.RA.currentInstruction = ira
        ira.genCode(self.asmWriter)

        self.asmWriter.seek(0)
        output = self.asmWriter.read()
        self.assertEqual(output, "\tsub\ta, b\n")
        self.assertEqual(registerAllocator.RA.isInRegister(self.foo), "a")
        self.assertNotIn(self.foo, registerAllocator.RA.symbols[self.foo]) # Not spilled yet
        self.assertFalse(registerAllocator.RA.isInRegister(self.bar))
        self.assertEqual(registerAllocator.RA.isInRegister(self.baz), "b")

    def test_IRSubInt(self):
        registerAllocator.RA.loadedSymbolInRegister(self.foo16, "hl")
        registerAllocator.RA.loadedSymbolInRegister(self.bar16, "bc")

        # foo = bar - baz
        ira = ir.IRSub(self.foo16, self.foo16, self.bar16)
        ira.live[self.foo16] = True
        ira.live[self.bar16] = False # Not necessary to spill bar
        registerAllocator.RA.currentInstruction = ira
        ira.genCode(self.asmWriter)

        self.asmWriter.seek(0)
        output = self.asmWriter.read()
        self.assertEqual(output, "\tor\ta\n\tsbc\thl, bc\n")
        self.assertEqual(registerAllocator.RA.isInRegister(self.foo16), "hl")
        self.assertEqual(registerAllocator.RA.isInRegister(self.bar16), "bc")

    #
    # IRBitwiseOr
    #

    def test_IRBitwiseOrChar(self):
        registerAllocator.RA.loadedSymbolInRegister(self.bar, "a")
        registerAllocator.RA.loadedSymbolInRegister(self.baz, "b")

        # foo = bar | baz
        ira = ir.IRBitwiseOr(self.foo, self.bar, self.baz)
        ira.live[self.foo] = True
        ira.live[self.bar] = False # Not necessary to spill bar
        ira.live[self.baz] = True
        registerAllocator.RA.currentInstruction = ira
        ira.genCode(self.asmWriter)

        self.asmWriter.seek(0)
        output = self.asmWriter.read()
        self.assertEqual(output, "\tor\ta, b\n")
        self.assertEqual(registerAllocator.RA.isInRegister(self.foo), "a")
        self.assertNotIn(self.foo, registerAllocator.RA.symbols[self.foo]) # Only in register
        self.assertFalse(registerAllocator.RA.isInRegister(self.bar))
        self.assertEqual(registerAllocator.RA.isInRegister(self.baz), "b")

    def test_IRBitwiseOrInt(self):
        registerAllocator.RA.loadedSymbolInRegister(self.foo16, "hl")
        registerAllocator.RA.loadedSymbolInRegister(self.bar16, "bc")

        ira = ir.IRBitwiseOr(self.foo16, self.foo16, self.bar16)
        ira.live[self.foo16] = True
        ira.live[self.bar16] = False # Not necessary to spill bar
        registerAllocator.RA.currentInstruction = ira
        ira.genCode(self.asmWriter)

        self.asmWriter.seek(0)
        output = self.asmWriter.read()

        self.assertNotIn(self.foo16, registerAllocator.RA.symbols[self.foo16]) # Only in register

    #
    # IRPromote
    #

    def test_IRPromote_inRegister(self):
        registerAllocator.RA.loadedSymbolInRegister(self.foo, "a")

        # foo16 = (int)foo
        ira = ir.IRPromote(self.foo16, self.foo, self.foo16.type)
        ira.live[self.foo] = True
        ira.live[self.foo16] = True
        registerAllocator.RA.currentInstruction = ira
        ira.genCode(self.asmWriter)

        self.asmWriter.seek(0)
        output = self.asmWriter.read()
        r = registerAllocator.RA.isInRegister(self.foo16)
        r_hi = r[0]
        r_lo = r[1]
        self.assertIn(f"\tld\t{r_hi}, 0\n", output)
        self.assertIn(f"\tld\t{r_lo}, a\n", output)

    def test_IRPromote_inMemory(self):
        # foo16 = (int)foo
        ira = ir.IRPromote(self.foo16, self.foo, self.foo16.type)
        ira.live[self.foo] = True
        ira.live[self.foo16] = True
        registerAllocator.RA.currentInstruction = ira
        ira.genCode(self.asmWriter)

        self.asmWriter.seek(0)
        output = self.asmWriter.read()
        r = registerAllocator.RA.isInRegister(self.foo16)
        r_hi = r[0]
        r_lo = r[1]
        self.assertIn(f"\tld\t{r_hi}, 0\n", output)
        self.assertIn(f"\tld\t{r_lo}, (ix + 1)\n", output)





