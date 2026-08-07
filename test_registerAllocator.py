import unittest
from registerAllocator import *
from io import StringIO
from symEntry import *
from asmWriter import AsmWriter
from ir import *


class TestRA(unittest.TestCase):
    def setUp(self):
        self.foo = SymbolOperand("char", "foo")
        self.foo.impl = StackAddress(-1)
        self.bar = SymbolOperand("char", "bar")
        self.bar.impl = StackAddress(-2)
        self.ra = RegisterAllocator()
        self.ra.currentInstruction = IR()
        self.ra.currentInstruction.live = { self.foo: True, self.bar: True }
        self.performedSpills = []
        self.ra.doStoreToSymbol = self.doStoreToSymbol

    def doStoreToSymbol(self, reg, s, onlyStore=False):
        self.performedSpills.append( (reg, s) )

    # loadRegister

    def test_loadRegister(self):
        self.ra.loadedSymbolInRegister(self.foo, "a")
        self.assertEqual(self.ra.symbols[self.foo], {self.foo, "a"})
        self.assertEqual(self.ra.registers["a"], {self.foo})
        self.assertFalse("a" in self.ra.freeRegisters)

    # isFree

    def test_isFree(self):
        self.assertEqual(self.ra.isFree("b"), True); # Free from start
        self.ra.loadedSymbolInRegister(self.foo, "b")
        self.assertEqual(self.ra.isFree("b"), False); 

    def test_isFree_coupledRegisters(self):
        self.assertEqual(self.ra.isFree("b"), True); # Free from start
        self.ra.loadedSymbolInRegister(self.foo, "bc")
        self.assertEqual(self.ra.isFree("b"), False); 

    # storedToSymbol

    def test_storedToSymbol(self):
        self.ra.storedToSymbol(self.foo)
        self.assertTrue(self.foo in self.ra.symbols[self.foo])

    # bar = foo

    def test_assignment(self):
        self.ra.loadedSymbolInRegister(self.foo, "a") # foo is loaded in a
        self.ra.assignedToSymbolWithRegister(self.bar, "a") # store foo (loaded in a) to bar
        self.assertEqual(self.ra.symbols[self.bar], {"a"})
        self.assertEqual(self.ra.registers["a"], {self.foo, self.bar}) # Now a holds both foo and bar

    def test_assignment2(self):
        self.ra.loadedSymbolInRegister(self.bar, "b") # bar was previously in reg b
        self.ra.loadedSymbolInRegister(self.foo, "a") # foo is loaded in a
        self.ra.assignedToSymbolWithRegister(self.bar, "a") # store foo (loaded in a) to bar
        self.assertEqual(self.ra.symbols[self.bar], {"a"}) # Note: b no longer holds updated bar and it is not stored yet to bar
        self.assertEqual(self.ra.registers["b"], set()) # The old bar value in reg b is no longer current
        self.assertEqual(self.ra.registers["a"], {self.foo, self.bar}) # Now a holds both foo and bar

    # removeSymbolForRegister
    def test_removeSymbolForRegister(self):
        self.ra.loadedSymbolInRegister(self.foo, "a")

        self.ra.removeSymbolForRegister(self.foo, "a")
        self.ra.verify()

        self.assertEqual(self.ra.registers["a"], set())
        self.assertNotIn(self.foo, self.ra.symbols) # Symbol no longer in any rgister

    def test_removeSymbolForRegister2(self):
        self.ra.loadedSymbolInRegister(self.foo, "a")
        self.ra.loadedSymbolInRegister(self.foo, "b")

        self.ra.removeSymbolForRegister(self.foo, "a")
        self.ra.verify()

        self.assertEqual(self.ra.registers["a"], set())
        self.assertEqual(self.ra.registers["b"], { self.foo })
        self.assertEqual(self.ra.symbols[self.foo], {self.foo, "b"} )

    #
    # Spilling
    #

    def test_spillRegister(self):
        self.ra.loadedSymbolInRegister(self.foo, "a")
        self.ra.spillRegister("a")
        self.assertFalse(self.foo in self.ra.symbols)
        self.assertEqual(self.ra.registers["a"], set())
        self.assertTrue("a" in self.ra.freeRegisters)
        self.assertEqual(self.performedSpills, []) # Already in memory

    # If already in a register, use that register
    def test_alreadyInRegister(self):
        self.ra.loadedSymbolInRegister(self.foo, "b")
        self.assertEqual(self.ra.getRegisterForSymbol(self.foo, ALL_REGISTERS), "b")

    # Not already in a register, but still free registers
    def test_notLoadedButFreeRegisters(self):
        self.ra.loadedSymbolInRegister(self.foo, "a")
        self.assertEqual(self.ra.getRegisterForSymbol(self.bar, {"a", "b"}), "b")

    # Not already in a register, but still free registers
    def test_notLoadedMustSpill2(self):
        self.ra.loadedSymbolInRegister(self.foo, "a")
        # Must spill register a
        self.assertEqual(self.ra.getRegisterForSymbol(self.bar, {"a"}), "a")
        # Check register a is no longer listed for foo
        self.assertFalse(self.foo in self.ra.symbols)
        # Check register a is now free
        self.assertTrue("a" in self.ra.freeRegisters)

    def test_spillRegister_live(self):
        self.ra.assignedToSymbolWithRegister(self.foo, "a")
        self.ra.currentInstruction.live[self.foo] = True

        self.ra.spillRegister("a")

        self.assertEqual(self.ra.registers["a"], set())
        self.assertFalse(self.foo in self.ra.symbols)
        self.assertEqual(self.performedSpills, [("a", self.foo)]) 

    def test_spillRegister_dead(self):
        self.ra.assignedToSymbolWithRegister(self.foo, "a")
        self.ra.currentInstruction.live[self.foo] = False

        self.ra.spillRegister("a")

        self.assertEqual(self.ra.registers["a"], set())
        self.assertFalse(self.foo in self.ra.symbols)
        self.assertEqual(self.performedSpills, []) # Not needed, is dead

    # spillRegisterToSymbol
    def test_spillRegisterToSymbol_1(self):
        # foo = 123 # in A
        # bar = foo # both foo and bar in A
        self.ra.assignedToSymbolWithRegister(self.foo, "a")
        self.ra.assignedToSymbolWithRegister(self.bar, "a")

        self.ra.spillRegisterToSymbol("a", self.foo)

        self.assertEqual(self.ra.registers["a"], { self.bar })
        self.assertFalse(self.foo in self.ra.symbols)
        self.assertEqual(self.ra.symbols[self.bar], { "a" })
        self.assertEqual(self.performedSpills, [("a", self.foo)])

    # already in register b
    def test_spillRegisterToSymbol_2(self):
        self.ra.loadedSymbolInRegister(self.foo, "a")
        self.ra.loadedSymbolInRegister(self.foo, "b")

        self.ra.spillRegisterToSymbol("a", self.foo)

        self.assertEqual(self.ra.symbols[self.foo], { self.foo, "b" })
        self.assertEqual(self.ra.registers["b"], { self.foo })

    # already in register b, not in memory
    def test_spillRegisterToSymbol_3(self):
        self.ra.loadedSymbolInRegister(self.foo, "a")
        self.ra.copiedRegisterToRegister("a", "b")

        self.ra.spillRegister("a")

        self.assertEqual(self.ra.symbols[self.foo], { self.foo, "b" })
        self.assertEqual(self.ra.registers["b"], { self.foo })

    # _spillSymbol
    def test_spillSymbols_inMemory(self):
        self.ra.loadedSymbolInRegister(self.foo, "a")

        self.ra._spillSymbol(self.foo)

        self.assertEqual(self.ra.registers["a"], set())
        self.assertFalse(self.foo in self.ra.symbols)
        self.assertEqual(self.performedSpills, []) # Not needed, already in memory

    def test_spillSymbols(self):
        self.ra.assignedToSymbolWithRegister(self.foo, "a")

        self.ra._spillSymbol(self.foo)

        self.assertEqual(self.ra.registers["a"], set())
        self.assertFalse(self.foo in self.ra.symbols)
        self.assertEqual(self.performedSpills, [("a", self.foo)])


    # spillAll
    def test_spillAll(self):
        self.ra.currentInstruction.live[self.foo] = True
        self.ra.currentInstruction.live[self.bar] = False
        self.ra.assignedToSymbolWithRegister(self.foo, "a") # char
        self.ra.assignedToSymbolWithRegister(self.bar, "b") # char

        self.ra.spillAll()

        self.assertEqual(self.ra.registers["a"], set())
        self.assertEqual(self.ra.registers["b"], set())
        # TODO how to test if it actually spills


    # spillAllMatchingType

    def test_storeAllMatchingType_int(self):
        foo = SymbolOperand("char", "foo")
        foo.impl = "dummyImpl"
        foo2 = SymbolOperand("char", "foo")
        foo2.impl = "dummyImpl"
        baz = SymbolOperand("int", "baz")
        baz.impl = "dummyImpl"
        temp = SymbolOperand("int", "temp001") # should not be spilled
        temp.impl = "dummyImpl"
        self.ra.currentInstruction.live[foo] = True
        self.ra.currentInstruction.live[foo2] = True
        self.ra.currentInstruction.live[baz] = False # store even if not live
        self.ra.currentInstruction.live[baz] = True
        self.ra.assignedToSymbolWithRegister(foo, "a") # char
        self.ra.assignedToSymbolWithRegister(foo2, "b") # char
        self.ra.assignedToSymbolWithRegister(baz, "c") # int

        self.ra.storeAllMatchingType("int")

        self.assertEqual(self.performedSpills, [ ("c", baz) ])
        self.assertEqual(self.ra.registers["c"], {baz})
        self.assertTrue(baz in self.ra.symbols) # Only store, don't spill

    def test_storeAllMatchingType_char(self):
        foo = SymbolOperand("char", "foo")
        foo.impl = "dummyImpl"
        foo2 = SymbolOperand("char", "foo")
        foo2.impl = "dummyImpl"
        baz = SymbolOperand("int", "baz")
        baz.impl = "dummyImpl"
        self.ra.currentInstruction.live[foo] = True
        self.ra.currentInstruction.live[foo2] = True
        self.ra.currentInstruction.live[baz] = True
        self.ra.assignedToSymbolWithRegister(foo, "a") # char
        self.ra.assignedToSymbolWithRegister(foo2, "b") # char
        self.ra.assignedToSymbolWithRegister(baz, "c") # int

        self.ra.storeAllMatchingType("char")

        self.assertEqual(self.performedSpills, [ ("a", foo), ("b", foo2) ])


