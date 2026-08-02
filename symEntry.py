from dataclasses import dataclass
from type_defs import StructType, PointerType, simpleTypeForComplexType


# Object semantics but with custom equalByValue function
class SymEntry:
    def __init__(self, t, n : str):
        self.completeType = t
        # TODO maybe name should be optional, only used for debugging?
        self.name = n
        self.impl : ValueAddress | None = None

    def __repr__(self):
        return f"<SymEntry {self.completeType} {self.name} {self.impl}>"

    @property
    def type(self):
        return simpleTypeForComplexType(self.completeType)

    @property
    def isPointer(self):
        return isinstance(self.completeType, PointerType)

    def equalByValue(self, other):
        return self.name == other.name and self.completeType == other.completeType


class CastSymEntry:
    def __init__(self, s : SymEntry, completeType):
        self.symEntry = s
        self.completeType = completeType

    def __repr__(self):
        return f"<CastSymEntry {self.completeType} {self.symEntry}>"

    @property
    def name(self):
        return self.symEntry.name

    @property
    def impl(self):
        return self.symEntry.impl

    @property
    def type(self):
        return simpleTypeForComplexType(self.completeType)

    @property
    def isPointer(self):
        # TODO create real pointer type
        if isinstance(self.completeType, StructType):
            return False
        else:
            return isinstance(self.completeType, PointerType)

    def equalByValue(self, other):
        return self.name == other.name and self.completeType == other.completeType


class ValueAddress:
    pass

@dataclass
class StackAddress(ValueAddress):
    offset : int

    # def __init__(self, offset):
    #     self.offset = offset
    #
    # def __repr__(self):
    #     return f"StackAddress @{self.offset}"

    def codeArg(self, offset=0):
        # Use ix - 1, as "ix-1" is interpreted as identifier "ix-1"
        # TODO this should be resolved by removing - from IDs in the lexer
        if self.offset >= 0:
            return f"(ix + {self.offset+offset})"
        else:
            return f"(ix - {-self.offset-offset})"

    def cloneWithOffset(self, offset):
        return StackAddress(self.offset + offset)

class GlobalAddress(ValueAddress):
    def __init__(self, name, offset=0):
        self.name = name
        self.offset = offset

    def __eq__(self, other):
        if not isinstance(other, GlobalAddress):
            return NotImplemented
        return self.name == other.name and self.offset == other.offset

    def __repr__(self):
        if self.offset:
            return f"GlobaAddress {self.name} offset {self.offset}"
        else:
            return f"GlobaAddress {self.name}"

    def codeArg(self, offset=0):
        o = self.offset + offset
        if o== 0:
            return f"({self.name})"
        else:
            return f"({self.name} + {o})"

    def pointerArg(self):
        if self.offset:
            return f"{self.name}+{self.offset}"
        else:
            return f"{self.name}"

    def cloneWithOffset(self, offset):
        return GlobalAddress(self.name, self.offset + offset)


class PointerAddress(ValueAddress):
    def __init__(self, p : ValueAddress):
        self.pointer = p
        pass

    def __repr__(self):
        return f"PointerAddress {self.pointer}"


# TODO what is the class? Is it really a ValueAddress?  Is it the value of the
# label and not what is stored at the label?
class GlobalLabel(ValueAddress):
    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return f"GlobaLabel {self.name}"

    def codeArg(self):
        return f"{self.name}"


class TypeAddress:
    def __init__(self, completeType):
        self.completeType = completeType
