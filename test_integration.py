import unittest
from testutilities import compile

class TestIntegration(unittest.TestCase):
    def test_localVariable(self):
        output = compile("""
            char main() {
                char FOO;
                FOO=1;
            }""")
        self.assertRegex(output, r"ld\t., 1")
        self.assertRegex(output, r"ld\t\(ix \- 1\), .")

    def test_globalVariable_assignChar(self):
        output = compile("""
            char FOO;
            char main() {
                FOO=1;
            }""")
        self.assertRegex(output, r"ld\t., 1")
        self.assertRegex(output, r"ld\t\(FOO\), .")
        self.assertRegex(output, r"FOO:\t.int8\t0")

    def test_globalVariable_readIntValue(self):
        output = compile("""
            int FOO=1;
            void main() {
                int f = FOO;
            }""")
        print(output)
        self.assertRegex(output, r"ld\t(bc|de|hl), \(FOO\)")
        self.assertRegex(output, r"FOO:\t.int16\t1")

    def test_globalVariable_readPointerValue(self):
        output = compile("""
            int* FOO=1;
            void main() {
                int* f = FOO;
            }""")
        print(output)
        self.assertRegex(output, r"ld\t(bc|de|hl), \(FOO\)")
        self.assertRegex(output, r"FOO:\t.int16\t1")

    def test_globalVariable_int(self):
        output = compile("""
            int FOO;
            char main() {
                FOO=1;
            }""")
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
        self.assertRegex(output, r"FOO:\t.int16\t42")
        
    def test_globalStringVariables(self):
        output = compile('char* FOO;')
        self.assertIn('FOO:\t.int16\t0', output)

    def test_globalVariablesWithString(self):
        output = compile('char* FOO = "foo";')
        self.assertIn('__str0:\t.string\t"foo\\0"', output)
        self.assertIn('FOO:\t.int16\t__str0', output)

    def test_addressOfGlobalVariable(self):
        output = compile("""
            int FOO=1;
            void main() {
                int* f = &FOO;
                *f=1;
            }""")
        self.assertRegex(output, r"ld\t(bc|de|hl), FOO")

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

    def test_stringArgument(self):
        output = compile("""
            char main(char* str) {
                main("foo");
            }""")
        self.assertIn("ld\thl, __str0\n\tpush\thl", output)
        self.assertIn('__str0:\t.string\t"foo\\0"', output)

    def test_globalStringAssignment(self):
        output = compile("""
            char* FOO = "foo";
            char main(char* str) {
                main(FOO);
                FOO = "bar";
            }""")
        # Loading original FOO
        self.assertRegex(output, r"ld\t(bc|de|hl), \(FOO\)\n\tpush\t(bc|de|hl)")
        # Loading new value
        self.assertRegex(output, r"ld\t(bc|de|hl), __str1")
        # Spilling new value
        self.assertRegex(output, r"ld\t\(FOO\), (bc|de|hl)")
        self.assertIn('__str0:\t.string\t"foo\\0"', output)
        self.assertIn('__str1:\t.string\t"bar\\0"', output)

    def test_identicalStringsReused(self):
        output = compile("""
            char main(char* str, char* str2) {
                main("foo", "foo");
            }""")
        print(output)
        self.assertIn("ld\thl, __str0\n", output)
        self.assertIn("push\thl\n", output)
        self.assertIn("push\thl", output)
        self.assertIn('__str0:\t.string\t"foo\\0"', output)

    def test_localStrings(self):
        output = compile("""
            char main(char* foo) {
                char* str;
                str = "foo";
                main(str);
            }""")
        self.assertRegex(output, r"ld\t(bc|de|hl), __str0\n")
        self.assertRegex(output, r"push\t(bc|hl|de)")
        self.assertIn('__str0:\t.string\t"foo\\0"', output)

    def test_localStrings2(self):
        output = compile("""
            char main(char* foo) {
                char* str = "foo";
                main(str);
            }""")
        self.assertRegex(output, r"ld\t(bc|de|hl), __str0\n")
        self.assertRegex(output, r"push\t(bc|de|hl)")
        self.assertIn('__str0:\t.string\t"foo\\0"', output)

    def test_if(self):
        output = compile("""
            void main(char n) {
                char c = 42;
                if (n==0)
                    c = 24;
            }""")
        # Spill c = 42 before if statement
        self.assertRegex(output, r"ld\t., 42\n[^\n]*\n\tld\t\(ix - 1\), .")
        # Test conditional jump
        self.assertIn("\tld\ta, (ix + 5)\n\tcp\t0\n\tjr\tnz, main_l1", output)
        # Spill c = 24 at end of if-statement
        self.assertRegex(output, r"ld\t., 24\n[^\n]*\n\tld\t\(ix - 1\), .")

    def test_while(self):
        output = compile("""char main() {
                              char a=0;
                              while (a<5) {
                                  a = a + 1;
                              }
                          }
                            """)
        # Test spill before first label
        self.assertRegex(output, r"\tld\t\(ix \- 1\), .\nmain_l1:")
        # Test conditional jump to skip label
        self.assertRegex(output, r"\tjr\t., main_l2")
        # jump to loop label
        self.assertRegex(output, r"\tjp\tmain_l1\n")

    def test_function_preamble_postamble(self):
        output = compile("""char main() {
                              char a=0;
                          }
                            """)
        # ; Let IX be frame-pointer
        # push    IX
        # ld      IX, 0
        # add     IX, SP
        self.assertRegex(output, r"""push[ \t]+IX\n[ \t]+ld[ \t]+IX, 0\n[ \t]add[ \t]+IX, SP""")
        # ; Reserve space for local variables
        # ld      HL, 0ffffh
        # add     HL, SP
        # ld      SP, HL
        self.assertRegex(output, r"ld[ \t]+HL, 0ffffh\n[ \t]+add[ \t]+HL, SP\n[ \t]ld[ \t]+SP, HL")
        self.assertRegex(output, r"ld[ \t]+HL, 0ffffh\n[ \t]+add[ \t]+HL, SP\n[ \t]ld[ \t]+SP, HL")
        # ;Restore stack pointer (free local variables)
        # ld      SP, IX
        self.assertRegex(output, r"ld[ \t]+SP, IX")
        # ;Restore previous frame pointer IX and return
        # pop     IX
        # ret
        self.assertRegex(output, r"pop\tIX\n\tret")

    def test_localVariableWithTypeDef(self):
        output = compile("""
            typedef char MyChar;
            char main() {
                MyChar FOO;
                FOO=1;
            }""")
        self.assertRegex(output, r"ld\t., 1")
        self.assertRegex(output, r"ld\t\(ix \- 1\), .")

    def test_struct_fieldReference(self):
        output = compile("""
            struct myStruct { char a; };
            char main() {
                char a;
                struct myStruct s;
                s.a = 1;
                a = s.a;
            }""")

    def test_pointerWithCast(self):
        output = compile("""
            char main() {
                char* p;
                p = (char*)0x8000;
            }""")
        self.assertRegex(output, r"ld\t(bc|de|hl), 32768")

    def test_castToVoidPtr(self):
        output = compile("""
            char main() {
                int i;
                void* p;
                p = (void*)i;
            }""")
        print(output)
        self.assertRegex(output, r"ld\t(b|d|h), \(ix - 1\)")
        self.assertRegex(output, r"ld\t(c|e|l), \(ix - 2\)")
        self.assertRegex(output, r"ld\t\(ix - 3\), (b|d|h)")
        self.assertRegex(output, r"ld\t\(ix - 4\), (c|e|l)")


