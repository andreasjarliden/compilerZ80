import unittest
from testutilities import compile
from error import CompileError

class TestErrorHandling(unittest.TestCase):
    def test_missingFunction(self):
        with self.assertRaises(CompileError) as ctx:
            output = compile("""char main() {
                                foo();
                                return 0;
                              }""")
        self.assertEqual(ctx.exception.location.line, 2) 
        self.assertEqual(ctx.exception.message, "Attempting to call unknown foo") 

    def test_callingNonFunction(self):
        with self.assertRaises(CompileError) as ctx:
            output = compile("""void main() {
                                    char foo;
                                    foo();
                              }""")
        self.assertEqual(ctx.exception.location.line, 3) 
        self.assertEqual(ctx.exception.message, "Attempting to call non-function foo") 

    def test_callingWrongNumberOfArguments(self):
        with self.assertRaises(CompileError) as ctx:
            output = compile("""void foo(char a, char b);
                                void main() {
                                    foo(1);
                              }""")
        self.assertEqual(ctx.exception.location.line, 3) 
        self.assertEqual(ctx.exception.message, "Attempting to call function foo with 1 arguments but expected 2") 




