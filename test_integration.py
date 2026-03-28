import unittest
from parser import parser
from compiler import astToThreeCode, updateLive, genCode, genDataSegment
from asmWriter import AsmWriter
from io import StringIO
from pprint import *

class TestIntegration(unittest.TestCase):
    def setUp(self):
        self.asmWriter = AsmWriter(StringIO())

    def test_localVariable(self):
        ast = parser.parse("""
            char main() {
                char FOO;
                FOO=1;
            }""")
        blocks, dataSegment = astToThreeCode(ast)
        pprint(blocks)
        updateLive(blocks)
        genCode(blocks, self.asmWriter)
        genDataSegment(dataSegment, self.asmWriter)
        self.asmWriter.seek(0)
        output = self.asmWriter.read()
        self.assertRegex(output, r"ld\t., 1")
        self.assertRegex(output, r"ld\t\(ix \- 1\), .")

    def test_globalVariable(self):
        ast = parser.parse("""
            char FOO;
            char main() {
                FOO=1;
            }""")
        blocks, dataSegment = astToThreeCode(ast)
        pprint(blocks)
        updateLive(blocks)
        genCode(blocks, self.asmWriter)
        genDataSegment(dataSegment, self.asmWriter)
        self.asmWriter.seek(0)
        output = self.asmWriter.read()
        self.assertRegex(output, r"ld\t., 1")
        self.assertRegex(output, r"ld\t\(FOO\), .")
        self.assertRegex(output, r"FOO:\t.int8\t0")

    def test_globalVariable2(self):
        ast = parser.parse("""
            char FOO;
            char main() {
                return FOO;
            }""")
        blocks, dataSegment = astToThreeCode(ast)
        pprint(blocks)
        updateLive(blocks)
        genCode(blocks, self.asmWriter)
        genDataSegment(dataSegment, self.asmWriter)
        self.asmWriter.seek(0)
        output = self.asmWriter.read()
        self.assertIn("ld\ta, (FOO)", output)

    def test_globalVariable3(self):
        ast = parser.parse("""
            char FOO;
            char main(char a) {
                return FOO+a;
            }""")
        blocks, dataSegment = astToThreeCode(ast)
        pprint(blocks)
        updateLive(blocks)
        genCode(blocks, self.asmWriter)
        genDataSegment(dataSegment, self.asmWriter)
        self.asmWriter.seek(0)
        output = self.asmWriter.read()
        self.assertIn("ld\ta, (FOO)", output)
        self.assertRegex(output, r"ld\t., \(ix \+ 5\)")
        self.assertRegex(output, r"add\ta, .")
