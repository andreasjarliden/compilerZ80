from dataclasses import dataclass

SIZE_FOR_TYPES = { "char": 1,
                   "int": 2 }

class SymEntry:
    def __init__(self, t, n):
        self.completeType = t
        # TODO maybe name should be optional, only used for debugging?
        self.name = n
        self.impl = None

    def __repr__(self):
        return f"<SymEntry {id(self)} {self.completeType} {self.name} {self.impl}>"

    @property
    def type(self):
        if self.completeType.endswith("*"):
            return "int"
        else:
            return self.completeType

    @property
    def size(self):
        return SIZE_FOR_TYPES[self.type]

    def equalByValue(self, other):
        return self.name == other.name and self.completeType == other.completeType

class ValueAddress:
    pass

class StackAddress(ValueAddress):
    def __init__(self, offset):
        self.offset = offset

    def __repr__(self):
        return f"ValueAddress @{self.offset}"

    def codeArg(self, offset=0):
        # Use ix - 1, as "ix-1" is interpreted as identifier "ix-1"
        # TODO this should be resolved by removing - from IDs in the lexer
        if self.offset >= 0:
            return f"(ix + {self.offset+offset})"
        else:
            return f"(ix - {-self.offset-offset})"

class GlobalAddress(ValueAddress):
    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return f"GlobaAddress {self.name}"

    def codeArg(self, offset=0):
        if offset == 0:
            return f"({self.name})"
        else:
            return f"({self.name} + {offset})"

class PointerAddress:
    def __init__(self, p):
        self.pointer = p
        pass

    def __repr__(self):
        return f"PointerAddress {self.pointer}"
