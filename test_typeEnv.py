import unittest
from typeEnv import *
from type_defs import StructType, StructField

class TestTypeEnv(unittest.TestCase):
    def test_addStruct(self):
        typeEnv = TypeEnv()
        self.assertFalse(typeEnv.lookupStructName("myStruct"))
        typeEnv.addStruct(StructType("myStruct", {}))
        self.assertTrue(typeEnv.lookupStructName("myStruct"))

    def test_scoping(self):
        typeEnv = TypeEnv()
        outerStruct = StructType("myStruct", { "outer": StructField(type="char", name="a", offset=0) })
        innerStruct = StructType("myStruct", { "inner": StructField(type="char", name="a", offset=0) })
        typeEnv.addStruct(outerStruct)
        typeEnv.pushFrame()
        typeEnv.addStruct(innerStruct)
        self.assertEqual(typeEnv.lookupStructName("myStruct"), innerStruct)
        typeEnv.popFrame()
        self.assertEqual(typeEnv.lookupStructName("myStruct"), outerStruct)

    def test_structSize(self):
        typeEnv = TypeEnv()
        s = StructType("myStruct", {"a": StructField(type="char", name="a", offset=0),
                                    "b": StructField(type="int", name="b", offset=1)})
        typeEnv.addStruct(s)
        self.assertEqual(typeEnv.sizeOfType("char"), 1)
        self.assertEqual(typeEnv.sizeOfType("int"), 2)
        self.assertEqual(typeEnv.sizeOfType(StructType("myStruct")), 3)
        s2 = StructType("myStruct2", {"a": StructField(type=StructType("myStruct"), name="a", offset=0),
                                     "b": StructField(type="int", name="b", offset=3)})
        typeEnv.addStruct(s2)
        self.assertEqual(typeEnv.sizeOfType(StructType("myStruct2")), 5)

