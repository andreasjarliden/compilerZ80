import unittest
from registerAllocator import *
from symbolTable import SymbolTable
from io import StringIO
from symEntry import *
from address import *
from asmWriter import AsmWriter
from ir import *


class TestRA(unittest.TestCase):
    def setUp(self):
        symbolTable = SymbolTable()
        symbolTable.addSymbol("char", "foo")
        symbolTable.addSymbol("char", "bar")
        symbolTable.addSymbol("int", "baz")
        self.ra = RegisterAllocator(symbolTable.currentSymbolTable())
        self.ra.currentInstruction = IR()
        self.ra.currentInstruction.live = { "foo": True, "bar": True, "fiz": True }

    def test_loadRegister(self):
        self.ra.loadNameInRegister("foo", "a")
        self.assertEqual(self.ra.addresses["foo"], {"foo", "a"})
        self.assertEqual(self.ra.registers["a"], {"foo"})
        self.assertFalse("a" in self.ra.freeRegisters)

    def test_loadRegister_replacingOld(self):
        self.ra.loadNameInRegister("bar", "c") # bar previously loaded in c
        self.ra.loadNameInRegister("foo", "a")
        self.ra.loadNameInRegister("bar", "a") # a no longer contains foo
        self.assertEqual(self.ra.addresses["bar"], {"bar", "a", "c"})
        self.assertTrue("bar" in self.ra.registers["a"]) 
        self.assertFalse("a" in self.ra.freeRegisters)

    def test_isFree(self):
        self.assertEqual(self.ra.isFree("b"), True); # Free from start
        self.ra.loadNameInRegister("foo", "b")
        self.assertEqual(self.ra.isFree("b"), False); 

    def test_isFree_coupledRegisters(self):
        self.assertEqual(self.ra.isFree("bc"), True); # Free from start
        self.ra.loadNameInRegister("foo", "b")
        self.assertEqual(self.ra.isFree("bc"), False); 

    def test_isFree_coupledRegisters2(self):
        self.assertEqual(self.ra.isFree("b"), True); # Free from start
        self.ra.loadNameInRegister("foo", "bc")
        self.assertEqual(self.ra.isFree("b"), False); 

    def test_storeToName(self):
        self.ra.storeToName("foo")
        self.assertTrue("foo" in self.ra.addresses["foo"])

    # bar = foo

    def test_assignment(self):
        self.ra.loadNameInRegister("bar", "b") # bar was previously in reg b
        self.ra.loadNameInRegister("foo", "a") # foo is loaded in a
        self.ra.assignToNameWithRegister("bar", "a") # store foo (loaded in a) to bar
        self.assertEqual(self.ra.addresses["bar"], {"a"}) # Note: b no longer holds updated bar and it is not stored yet to bar
        self.assertEqual(self.ra.registers["a"], {"foo", "bar"}) # Now a holds both foo and bar

    # Spilling

    def test_spillRegister(self):
        self.ra.loadNameInRegister("foo", "a")
        self.ra.spillRegister("a")
        self.assertEqual(self.ra.addresses["foo"], {"foo"})
        self.assertEqual(self.ra.registers["a"], set())
        self.assertTrue("a" in self.ra.freeRegisters)

    # If already in a register, use that register
    def test_alreadyInRegister(self):
        self.ra.loadNameInRegister("foo", "b")
        self.assertEqual(self.ra.getRegisterForArg("foo", ALL_REGISTERS), "b")

    # Not already in a register, but still free registers
    def test_notLoadedButFreeRegisters(self):
        self.ra.loadNameInRegister("foo", "a")
        self.assertEqual(self.ra.getRegisterForArg("bar", {"a", "b"}), "b")

    # Not already in a register, but still free registers
    def test_notLoadedMustSpill(self):
        self.ra.loadNameInRegister("foo", "a")
        # Must spill register a
        self.assertEqual(self.ra.getRegisterForArg("bar", {"a"}), "a")
        # Check register a is no longer listed for foo
        self.assertEqual(self.ra.addresses["foo"], {"foo"})
        # Check register a is now free
        self.assertTrue("a" in self.ra.freeRegisters)

    def test_spillRegister_dead(self):
        self.ra.loadNameInRegister("foo", "a")
        self.ra.currentInstruction.live["foo"] = False

        self.ra.spillRegister("a")

        self.assertEqual(self.ra.registers["a"], set())
        self.assertEqual(self.ra.addresses["foo"], {"foo"})

    def test_spillAllMatchingType_char(self):
        self.ra.currentInstruction.live["foo"] = True
        self.ra.currentInstruction.live["bar"] = True
        self.ra.currentInstruction.live["baz"] = True
        self.ra.assignToNameWithRegister("foo", "a") # char
        self.ra.assignToNameWithRegister("bar", "b") # char
        self.ra.assignToNameWithRegister("baz", "c") # int

        self.ra.spillAllMatchingType("char")

        self.assertEqual(self.ra.registers["a"], set())
        self.assertEqual(self.ra.addresses["foo"], {"foo"})
        self.assertEqual(self.ra.registers["b"], set())
        self.assertEqual(self.ra.addresses["bar"], {"bar"})
        self.assertEqual(self.ra.registers["c"], {"baz"})

    def test_spillAllMatchingType_int(self):
        self.ra.currentInstruction.live["foo"] = True
        self.ra.currentInstruction.live["bar"] = True
        self.ra.currentInstruction.live["baz"] = True
        self.ra.assignToNameWithRegister("foo", "a") # char
        self.ra.assignToNameWithRegister("bar", "b") # char
        self.ra.assignToNameWithRegister("baz", "c") # int

        self.ra.spillAllMatchingType("int")

        self.assertEqual(self.ra.registers["a"], {"foo"})
        self.assertEqual(self.ra.registers["b"], {"bar"})
        self.assertEqual(self.ra.registers["c"], set())
        self.assertEqual(self.ra.addresses["baz"], {"baz"})


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
        self.symbolTable = { "foo": self.foo, "bar": self.bar, "ptr": self.ptr, "bar16": self.bar16, "deref": self.derefPtr, "deref16": self.derefPtr16 }
        self.ra = Z80RegisterAllocator(StringIO(), self.symbolTable)
        self.ra.currentInstruction = IR()
        self.ra.currentInstruction.live = { "foo": True, "bar": True, "ptr": True }

    def test_loadInA_alreadyLoaded(self):
        self.ra.loadNameInRegister("foo", "a")
        r = self.ra.loadInA(SymEntry("char", "foo")) 
        self.assertEqual(r, "a")
        self.ra.asmFile.seek(0)
        self.assertEqual(self.ra.asmFile.read(), "")

    def test_loadInA_freeButNotLoaded(self):
        r = self.ra.loadInA(self.foo)
        self.assertEqual(r, "a")
        self.ra.asmFile.seek(0)
        self.assertEqual(self.ra.asmFile.read(), "\tld\ta, (ix + 0)\n")

    def test_loadInA_loadedInOtherRegister(self):
        self.ra.loadNameInRegister("foo", "b")
        r = self.ra.loadInA(SymEntry("char", "foo"))
        self.assertEqual(r, "a")
        self.ra.asmFile.seek(0)
        self.assertEqual(self.ra.asmFile.read(), "\tld\ta, b\n")

    def test_spill(self):
        self.ra.loadNameInRegister("foo", "a")
        r = self.ra.getRegisterForArg("bar", { "a" })
        self.assertEqual(r, "a")
        self.ra.asmFile.seek(0)
        self.assertIn("\tld\t(ix + 0), a\n", self.ra.asmFile.read())

    def test_spillRegisterPair(self):
        self.ra.loadNameInRegister("foo", "b")
        r = self.ra.getRegisterForArg("bar16", { "bc" })
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
        self.ra.loadNameInRegister("foo", "b")

        self.ra.loadInA(self.foo);

        self.ra.asmFile.seek(0)
        self.assertIn("\tld\ta, b\n", self.ra.asmFile.read())

    # already in register a
    def test_loadInA_alreadyInRegisterA(self):
        self.ra.loadNameInRegister("foo", "a")

        self.ra.loadInA(self.foo);

        self.ra.asmFile.seek(0)
        self.assertEqual("", self.ra.asmFile.read())

    def test_loadInA_fromPointerInMemory(self):
        # Just to force de to be used
        self.ra.loadNameInRegister("foo", "bc")
        self.ra.loadNameInRegister("foo", "hl")

        self.ra.loadInA(self.derefPtr);

        self.ra.asmFile.seek(0)
        output = self.ra.asmFile.read()
        self.assertIn("\tld\td, (ix + 3)", output)
        self.assertIn("\tld\te, (ix + 2)", output)
        self.assertIn("\tld\ta, (de)", output)

    def test_loadInA_fromPointerInRegister(self):
        self.ra.loadNameInRegister("ptr", "de")
        self.ra.loadInA(self.derefPtr);

        self.ra.asmFile.seek(0)
        output = self.ra.asmFile.read()
        self.assertEqual("\tld\ta, (de)\n", output)

    # loadInHL

    def test_loadInHL_fromPointerInRegister(self):
        self.ra.loadNameInRegister("ptr", "de")
        self.ra.loadInHL(self.derefPtr16);

        self.ra.asmFile.seek(0)
        output = self.ra.asmFile.read()
        self.assertIn("\tld\tl, (de)\n", output)
        self.assertIn("\tinc\tde\n", output)
        self.assertIn("\tld\th, (de)\n", output)
        self.assertIn("\tdec\tde\n", output)

    def test_loadInHL_fromPointerInRegisterWhichIsDead(self):
        self.ra.loadNameInRegister("ptr", "de")
        self.ra.currentInstruction.live["ptr"] = False
        self.ra.loadInHL(self.derefPtr16);

        self.ra.asmFile.seek(0)
        output = self.ra.asmFile.read()
        # No need to restore the pointer
        self.assertNotIn("\tdec\tde\n", output)
        self.assertFalse(self.ra.isInRegiser("ptr", { "de" }))
        # TODO also check that we don't ruin the register if it also stores a different name

    def test_loadInHL_fromOtherRegister(self):
        self.ra.loadNameInRegister("foo", "de")
        self.ra.loadInHL(self.foo);

        self.ra.asmFile.seek(0)
        output = self.ra.asmFile.read()
        self.assertIn("\tld\th, d\n", output)
        self.assertIn("\tld\tl, e\n", output)

    def test_loadInHL_fromPointerInHL(self):
        # Just to force de to be used
        self.ra.loadNameInRegister("foo", "bc")
        self.ra.loadNameInRegister("ptr", "hl")
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
