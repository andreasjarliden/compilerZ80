import unittest
from io import StringIO
from symEntry import *
from address import *

RA = None
ALL_REGISTERS = {'a', 'b', 'c', 'd', 'e', 'h', 'l', 'bc', 'de', 'hl'}

class RegisterAllocator:
    def __init__(self, addresses):
        self.registers = {r: set() for r in ALL_REGISTERS}
        self.addresses = {a: {a} for a in addresses}
        self.coupledRegisters = { 'bc': ('b', 'c'),
                                 'b': ['bc'],
                                 'c': ('bc',),
                                 'de': ('d', 'e'),
                                 'd': ['de'],
                                 'e': ('de',),
                                 'hl': ('h', 'l'),
                                 'h': ['hl'],
                                 'l': ('hl',) }

    def __repr__(self):
        return f"registers: {self.registers}\nfree registers: {self.freeRegisters}\naddresses: {self.addresses}"

    def doSpill(self, reg, name):
        pass

    def isFree(self, r):
        if self.registers[r]:
            return False
        for cr in self.coupledRegisters.get(r, ()):
            if self.registers[cr]:
                return False
        return True

    @property
    def freeRegisters(self):
        free = []
        for r in self.registers:
            if self.isFree(r):
                free.append(r)
        return set(free)

    def spillRegister(self, r):
        # Remove register from all addresses
        for n in self.registers[r]:
            self.addresses[n].remove(r)
            self.doSpill(r, n)
        # Register no longer contains anything
        self.registers[r] = set()

    def spillScore(self, r):
        score = 0
        for n in self.registers[r]:
            # If n is in some other register. Consider it free to spill.
            # (disregard if we have different groups of registers)
            if len(self.addresses[n]) > 1:
                continue
            # Is n what we are assigning to? In that case free to spill

    def getRegisterForArg(self, name, possibleRegisters):
        # Already loaded?
        regs = self.addresses[name] & possibleRegisters
        if regs:
            return regs.pop()
        # No, pick one of the free registers
        regs = self.freeRegisters & possibleRegisters
        if regs:
            return regs.pop()
        # No free, have to spill
        r = next(iter(possibleRegisters))
        self.spillRegister(r)
        # Spill any coupled register, e.g. spilling bc means also spilling b and c (if loaded). 
        for cr in self.coupledRegisters.get(r, ()):
            self.spillRegister(cr)
        return r

    # TODO test
    def isInRegister(self, name, possibleRegisters = ALL_REGISTERS):
        # Already loaded?
        regs = self.addresses[name] & possibleRegisters
        if regs:
            return regs.pop()
        else:
            return None

    # Note: This doesn't handle any spilling. r is assumed to be free.
    def loadNameInRegister(self, n, r):
        self.addresses[n].add(r)
        self.registers[r].add(n)

    # Example: LD (ix+n), a
    def storeToName(self, n):
        self.addresses[n].add(n)

    # Example ADD r, ... where a represents name
    def operationToNameWithRegister(self, n, r):
        oldNames = self.registers[r]
        for oldName in oldNames:
            self.addresses[oldName].remove(r)
        self.registers[r] = { n }
        self.addresses[n] = { r }

    # Example: LD a, b
    def copyFromRegisterToName(self, r, n):
        self.registers[r].add(n)
        self.addresses[n] = { r }


class TestRA(unittest.TestCase):
    def setUp(self):
        self.ra = RegisterAllocator(["foo", "bar", "fiz"])

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

    def test_operation(self):
        self.ra.loadNameInRegister("fiz", "a") # will be replaced

        # foo = bar + baz
        # a = b + c
        self.ra.operationToNameWithRegister("foo", "a")

        self.assertEqual(self.ra.registers["a"], {"foo"}) # Now hold foo but no longer fiz
        self.assertEqual(self.ra.addresses["foo"], {"a"}) # Only in register, not stored to foo
        self.assertFalse("a" in self.ra.addresses["fiz"]) # fiz no longer held by a

    # bar = foo
    def test_assignment(self):
        self.ra.loadNameInRegister("bar", "b") # bar was previously in reg b
        self.ra.loadNameInRegister("foo", "a") # foo is loaded in a
        self.ra.copyFromRegisterToName("a", "bar") # store foo (loaded in a) to bar
        self.assertEqual(self.ra.addresses["bar"], {"a"}) # Note: b no longer holds updated bar and it is not stored yet to bar
        self.assertEqual(self.ra.registers["a"], {"foo", "bar"}) # Now a holds both foo and bar
        # self.assertEqual(self.ra.registers["b"], set()) # b is now free

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


