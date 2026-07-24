from type_defs import StructType, PointerType

SIZE_FOR_TYPES = { "char": 1,
                   "int": 2 }

class TypeEnv:
    def __init__(self):
        self.structEnv = [{}]

    def __repr__(self):
        return f"TypeEnv structEnv={self.structEnv}"

    def sizeOfType(self, t):
        if isinstance(t, StructType):
            sum = 0
            s = self.lookupStructName(t.name)
            for field in s.fields.values():
                sum += self.sizeOfType(field.type)
            return sum
        if isinstance(t, PointerType):
            return self.sizeOfType("int")
        return SIZE_FOR_TYPES[t]

    def addStruct(self, s : StructType):
        self.structEnv[-1][s.name] = s

    def lookupStructName(self, name):
        for frame in reversed(self.structEnv):
            try:
                return frame[name]
            except KeyError:
                pass
        return None

    def pushFrame(self):
        self.structEnv.append({})

    def popFrame(self):
        self.structEnv.pop()
