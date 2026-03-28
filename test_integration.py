import unittest
from parser import parser
from compiler import astToThreeCode, updateLive, genCode, genDataSegment
from asmWriter import AsmWriter
from io import StringIO
from pprint import *

def compile(code):
    asmWriter = AsmWriter(StringIO())
    ast = parser.parse(code)
    blocks, dataSegment = astToThreeCode(ast)
    pprint(blocks)
    updateLive(blocks)
    genCode(blocks, asmWriter)
    genDataSegment(dataSegment, asmWriter)
    asmWriter.seek(0)
    return asmWriter.read()

class TestIntegration(unittest.TestCase):
    def setUp(self):
        self.asmWriter = AsmWriter(StringIO())


    def test_localVariable(self):
        output = compile("""
            char main() {
                char FOO;
                FOO=1;
            }""")
        self.assertRegex(output, r"ld\t., 1")
        self.assertRegex(output, r"ld\t\(ix \- 1\), .")

    def test_globalVariable(self):
        output = compile("""
            char FOO;
            char main() {
                FOO=1;
            }""")
        self.assertRegex(output, r"ld\t., 1")
        self.assertRegex(output, r"ld\t\(FOO\), .")
        self.assertRegex(output, r"FOO:\t.int8\t0")

    def test_globalVariable2(self):
        output = compile("""
            char FOO;
            char main() {
                return FOO;
            }""")
        self.assertIn("ld\ta, (FOO)", output)

    def test_globalVariable3(self):
        output = compile("""
            char FOO;
            char main(char a) {
                return FOO+a;
            }""")
        self.assertIn("ld\ta, (FOO)", output)
        self.assertRegex(output, r"ld\t., \(ix \+ 5\)")
        self.assertRegex(output, r"add\ta, .")
        
    def test_spillBeforeFunCall(self):
        output = compile("""
            char FOO;
            char foo() {
                return FOO;
            }
            char main(char a) {
                FOO = 42;
                foo();
            }""")
        self.assertIn("ld\t(FOO),", output)
        self.assertTrue(output.find("ld\t(FOO),") < output.find("call\tfoo"))

