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
            output = compile("""void foo() { return 0;} char main() {
                                    char foo;
                                    foo();
                                    return 0;
                              }""")
        self.assertEqual(ctx.exception.location.line, 3) 
        self.assertEqual(ctx.exception.message, "Attempting to call non-function foo") 




