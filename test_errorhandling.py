import unittest
from testutilities import compile
from error import CompileError

class TestIntegration(unittest.TestCase):

    def test_error_missingFunction(self):
        with self.assertRaises(CompileError) as ctx:
            output = compile("""char main() {
                                foo();
                                return 0;
                              }""")
        self.assertEqual(ctx.exception.location.line, 2) 
        self.assertEqual(ctx.exception.message, "Error in function call") 



