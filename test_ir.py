import unittest
from io import StringIO
from operand import *
from address import *
import ir
import registerAllocator
from asmWriter import StringAsmWriter

class TestIR(unittest.TestCase):
    def setUp(self):
        self.foo = SymbolOperand("char", "foo")
        self.foo16 = SymbolOperand("int", "foo")
        self.bar = SymbolOperand("char", "bar")
        self.bar16 = SymbolOperand("int", "bar")
        self.baz = SymbolOperand("char", "baz")
        self.baz16 = SymbolOperand("int", "baz")
        self.ptr = SymbolOperand(PointerType("int"), "ptr")
        self.derefPtr = SymbolOperand("char", "derefPtr")
        self.foo.impl = StackAddress(1)
        self.foo16.impl = StackAddress(1)
        self.bar.impl = StackAddress(2)
        self.bar16.impl = StackAddress(3)
        self.baz.impl = StackAddress(3)
        self.baz16.impl = StackAddress(5)
        self.ptr.impl = StackAddress(4)
        self.derefPtr.impl = PointerAddress(self.ptr)
        self.asmWriter = StringAsmWriter()
        registerAllocator.RA = registerAllocator.Z80RegisterAllocator(self.asmWriter)

    #
    # drops cast
    #
    def test_dropCast(self):
        # res, lhs & rhs all drop any CastSymbolOperand to the direct SymbolOperand
        symbol = SymbolOperand("char", "foo");
        castEntry = CastSymbolOperand(symbol, "int")
        irdummy = ir.IR(castEntry, castEntry, castEntry)
        self.assertEqual(irdummy.resultAddr, symbol)
        self.assertEqual(irdummy.lhsAddr, symbol)
        self.assertEqual(irdummy.rhsAddr, symbol)

        # Drops multiple casts
        multipleCast = CastSymbolOperand(castEntry, "char")
        irdummy = ir.IR(castEntry, castEntry, castEntry)
        self.assertEqual(irdummy.resultAddr, symbol)

        # Drops cast on pointers
        pointerSymbolOperand = SymbolOperand(PointerType("char"), "ptr")
        castPointerSymbolOperand = CastSymbolOperand(pointerSymbolOperand, PointerType("int"))
        symbol.impl = PointerAddress(castPointerSymbolOperand)
        irdummy = ir.IR(symbol, symbol, symbol)
        self.assertEqual(irdummy.resultAddr.impl.pointer, pointerSymbolOperand)


    #
    # loadRhs8
    # 
    def test_loadRhs8_loadingPointerAddress(self):
        registerAllocator.RA.assignedToSymbolWithRegister(self.foo16, "hl")
        irdummy = ir.IR(None, self.derefPtr, self.asmWriter)
        irdummy.live[self.foo16] = True
        registerAllocator.RA.currentInstruction = irdummy

        irdummy.loadRhs8(self.derefPtr, self.asmWriter)
        output = self.asmWriter.output()
        # spills old value in hl, the pointer of derefPtr (ptr) is loaded
        # afterwards.
        self.assertIn("\tld\t(ix + 2), h\n\tld\t(ix + 1), l\n\tld\th, (ix + 5)\n\tld\tl, (ix + 4)", output)
        self.assertEqual(registerAllocator.RA.symbols, { self.ptr: {self.ptr, "hl"}})

    def test_loadRhs8_pointerAlreadyInDE(self):
        registerAllocator.RA.assignedToSymbolWithRegister(self.foo16, "hl")
        registerAllocator.RA.assignedToSymbolWithRegister(self.ptr, "de")
        irdummy = ir.IR(None, self.derefPtr, self.asmWriter)
        irdummy.live[self.foo16] = True
        registerAllocator.RA.currentInstruction = irdummy

        irdummy.loadRhs8(self.derefPtr, self.asmWriter)
        output = self.asmWriter.output()
        # spills old value in hl, the pointer of derefPtr (ptr) is loaded
        # afterwards.
        self.assertIn("\tld\t(ix + 2), h\n\tld\t(ix + 1), l\n\tld\th, d\n\tld\tl, e", output)
        self.assertEqual(registerAllocator.RA.symbols, { self.ptr: {self.ptr, "hl", "de"}})

    # IRAssign

    def test_IRAssign_constant8(self):
        ira = ir.IRAssign(self.foo, ConstantOperand("char", 42))
        ira.live[self.foo] = True
        ira.genCode(self.asmWriter)

        output = self.asmWriter.output()
        self.assertRegex(output, "\tld\t., 42\n")
        self.assertTrue(registerAllocator.RA.isInRegister(self.foo))

    def test_IRAssign_constant16(self):
        ira = ir.IRAssign(self.foo16, ConstantOperand("int", 0x1234))
        ira.live[self.foo16] = True
        ira.genCode(self.asmWriter)

        output = self.asmWriter.output()
        self.assertRegex(output, f"\tld\t.., {0x1234}\n")
        self.assertTrue(registerAllocator.RA.isInRegister(self.foo16))

    def test_IRAssign_stackVariable(self):
        ira = ir.IRAssign(self.foo, self.bar)
        ira.live[self.foo] = True
        ira.live[self.bar] = True
        ira.genCode(self.asmWriter)

        output = self.asmWriter.output()
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

        output = self.asmWriter.output()
        self.assertIn("\tld\t(hl), e\n\tinc\thl\n\tld\t(hl), d", output)

    def test_IRAssignToPointerViaBC(self):
        registerAllocator.RA.loadedSymbolInRegister(self.ptr, "bc")
        registerAllocator.RA.loadedSymbolInRegister(self.bar16, "de")
        ira = ir.IRAssignToPointer(self.ptr, self.bar16)
        ira.live[self.ptr] = True
        ira.live[self.bar16] = True
        registerAllocator.RA.currentInstruction = ira
        ira.genCode(self.asmWriter)

        output = self.asmWriter.output()
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

        output = self.asmWriter.output()
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

        output = self.asmWriter.output()
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

        output = self.asmWriter.output()
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

        output = self.asmWriter.output()
        self.assertIn("\tld\ta, (ix + 2)", output)
        self.assertRegex(output, r"ld\t., \(ix \+ 3\)")
        self.assertEqual(registerAllocator.RA.isInRegister(self.foo), "a")
        self.assertFalse(registerAllocator.RA.isInRegister(self.bar))
        self.assertTrue(registerAllocator.RA.isInRegister(self.baz))

    # lhs is in another register, rhs is a constant
    def test_IRAdd_rhsIsConstant(self):
        registerAllocator.RA.loadedSymbolInRegister(self.bar, "b")

        # foo = bar + 42
        ira = ir.IRAdd(self.foo, self.bar, ConstantOperand("char", 42))
        ira.live[self.foo] = True
        ira.live[self.bar] = False # Not necessary to spill bar
        registerAllocator.RA.currentInstruction = ira
        ira.genCode(self.asmWriter)

        output = self.asmWriter.output()
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

        output = self.asmWriter.output()
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

        output = self.asmWriter.output()
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

        output = self.asmWriter.output()
        self.assertIn("\tld\th, (ix + 5)\n", output)
        self.assertIn("\tld\tl, (ix + 4)\n", output)
        self.assertIn("\tadd\ta, (hl)\n", output)
        self.assertEqual(registerAllocator.RA.isInRegister(self.foo), "a")
        self.assertEqual(registerAllocator.RA.symbols[self.ptr], {self.ptr, "hl"})

    # Load rhs via global address
    def test_IRAdd_rhsIsGlobalVariable(self):
        GLOBAL = SymbolOperand("char", "global")
        GLOBAL.impl = GlobalAddress("global")
        registerAllocator.RA.loadedSymbolInRegister(self.bar, "a")

        # foo = bar + GLOBAL
        ira = ir.IRAdd(self.foo, self.bar, GLOBAL)
        ira.live[self.foo] = True
        ira.live[self.bar] = True # Not necessary to spill bar
        ira.live[GLOBAL] = True 
        registerAllocator.RA.currentInstruction = ira
        ira.genCode(self.asmWriter)

        output = self.asmWriter.output()
        # ld a, (global) # Must load (global) to A and transfer it
        # ld <reg>, a
        # add a, <reg>
        self.assertIn("\tld\ta, (global)", output)
        self.assertRegex(output, r"\tld\t., a")
        self.assertIn("\tld\ta, (ix + 2)", output)
        self.assertRegex(output, r"\tadd\ta, .")

    def test_IRAddInt_constantOptimized(self):
        registerAllocator.RA.loadedSymbolInRegister(self.foo16, "bc")

        # bar = foo + 1
        ira = ir.IRAdd(self.bar16, self.foo16, ConstantOperand("char", 1))
        ira.live[self.foo16] = True
        registerAllocator.RA.currentInstruction = ira
        ira.genCode(self.asmWriter)

        output = self.asmWriter.output()
        self.assertIn(output, "\tld\thl, 1\n\tadd\thl, bc\n")
        self.assertEqual(registerAllocator.RA.isInRegister(self.foo16), "bc")
        self.assertEqual(registerAllocator.RA.isInRegister(self.bar16), "hl")

    def test_IRAddInt_constantOptimized_LhsInHL(self):
        registerAllocator.RA.loadedSymbolInRegister(self.foo16, "hl")

        # bar = foo + 1
        ira = ir.IRAdd(self.bar16, self.foo16, ConstantOperand("char", 1))
        ira.live[self.foo16] = True
        registerAllocator.RA.currentInstruction = ira
        ira.genCode(self.asmWriter)

        output = self.asmWriter.output()
        self.assertRegex(output, "\tld\t(bc|de), 1\n\tadd\thl, (bc|de)\n")
        self.assertNotIn(self.foo16, registerAllocator.RA.registers)
        self.assertEqual(registerAllocator.RA.isInRegister(self.bar16), "hl")

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

        output = self.asmWriter.output()
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

        output = self.asmWriter.output()
        self.assertEqual(output, "\tor\ta\n\tsbc\thl, bc\n")
        self.assertEqual(registerAllocator.RA.isInRegister(self.foo16), "hl")
        self.assertEqual(registerAllocator.RA.isInRegister(self.bar16), "bc")

    # Optimize 16 bit subtractions by turning them into add with 1-complement.
    # It avoids the or, but also makes it a transitive operation, which means
    # we can use the constant as the lhs which is restricted to HL and always
    # replaced.  This makes register handling more flexible.
    def test_IRSubInt_constantOptimized(self):
        registerAllocator.RA.loadedSymbolInRegister(self.foo16, "bc")

        # bar = foo - 1
        ira = ir.IRSub(self.bar16, self.foo16, ConstantOperand("char", 1))
        ira.live[self.foo16] = True
        registerAllocator.RA.currentInstruction = ira
        ira.genCode(self.asmWriter)

        output = self.asmWriter.output()
        self.assertIn(output, "\tld\thl, 65535\n\tadd\thl, bc\n")
        self.assertEqual(registerAllocator.RA.isInRegister(self.foo16), "bc")
        self.assertEqual(registerAllocator.RA.isInRegister(self.bar16), "hl")

    # Optimize 16 bit subtractions by turning them into add with 1-complement.
    # In this example the lhs is already in hl, so we use the regular order.
    def test_IRSubInt_constantOptimized_LhsInHL(self):
        registerAllocator.RA.loadedSymbolInRegister(self.foo16, "hl")

        # bar = foo - 1
        ira = ir.IRSub(self.bar16, self.foo16, ConstantOperand("char", 1))
        ira.live[self.foo16] = True
        registerAllocator.RA.currentInstruction = ira
        ira.genCode(self.asmWriter)

        output = self.asmWriter.output()
        self.assertRegex(output, "\tld\t(bc|de), 65535\n\tadd\thl, (bc|de)\n")
        self.assertNotIn(self.foo16, registerAllocator.RA.registers)
        self.assertEqual(registerAllocator.RA.isInRegister(self.bar16), "hl")

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

        output = self.asmWriter.output()
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

        output = self.asmWriter.output()

        self.assertNotIn(self.foo16, registerAllocator.RA.symbols[self.foo16]) # Only in register

    #
    # IRMul
    #
    def test_IRMul_int_constant(self):
        registerAllocator.RA.loadedSymbolInRegister(self.foo16, "de")

        ira = ir.IRMul(self.bar16, self.foo16, ConstantOperand("int", 5))
        ira.live[self.foo16] = True
        registerAllocator.RA.currentInstruction = ira
        ira.genCode(self.asmWriter)

        output = self.asmWriter.output()

        print(output)
        self.assertIn("\tld\thl, 0\n" +
            "\tadd\thl, de\n" +
            "\tsla\te\n\trl\td\n"*2 +
            "\tadd\thl, de\n", output)
        self.assertNotIn(self.bar16, registerAllocator.RA.symbols[self.bar16]) # Only in register
        self.assertEqual(registerAllocator.RA.registers["de"], set()) # Only in register

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

        output = self.asmWriter.output()
        r = registerAllocator.RA.isInRegister(self.foo16)
        r_hi = r[0]
        r_lo = r[1]
        self.assertIn(f"\tld\t{r_hi}, 0\n", output)
        self.assertIn(f"\tld\t{r_lo}, a\n", output)
        self.assertNotIn(self.foo16, registerAllocator.RA.symbols[self.foo16]) # Only in register

    def test_IRPromote_inMemory(self):
        # foo16 = (int)foo
        ira = ir.IRPromote(self.foo16, self.foo, self.foo16.type)
        ira.live[self.foo] = True
        ira.live[self.foo16] = True
        registerAllocator.RA.currentInstruction = ira
        ira.genCode(self.asmWriter)

        output = self.asmWriter.output()
        r = registerAllocator.RA.isInRegister(self.foo16)
        r_hi = r[0]
        r_lo = r[1]
        self.assertIn(f"\tld\t{r_hi}, 0\n", output)
        self.assertIn(f"\tld\t{r_lo}, (ix + 1)\n", output)
        self.assertNotIn(self.foo16, registerAllocator.RA.symbols[self.foo16]) # Only in register

    def test_IRPromote_constant(self):
        # foo16 = (int)ConstantOperand 4
        ira = ir.IRPromote(self.foo16, ConstantOperand("char", 4), self.foo16.type)
        ira.live[self.foo16] = True
        registerAllocator.RA.currentInstruction = ira
        ira.genCode(self.asmWriter)

        output = self.asmWriter.output()
        r = registerAllocator.RA.isInRegister(self.foo16)
        r_hi = r[0]
        r_lo = r[1]
        print(output)
        self.assertRegex(output, r"\tld\t(bc|de|hl), 4\n", output)
        self.assertNotIn(self.foo16, registerAllocator.RA.symbols[self.foo16]) # Only in register

    #
    # IRIfRelation
    #
    def test_IRIfRelation_int(self):
        registerAllocator.RA.loadedSymbolInRegister(self.foo16, "hl")
        registerAllocator.RA.loadedSymbolInRegister(self.bar16, "bc")

        # foo = bar - baz
        ira = ir.IRIfRelation("==", self.foo16, self.bar16, "elseLabel")
        ira.live[self.foo16] = True
        ira.live[self.bar16] = False # Not necessary to spill bar
        registerAllocator.RA.currentInstruction = ira
        ira.genCode(self.asmWriter)

        output = self.asmWriter.output()
        print(output)
        self.assertEqual(output, "\tor\ta\n\tsbc\thl, bc\n\tjp\tnz, elseLabel\n")

    #
    # IRAddressOf
    #
    def test_IRAddressOf_localVariable(self):
        result = SymbolOperand(PointerType("char"), "res")
        result.impl = StackAddress(-2)
        arg = SymbolOperand("char", "arg")
        # Rightmost argument (16-bit) is at ix+5, ix+4
        arg.impl = StackAddress(-4) 
        ira = ir.IRAddressOf(arg, result)
        ira.genCode(self.asmWriter)

        output = self.asmWriter.output()
        self.assertRegex(output, "push\tix\n\tpop\thl\n\tld\t(bc|de), 0fffch\n\tadd\thl, (bc|de)")

    def test_IRAddressOf_stackArgument(self):
        result = SymbolOperand(PointerType("char"), "res")
        result.impl = StackAddress(-1)
        arg = SymbolOperand("char", "arg")
        # Rightmost argument (16-bit) is at ix+5, ix+4
        arg.impl = StackAddress(4) 
        ira = ir.IRAddressOf(arg, result)
        ira.genCode(self.asmWriter)

        output = self.asmWriter.output()
        self.assertRegex(output, "push\tix\n\tpop\thl\n\tld\t(bc|de), 00004h\n\tadd\thl, (bc|de)")



