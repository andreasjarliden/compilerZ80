from asmWriter import AsmWriter
from symEntry import StackAddress
import unittest
from io import StringIO

class TestAsmWriter(unittest.TestCase):
    def setUp(self):
        self.writer = AsmWriter(StringIO())

    def checkOutput(self):
        self.writer.file.seek(0)
        self.output = self.writer.file.read()

    def test_loadRegisterWithAddress8(self):
        v = StackAddress(42)
        self.writer.loadRegisterWithAddress("a", v)

        self.checkOutput()
        self.assertEqual(self.output, "\tld\ta, (ix + 42)\n")

    def test_loadRegisterWithAddress16(self):
        v = StackAddress(42)
        self.writer.loadRegisterWithAddress("bc", v)

        self.checkOutput()
        self.assertIn("\tld\tb, (ix + 43)\n", self.output)
        self.assertIn("\tld\tc, (ix + 42)\n", self.output)

    def test_loadRegisterWithRegister8(self):
        self.writer.loadRegisterWithRegister("a", "b")

        self.checkOutput()
        self.assertIn("\tld\ta, b\n", self.output)

    def test_loadRegisterWithRegister16(self):
        self.writer.loadRegisterWithRegister("bc", "de")

        self.checkOutput()
        self.assertIn("\tld\tb, d\n", self.output)
        self.assertIn("\tld\tc, e\n", self.output)

