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
        symbolTable = { self.foo.name: self.foo,
                       self.bar.name: self.bar
                       }
        self.bar.impl = StackAddress(2)
        stringIO = StringIO()
        ir.asmFile = stringIO
        ir.asmWriter = ir.asmFile
        registerAllocator.RA = registerAllocator.Z80RegisterAllocator(ir.asmFile, symbolTable)

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

    def test_IRAssign_alreadyInRegister(self):
        registerAllocator.RA.loadNameInRegister("bar", "a")

        ira = ir.IRAssign(self.foo, self.bar)
        ira.live[self.foo.name] = True
        ira.live[self.bar.name] = True
        ira.genCode()

        ir.asmFile.seek(0)
        output = ir.asmFile.read()
        self.assertEqual(output, "")
        self.assertEqual(registerAllocator.RA.isInRegister("foo"), "a")





