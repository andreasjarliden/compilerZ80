import unittest
from registerAllocator import *
from io import StringIO
from symEntry import *
from address import *
from asmWriter import AsmWriter
from ir import *


class TestRA(unittest.TestCase):
    def setUp(self):
        self.foo = SymEntry("char", "foo")
        self.bar = SymEntry("char", "bar")
        self.ra = RegisterAllocator()
        self.ra.currentInstruction = IR()
        self.ra.currentInstruction.live = { self.foo: True, self.bar: True }

    # loadRegister

    def test_loadRegister(self):
        self.ra.loadSymbolInRegister(self.foo, "a")
        self.assertEqual(self.ra.symbols[self.foo], {self.foo, "a"})
        self.assertEqual(self.ra.registers["a"], {self.foo})
        self.assertFalse("a" in self.ra.freeRegisters)

    def test_loadRegister_replacingOld(self):
        self.ra.loadSymbolInRegister(self.bar, "c") # bar previously loaded in c
        self.ra.loadSymbolInRegister(self.foo, "a")
        self.ra.loadSymbolInRegister(self.bar, "a") # a no longer contains foo
        self.assertEqual(self.ra.symbols[self.bar], {self.bar, "a", "c"})
        self.assertTrue(self.bar in self.ra.registers["a"]) 
        self.assertFalse("a" in self.ra.freeRegisters)

    # isFree

    def test_isFree(self):
        self.assertEqual(self.ra.isFree("b"), True); # Free from start
        self.ra.loadSymbolInRegister(self.foo, "b")
        self.assertEqual(self.ra.isFree("b"), False); 

    def test_isFree_coupledRegisters(self):
        self.assertEqual(self.ra.isFree("b"), True); # Free from start
        self.ra.loadSymbolInRegister("foo", "bc")
        self.assertEqual(self.ra.isFree("b"), False); 

    # storeToSymbol

    def test_storeToSymbol(self):
        self.ra.storeToSymbol(self.foo)
        self.assertTrue(self.foo in self.ra.symbols[self.foo])

    # bar = foo

    def test_assignment2(self):
        self.ra.loadSymbolInRegister(self.bar, "b") # bar was previously in reg b
        self.ra.loadSymbolInRegister(self.foo, "a") # foo is loaded in a
        self.ra.assignToSymbolWithRegister(self.bar, "a") # store foo (loaded in a) to bar
        self.assertEqual(self.ra.symbols[self.bar], {"a"}) # Note: b no longer holds updated bar and it is not stored yet to bar
        self.assertEqual(self.ra.registers["a"], {self.foo, self.bar}) # Now a holds both foo and bar

    # Spilling

    def test_spillRegister(self):
        self.ra.loadSymbolInRegister(self.foo, "a")
        self.ra.spillRegister("a")
        self.assertEqual(self.ra.symbols[self.foo], {self.foo})
        self.assertEqual(self.ra.registers["a"], set())
        self.assertTrue("a" in self.ra.freeRegisters)

    # If already in a register, use that register
    def test_alreadyInRegister(self):
        self.ra.loadSymbolInRegister(self.foo, "b")
        self.assertEqual(self.ra.getRegisterForSymbol(self.foo, ALL_REGISTERS), "b")

    # Not already in a register, but still free registers
    def test_notLoadedButFreeRegisters(self):
        self.ra.loadSymbolInRegister(self.foo, "a")
        self.assertEqual(self.ra.getRegisterForSymbol(self.bar, {"a", "b"}), "b")

    # Not already in a register, but still free registers
    def test_notLoadedMustSpill2(self):
        self.ra.loadSymbolInRegister(self.foo, "a")
        # Must spill register a
        self.assertEqual(self.ra.getRegisterForSymbol(self.bar, {"a"}), "a")
        # Check register a is no longer listed for foo
        self.assertEqual(self.ra.symbols[self.foo], {self.foo})
        # Check register a is now free
        self.assertTrue("a" in self.ra.freeRegisters)

    def test_spillRegister_dead(self):
        self.ra.loadSymbolInRegister(self.foo, "a")
        self.ra.currentInstruction.live["foo"] = False

        self.ra.spillRegister("a")

        self.assertEqual(self.ra.registers["a"], set())
        self.assertEqual(self.ra.symbols[self.foo], {self.foo})

    # spillAll
    def test_spillAll(self):
        self.ra.currentInstruction.live[self.foo] = True
        self.ra.currentInstruction.live[self.bar] = False
        self.ra.assignToSymbolWithRegister(self.foo, "a") # char
        self.ra.assignToSymbolWithRegister(self.bar, "b") # char

        self.ra.spillAll()

        self.assertEqual(self.ra.registers["a"], set())
        self.assertEqual(self.ra.registers["b"], set())
        # TODO how to test if it actually spills


    # spillAllMatchingType

    def test_spillAllMatchingType_int(self):
        foo = SymEntry("char", "foo")
        foo2 = SymEntry("char", "foo")
        baz = SymEntry("int", "baz")
        self.ra.currentInstruction.live[foo] = True
        self.ra.currentInstruction.live[foo2] = True
        self.ra.currentInstruction.live[baz] = True
        self.ra.assignToSymbolWithRegister(foo, "a") # char
        self.ra.assignToSymbolWithRegister(foo2, "b") # char
        self.ra.assignToSymbolWithRegister(baz, "c") # int

        self.ra.spillAllMatchingType("int")

        self.assertEqual(self.ra.registers["a"], {foo})
        self.assertEqual(self.ra.registers["b"], {foo2})
        self.assertEqual(self.ra.registers["c"], set())
        self.assertEqual(self.ra.symbols[baz], {baz})

    def test_spillAllMatchingType_char(self):
        foo = SymEntry("char", "foo")
        foo2 = SymEntry("char", "foo")
        baz = SymEntry("int", "baz")
        self.ra.currentInstruction.live[foo] = True
        self.ra.currentInstruction.live[foo2] = True
        self.ra.currentInstruction.live[baz] = True
        self.ra.assignToSymbolWithRegister(foo, "a") # char
        self.ra.assignToSymbolWithRegister(foo2, "b") # char
        self.ra.assignToSymbolWithRegister(baz, "c") # int

        self.ra.spillAllMatchingType("char")

        self.assertEqual(self.ra.registers["a"], set())
        self.assertEqual(self.ra.symbols[foo], {foo})
        self.assertEqual(self.ra.registers["b"], set())
        self.assertEqual(self.ra.symbols[foo2], {foo2})
        self.assertEqual(self.ra.registers["c"], {baz})