class TestZ80RA(unittest.TestCase):
    def setUp(self):
        self.foo = SymbolOperand("char", "foo")
        self.foo.impl = StackAddress(0)
        self.ptr = SymbolOperand("int", "ptr")
        self.ptr.impl = StackAddress(2)
        self.derefPtr = SymbolOperand("char", "deref")
        self.derefPtr.impl = PointerAddress(self.ptr)
        self.derefPtr16 = SymbolOperand("int", "deref16")
        self.derefPtr16.impl = PointerAddress(self.ptr)
        self.bar = SymbolOperand("char", "bar")
        self.bar.impl = StackAddress(-11)
        self.bar16 = SymbolOperand("char", "bar16")
        self.bar16.impl = StackAddress(-2)
        self.asmWriter = StringAsmWriter()
        self.ra = Z80RegisterAllocator(self.asmWriter)
        self.ra.currentInstruction = IR()
        self.ra.currentInstruction.live = { self.foo: True, self.bar: True, self.ptr: True }

    def test_doStoreToSymbol_StackAddress_char(self):
        s = SymbolOperand("char", "foo")
        s.impl = StackAddress(42)
        self.ra.doStoreToSymbol("a", s)
        output = self.asmWriter.output()
        self.assertIn("ld\t(ix + 42), a", output)

    def test_doStoreToSymbol_StackAddress_int(self):
        s = SymbolOperand("int", "foo")
        s.impl = StackAddress(42)
        self.ra.doStoreToSymbol("hl", s)
        output = self.asmWriter.output()
        self.assertIn("ld\t(ix + 43), h", output)
        self.assertIn("ld\t(ix + 42), l", output)

    def test_doStoreToSymbol_GlobalAddress_char(self):
        # Char
        s = SymbolOperand("char", "foo")
        s.impl = GlobalAddress("label")
        self.ra.doStoreToSymbol("a", s)
        output = self.asmWriter.output()
        self.assertIn("ld\t(label), a", output)

    def test_doStoreToSymbol_GlobalAddress_int(self):
        s = SymbolOperand("int", "foo")
        s.impl = GlobalAddress("label")
        self.ra.doStoreToSymbol("hl", s)
        output = self.asmWriter.output()
        self.assertIn("ld\t(label), hl", output)

    def test_spill(self):
        self.ra.assignedToSymbolWithRegister(self.foo, "a")
        r = self.ra.getRegisterForSymbol(self.bar, { "a" })
        output = self.asmWriter.output()
        self.assertEqual(r, "a")
        self.assertIn("\tld\t(ix + 0), a\n", output)

    def test_spillRegisterPair(self):
        self.ra.assignedToSymbolWithRegister(self.foo, "b")
        r = self.ra.getRegisterForSymbol(self.bar16, { "bc" })
        output = self.asmWriter.output()
        self.assertEqual(r, "bc")
        self.assertIn("\tld\t(ix + 0), b\n", output)
        self.assertEqual(self.ra.registers["b"], set())

    def test_spillRegisterPair2(self):
        self.ra.assignedToSymbolWithRegister(self.foo, "b")
        r = self.ra.getRegisterForSymbol(self.bar16, { "bc" })
        output = self.asmWriter.output()
        self.assertEqual(r, "bc")
        self.assertIn("\tld\t(ix + 0), b\n", output)
        self.assertEqual(self.ra.registers["b"], set())

    # More complicated as we might have to use a to spill a different register
    def test_spillGlobalChar(self):
        self.ra.assignedToSymbolWithRegister(self.foo, "a")
        GLOBAL = SymbolOperand("char", "GLOBAL")
        GLOBAL.impl = GlobalAddress("GLOBAL")
        self.ra.currentInstruction.live[GLOBAL] = True
        self.ra.assignedToSymbolWithRegister(GLOBAL, "b")

        self.ra.spillRegister("b")

        output = self.asmWriter.output()
        self.assertIn("ld\t(ix + 0), a", output) # spilling A
        self.assertIn("ld\ta, b", output) # copying b to A
        self.assertIn("ld\t(GLOBAL), a", output) # spilling B via A
        self.assertTrue(output.find("ld\t(ix + 0)") < output.find("ld\ta, b"))
        self.assertTrue(output.find("ld\ta, b") < output.find("ld\t(GLOBAL), a"))

    def test_spillGlobalInt(self):
        GLOBAL = SymbolOperand("int", "GLOBAL")
        GLOBAL.impl = GlobalAddress("GLOBAL")
        self.ra.currentInstruction.live[GLOBAL] = True
        self.ra.assignedToSymbolWithRegister(GLOBAL, "bc")

        self.ra.spillRegister("bc")

        output = self.asmWriter.output()
        self.assertIn("ld\t(GLOBAL), bc", output)

    # Check the special case where we are spilling reg a directly
    def test_spillGlobalChar_regA(self):
        GLOBAL = SymbolOperand("char", "GLOBAL")
        GLOBAL.impl = GlobalAddress("GLOBAL")
        self.ra.currentInstruction.live[GLOBAL] = True
        self.ra.assignedToSymbolWithRegister(GLOBAL, "a")

        self.ra.spillRegister("a")

        output = self.asmWriter.output()
        self.assertIn("ld\t(GLOBAL), a", output) # spilling B via A

    #
    # loadInA
    #

    def test_loadInA_alreadyLoaded(self):
        self.ra.loadedSymbolInRegister(self.foo, "a")
        r = self.ra.loadInA(self.foo) 

        output = self.asmWriter.output()
        self.assertEqual(r, "a")
        self.assertEqual(output, "")

    def test_loadInA_freeButNotLoaded(self):
        r = self.ra.loadInA(self.foo)

        output = self.asmWriter.output()
        self.assertEqual(r, "a")
        self.assertEqual(output, "\tld\ta, (ix + 0)\n")

    def test_loadInA_loadedInOtherRegister(self):
        self.ra.loadedSymbolInRegister(self.foo, "b")
        r = self.ra.loadInA(self.foo)

        output = self.asmWriter.output()
        self.assertEqual(r, "a")
        self.assertEqual(output, "\tld\ta, b\n")
    def test_loadInA_fromConstant(self):
        self.ra.loadInA(Constant("char", 42));

        output = self.asmWriter.output()
        self.assertIn("\tld\ta, 42\n", output)

    def test_loadInA_fromMemory(self):
        self.ra.loadInA(self.foo);

        output = self.asmWriter.output()
        self.assertIn("\tld\ta, (ix + 0)\n", output)

    # already in register b
    def test_loadInA_alreadyInRegister(self):
        self.ra.loadedSymbolInRegister(self.foo, "b")

        self.ra.loadInA(self.foo);

        output = self.asmWriter.output()
        self.assertIn("\tld\ta, b\n", output)
        self.assertEqual(self.ra.symbols[self.foo], { self.foo, "a", "b" })
        self.assertEqual(self.ra.registers["a"], { self.foo })
        self.assertEqual(self.ra.registers["b"], { self.foo })

    # already in register b
    def test_loadInA_alreadyInRegisterButNotInMemory(self):
        self.ra.assignedToSymbolWithRegister(self.foo, "b")

        self.ra.loadInA(self.foo);

        output = self.asmWriter.output()
        self.assertIn("\tld\ta, b\n", output)
        self.assertEqual(self.ra.symbols[self.foo], { "a", "b" })
        self.assertEqual(self.ra.registers["a"], { self.foo })
        self.assertEqual(self.ra.registers["b"], { self.foo })

    # already in register a
    def test_loadInA_alreadyInRegisterA(self):
        self.ra.loadedSymbolInRegister(self.foo, "a")

        self.ra.loadInA(self.foo);

        output = self.asmWriter.output()
        self.assertEqual("", output)

    def test_loadInA_fromPointerInMemory(self):
        # Just to force de to be used
        self.ra.loadedSymbolInRegister(self.foo, "bc")
        self.ra.loadedSymbolInRegister(self.foo, "hl")

        self.ra.loadInA(self.derefPtr);

        output = self.asmWriter.output()
        self.assertIn("\tld\td, (ix + 3)", output)
        self.assertIn("\tld\te, (ix + 2)", output)
        self.assertIn("\tld\ta, (de)", output)

    def test_loadInA_fromPointerInRegister(self):
        self.ra.loadedSymbolInRegister(self.ptr, "de")
        self.ra.loadInA(self.derefPtr);

        output = self.asmWriter.output()
        self.assertEqual("\tld\ta, (de)\n", output)

    #  doLoadInRegister8
    def test_doLoadInRegister8(self):
        ptr = SymbolOperand(PointerType("char"), "ptr")
        ptr.impl = "dummy"
        foo = SymbolOperand("char", "foo")
        foo.impl = PointerAddress(ptr)

        # Force an attempt to ld r, (bc/de), when r is not a which is not
        # supported.
        self.ra.loadedSymbolInRegister(ptr, "de")
        self.ra.doLoadInRegister8(foo, { 'b', 'c', 'd', 'e' });

        output = self.asmWriter.output()
        self.assertEqual("\tld\ta, (de)\n", output)

    # loadInHL

    def test_loadInHL_fromPointerInRegister(self):
        self.ra.loadedSymbolInRegister(self.ptr, "de")
        self.ra.loadInHL(self.derefPtr16);

        output = self.asmWriter.output()
        self.assertIn("\tld\ta, (de)\n", output)
        self.assertIn("\tld\tl, a\n", output)
        self.assertIn("\tinc\tde\n", output)
        self.assertIn("\tld\ta, (de)\n", output)
        self.assertIn("\tld\th, a\n", output)
        self.assertIn("\tdec\tde\n", output)

    def test_loadInHL_fromPointerInRegisterWhichIsDead(self):
        self.ra.loadedSymbolInRegister(self.ptr, "de")
        self.ra.currentInstruction.live[self.ptr] = False
        self.ra.loadInHL(self.derefPtr16);

        output = self.asmWriter.output()
        self.assertFalse(self.ra.isInRegister("ptr", { "de" }))
        # TODO also check that we don't ruin the register if it also stores a different name

    def test_loadInHL_fromOtherRegister(self):
        self.ra.loadedSymbolInRegister(self.foo, "de")
        self.ra.loadInHL(self.foo);

        output = self.asmWriter.output()
        self.assertIn("\tld\th, d\n", output)
        self.assertIn("\tld\tl, e\n", output)

    def test_loadInHL_fromPointerInHL(self):
        # Just to force de to be used
        self.ra.loadedSymbolInRegister(self.foo, "bc")
        self.ra.assignedToSymbolWithRegister(self.ptr, "hl")
        self.ra.loadInHL(self.derefPtr16);

        output = self.asmWriter.output()

        # Expect copy pointer in hl to de
        self.assertIn("\tld\td, h\n", output)
        self.assertIn("\tld\te, l\n", output)
        # Expect spilling of hl to ptr
        self.assertIn("\tld\t(ix + 3), h\n", output)
        self.assertIn("\tld\t(ix + 2), l\n", output)
        # Expect loading hl from (de)
        self.assertIn("\tld\ta, (de)\n", output)
        self.assertIn("\tld\tl, a\n", output)
        self.assertIn("\tinc\tde\n", output)
        self.assertIn("\tld\ta, (de)\n", output)
        self.assertIn("\tld\th, a\n", output)
