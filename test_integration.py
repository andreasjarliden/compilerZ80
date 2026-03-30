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

    def test_globalVariable_char(self):
        output = compile("""
            char FOO;
            char main() {
                FOO=1;
            }""")
        self.assertRegex(output, r"ld\t., 1")
        self.assertRegex(output, r"ld\t\(FOO\), .")
        self.assertRegex(output, r"FOO:\t.int8\t0")

    def test_globalVariable_int(self):
        output = compile("""
            int FOO;
            char main() {
                FOO=1;
            }""")
        print(output)
        self.assertRegex(output, r"ld\t(bc|de|hl), 1")
        self.assertRegex(output, r"ld\t\(FOO\), (bc|de|hl)")
        self.assertRegex(output, r"FOO:\t.int16\t0")

    def test_globalVariable_charReturn(self):
        output = compile("""
            char FOO;
            char main() {
                return FOO;
            }""")
        self.assertIn("ld\ta, (FOO)", output)

    def test_globalVariables_charAdd(self):
        output = compile("""
            char FOO;
            char main(char a) {
                return FOO+a;
            }""")
        self.assertIn("ld\ta, (FOO)", output)
        self.assertRegex(output, r"ld\t., \(ix \+ 5\)")
        self.assertRegex(output, r"add\ta, .")

    def test_globalVariables_intAdd(self):
        output = compile("""
            int FOO;
            int main(int bar) {
                return FOO+bar;
            }""")
        print(output)
        self.assertRegex(output, r"ld\thl, \(FOO\)")
        self.assertRegex(output, r"ld\t., \(ix \+ 5\)")
        self.assertRegex(output, r"ld\t., \(ix \+ 4\)")
        self.assertRegex(output, r"add\thl, (bc|de|hl)")

    def test_globalVariablesWithValue(self):
        output = compile("int FOO = 42;")
        self.assertRegex(output, r"FOO:\t.int16\t42")
        
    def test_globalVariablesWithString(self):
        output = compile('char* FOO = "foo";')
        print(output)
        self.assertRegex(output, r'FOO:\t.string\t"foo\\0"')

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

