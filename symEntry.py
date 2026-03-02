SIZE_FOR_TYPES = { "char": 1,
                   "int": 2 }

class SymEntry:
    def __init__(self, t, completeType, name):
        self.name = name
        self.type = t
        self.completeType = completeType
        self.impl = None
        self.live = None

    def initLive(self):
        self.live = not self.name.startswith("temp")
        self.nextUse = None

    @property
    def size(self):
        return SIZE_FOR_TYPES[self.type]

    def __repr__(self):
        return f"<SymEntry {self.name} {self.type} {self.completeType} {self.impl}>"


class StackVariable:
    def __init__(self, offset):
        self.offset = offset

    def __repr__(self):
        return f"StackVariable @{self.offset}"

    def codeArg(self, offset=0):
        # Use ix - 1, as "ix-1" is interpreted as identifier "ix-1"
        # TODO this should be resolved by removing - from IDs in the lexer
        if self.offset >= 0:
            return f"(ix + {self.offset+offset})"
        else:
            return f"(ix - {-self.offset-offset})"


# TODO rename to e.g. PointerVariable? Or StackAddress, PointerAddress and AbsolutePointerAddress?
class DereferencedPointer:
    def __init__(self):
        pass

    def __repr__(self):
        return f"DereferencedPointer"
