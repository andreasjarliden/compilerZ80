from dataclasses import dataclass

SIZE_FOR_TYPES = { "char": 1,
                   "int": 2 }

@dataclass
class SymEntry:
    completeType : str
    name : str

    def __post_init__(self):
        self.impl = None

    @property
    def type(self):
        if self.completeType.startswith("*"):
            return "int"
        else:
            return self.completeType

    @property
    def size(self):
        return SIZE_FOR_TYPES[self.type]

class StackAddress:
    def __init__(self, offset):
        self.offset = offset

    def __repr__(self):
        return f"StackAddress @{self.offset}"

    def codeArg(self, offset=0):
        # Use ix - 1, as "ix-1" is interpreted as identifier "ix-1"
        # TODO this should be resolved by removing - from IDs in the lexer
        if self.offset >= 0:
            return f"(ix + {self.offset+offset})"
        else:
            return f"(ix - {-self.offset-offset})"


class PointerAddress:
    def __init__(self, p):
        self.pointer = p
        pass

    def __repr__(self):
        return f"PointerAddress {self.pointer}"