class TestZ80RA(unittest.TestCase):
    def setUp(self):
        self.foo = SymEntry("char", "foo")
        self.foo.impl = StackAddress(0)
        self.ptr = SymEntry("int", "ptr")
        self.ptr.impl = StackAddress(2)
        self.derefPtr = SymEntry("char", "deref")
        self.derefPtr.impl = PointerAddress(self.ptr)
        self.derefPtr16 = SymEntry("int", "deref16")
        self.derefPtr16.impl = PointerAddress(self.ptr)
        self.bar = SymEntry("char", "bar")
        self.bar.impl = StackAddress(-11)
        self.bar16 = SymEntry("char", "bar16")
        self.bar16.impl = StackAddress(-2)
        self.ra = Z80RegisterAllocator(StringIO())
        self.ra.currentInstruction = IR()
        self.ra.currentInstruction.live = { self.foo: True, self.bar: True, self.ptr: True }

    def test_loadInA_alreadyLoaded(self):
        self.ra.loadSymbolInRegister(self.foo, "a")
        r = self.ra.loadInA(self.foo) 
        self.assertEqual(r, "a")
        self.ra.asmFile.seek(0)
        self.assertEqual(self.ra.asmFile.read(), "")

    def test_loadInA_freeButNotLoaded(self):
        r = self.ra.loadInA(self.foo)
        self.assertEqual(r, "a")
        self.ra.asmFile.seek(0)
        self.assertEqual(self.ra.asmFile.read(), "\tld\ta, (ix + 0)\n")

    def test_loadInA_loadedInOtherRegister(self):
        self.ra.loadSymbolInRegister(self.foo, "b")
        r = self.ra.loadInA(self.foo)
        self.assertEqual(r, "a")
        self.ra.asmFile.seek(0)
        self.assertEqual(self.ra.asmFile.read(), "\tld\ta, b\n")

    def test_spill(self):
        self.ra.loadSymbolInRegister(self.foo, "a")
        r = self.ra.getRegisterForSymbol(self.bar, { "a" })
        self.assertEqual(r, "a")
        self.ra.asmFile.seek(0)
        self.assertIn("\tld\t(ix + 0), a\n", self.ra.asmFile.read())

    def test_spillRegisterPair(self):
        self.ra.loadSymbolInRegister(self.foo, "b")
        r = self.ra.getRegisterForSymbol(self.bar16, { "bc" })
        self.assertEqual(r, "bc")
        self.ra.asmFile.seek(0)
        self.assertIn("\tld\t(ix + 0), b\n", self.ra.asmFile.read())
        self.assertEqual(self.ra.registers["b"], set())

    def test_spillRegisterPair2(self):
        self.ra.loadSymbolInRegister(self.foo, "b")
        r = self.ra.getRegisterForSymbol(self.bar16, { "bc" })
        self.assertEqual(r, "bc")
        self.ra.asmFile.seek(0)
        self.assertIn("\tld\t(ix + 0), b\n", self.ra.asmFile.read())
        self.assertEqual(self.ra.registers["b"], set())

    # loadInA

    def test_loadInA_fromConstant(self):
        self.ra.loadInA(Constant("char", 42));

        self.ra.asmFile.seek(0)
        self.assertIn("\tld\ta, 42\n", self.ra.asmFile.read())

    def test_loadInA_fromMemory(self):
        self.ra.loadInA(self.foo);

        self.ra.asmFile.seek(0)
        self.assertIn("\tld\ta, (ix + 0)\n", self.ra.asmFile.read())

    # already in register b
    def test_loadInA_alreadyInRegister(self):
        self.ra.loadSymbolInRegister(self.foo, "b")

        self.ra.loadInA(self.foo);

        self.ra.asmFile.seek(0)
        self.assertIn("\tld\ta, b\n", self.ra.asmFile.read())

    # already in register a
    def test_loadInA_alreadyInRegisterA(self):
        self.ra.loadSymbolInRegister(self.foo, "a")

        self.ra.loadInA(self.foo);

        self.ra.asmFile.seek(0)
        self.assertEqual("", self.ra.asmFile.read())

    def test_loadInA_fromPointerInMemory(self):
        # Just to force de to be used
        self.ra.loadSymbolInRegister(self.foo, "bc")
        self.ra.loadSymbolInRegister(self.foo, "hl")

        self.ra.loadInA(self.derefPtr);

        self.ra.asmFile.seek(0)
        output = self.ra.asmFile.read()
        self.assertIn("\tld\td, (ix + 3)", output)
        self.assertIn("\tld\te, (ix + 2)", output)
        self.assertIn("\tld\ta, (de)", output)

    def test_loadInA_fromPointerInRegister(self):
        self.ra.loadSymbolInRegister(self.ptr, "de")
        self.ra.loadInA(self.derefPtr);

        self.ra.asmFile.seek(0)
        output = self.ra.asmFile.read()
        self.assertEqual("\tld\ta, (de)\n", output)

    # loadInHL

    def test_loadInHL_fromPointerInRegister(self):
        self.ra.loadSymbolInRegister(self.ptr, "de")
        self.ra.loadInHL(self.derefPtr16);

        self.ra.asmFile.seek(0)
        output = self.ra.asmFile.read()
        self.assertIn("\tld\tl, (de)\n", output)
        self.assertIn("\tinc\tde\n", output)
        self.assertIn("\tld\th, (de)\n", output)
        self.assertIn("\tdec\tde\n", output)

    def test_loadInHL_fromPointerInRegisterWhichIsDead(self):
        self.ra.loadSymbolInRegister(self.ptr, "de")
        self.ra.currentInstruction.live[self.ptr] = False
        self.ra.loadInHL(self.derefPtr16);

        self.ra.asmFile.seek(0)
        output = self.ra.asmFile.read()
        # No need to restore the pointer
        self.assertNotIn("\tdec\tde\n", output)
        self.assertFalse(self.ra.isInRegister("ptr", { "de" }))
        # TODO also check that we don't ruin the register if it also stores a different name

    def test_loadInHL_fromOtherRegister(self):
        self.ra.loadSymbolInRegister(self.foo, "de")
        self.ra.loadInHL(self.foo);

        self.ra.asmFile.seek(0)
        output = self.ra.asmFile.read()
        self.assertIn("\tld\th, d\n", output)
        self.assertIn("\tld\tl, e\n", output)

    def test_loadInHL_fromPointerInHL(self):
        # Just to force de to be used
        self.ra.loadSymbolInRegister(self.foo, "bc")
        self.ra.loadSymbolInRegister(self.ptr, "hl")
        self.ra.loadInHL(self.derefPtr16);

        self.ra.asmFile.seek(0)
        output = self.ra.asmFile.read()

        # Expect copy pointer in hl to de
        self.assertIn("\tld\td, h\n", output)
        self.assertIn("\tld\te, l\n", output)
        # Expect spilling of hl to ptr
        self.assertIn("\tld\t(ix + 3), h\n", output)
        self.assertIn("\tld\t(ix + 2), l\n", output)
        # Expect loading hl from (de)
        self.assertIn("\tld\tl, (de)\n", output)
        self.assertIn("\tinc\tde\n", output)
        self.assertIn("\tld\th, (de)\n", output)
