import unittest
from parser import parser
from compiler import astToThreeCode, updateLive, genCode, genDataSegment
from asmWriter import AsmWriter
from io import StringIO
from pprint import *
from astnodes import ASTContext

def compile(code):
    asmWriter = AsmWriter(StringIO())
    ast = parser.parse(code)
    astContext = ASTContext()
    blocks, dataSegment = astToThreeCode(ast, astContext)
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
        print(output)
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
        self.assertRegex(output, r"ld\thl, \(FOO\)")
        self.assertRegex(output, r"ld\t., \(ix \+ 5\)")
        self.assertRegex(output, r"ld\t., \(ix \+ 4\)")
        self.assertRegex(output, r"add\thl, (bc|de|hl)")

    def test_globalVariablesWithValue(self):
        output = compile("int FOO = 42;")
        print(output)
        self.assertRegex(output, r"FOO:\t.int16\t42")
        
    def test_globalStringVariables(self):
        output = compile('char* FOO;')
        print(output)
        self.assertIn('FOO:\t.int16\t0', output)

    def test_globalVariablesWithString(self):
        output = compile('char* FOO = "foo";')
        print(output)
        self.assertIn('__str0:\t.string\t"foo\\0"', output)
        self.assertIn('FOO:\t.int16\t__str0', output)

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
        print(output)
        self.assertIn("ld\t(FOO),", output)
        self.assertTrue(output.find("ld\t(FOO),") < output.find("call\tfoo"))

    def test_stringArgument(self):
        output = compile("""
            char main(char* str) {
                main("foo");
            }""")
        print(output)
        self.assertIn("ld\thl, __str0\n\tpush\thl", output)
        self.assertIn('__str0:\t.string\t"foo\\0"', output)

    def test_identicalStringsReused(self):
        output = compile("""
            char main(char* str, char* str2) {
                main("foo", "foo");
            }""")
        print(output)
        self.assertIn("ld\thl, __str0\n\tpush\thl\n\tpush\thl", output)
        self.assertIn('__str0:\t.string\t"foo\\0"', output)

    def test_localStrings(self):
        output = compile("""
            char main(char* foo) {
                char* str;
                str = "foo";
                main(str);
            }""")
        self.assertRegex(output, r"ld\t(bc|de|hl), __str0\n\tpush\t(bc|hl|de)", output)
        self.assertIn('__str0:\t.string\t"foo\\0"', output)

    def test_localStrings2(self):
        output = compile("""
            char main(char* foo) {
                char* str = "foo";
                main(str);
            }""")
        print(output)
        self.assertRegex(output, r"ld\t(bc|de|hl), __str0\n\tpush\t(bc|de|hl)", output)
        self.assertIn('__str0:\t.string\t"foo\\0"', output)

