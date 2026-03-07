import unittest
from io import StringIO
from symEntry import *
import address
import ir
import registerAllocator

class TestIR(unittest.TestCase):
    def setUp(self):
        self.foo = SymEntry("char", "char", "foo")
        symbolTable = { self.foo.name: self.foo }
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


