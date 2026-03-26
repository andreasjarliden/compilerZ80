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
        print(blocks)
        genCode(blocks, self.asmWriter)
        genDataSegment(dataSegment, self.asmWriter)
        self.asmWriter.seek(0)
        output = self.asmWriter.read()
        print(output)
        print(dataSegment)

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
        print(output)
        print(dataSegment)
        self.assertRegex(output, r"ld\t., 1")
        self.assertRegex(output, r"ld\t\(FOO\), .")
        self.assertRegex(output, r"FOO:\t.int8\t0")