class Z80RegisterAllocator(RegisterAllocator):
    def __init__(self, asmFile, symbolTable):
        super().__init__(symbolTable.keys())
        self.symbolTable = symbolTable
        self.asmFile = asmFile

    def doSpill(self, r, name):
        offset = self.symbolTable[name].impl.offset
        self.asmFile.write(f"\tld\t(ix + {offset}), {r}\n")

    def loadInA(self, address):
        # Is constant?
        if isinstance(address, Constant):
            # TODO what address should we write for the value?
            self.asmFile.write(f'\tld\ta, {address.value}\n')
            return
        # Get register a, spilling if needed
        regY = self.getRegisterForArg(address.name, { "a" })
        # Already loaded?
        if address.name not in self.registers[regY]:
            # No, already in a register?
            inReg = self.isInRegister(address.name, { "b", "c", "d", "e", "h", "l" })
            if inReg:
                # Yes, just move register
                self.asmFile.write(f'\tld\ta, {inReg}\n')
                self.loadNameInRegister(address.name, "a")
            else:
                # No, load from memory
                self.asmFile.write(f'\tld\t{regY}, {address.impl.codeArg()}\n')
                self.loadNameInRegister(address.name, regY)
        return regY

    def loadInHL(self, address):
        # Is constant?
        if isinstance(address, Constant):
            # TODO what address to write for the value?
            self.asmFile.write(f'\tld\thl, {address.value}\n')
            return
        # Get register hl, spilling if needed
        regY = self.getRegisterForArg(address.name, { "hl" })
        # Already loaded?
        if address.name not in self.registers[regY]:
            # No, already in a register?
            # TODO add IY?
            inReg = self.isInRegister(address.name, { "bc", "de", "hl" })
            if inReg:
                # Yes, just move register
                self.asmFile.write(f'\tld\th, {inReg[0]}\n')
                self.asmFile.write(f'\tld\tl, {inReg[1]}\n')
                self.loadNameInRegister(address.name, "a")
            else:
                # No, load from memory
                self.asmFile.write(f'\tld\th, {address.impl.codeArg(+1)}\n')
                self.asmFile.write(f'\tld\tl, {address.impl.codeArg()}\n')
                self.loadNameInRegister(address.name, "hl")

class TestZ80RA(unittest.TestCase):
    def setUp(self):
        self.foo = SymEntry("char", "char", "foo")
        self.foo.impl = StackVariable(0)
        self.bar = SymEntry("char", "char", "bar")
        self.bar.impl = StackVariable(-11)
        self.bar16 = SymEntry("char", "char", "bar16")
        self.bar16.impl = StackVariable(-2)
        self.symbolTable = { "foo": self.foo, "bar": self.bar, "bar16": self.bar16 }
        self.ra = Z80RegisterAllocator(StringIO(), self.symbolTable)

    def test_loadInA_alreadyLoaded(self):
        self.ra.loadNameInRegister("foo", "a")
        r = self.ra.loadInA(SymEntry("char", "char", "foo")) 
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
        r = self.ra.loadInA(SymEntry("char", "char", "foo"))
        self.assertEqual(r, "a")
        self.ra.asmFile.seek(0)
        self.assertEqual(self.ra.asmFile.read(), "\tld\ta, b\n")

    def test_spill(self):
        self.ra.loadNameInRegister("foo", "a")
        r = self.ra.getRegisterForArg("bar", { "a" })
        self.assertEqual(r, "a")
        self.ra.asmFile.seek(0)
        self.assertEqual(self.ra.asmFile.read(), "\tld\t(ix + 0), a\n")

    def test_spillRegisterPair(self):
        self.ra.loadNameInRegister("foo", "b")
        r = self.ra.getRegisterForArg("bar16", { "bc" })
        self.assertEqual(r, "bc")
        self.ra.asmFile.seek(0)
        self.assertEqual(self.ra.asmFile.read(), "\tld\t(ix + 0), b\n")
        self.assertEqual(self.ra.registers["b"], set())
