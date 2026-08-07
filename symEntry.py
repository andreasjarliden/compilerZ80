from dataclasses import dataclass
from type_defs import StructType, PointerType, simpleTypeForComplexType
from abc import ABC, abstractmethod
from typing import Any

class Operand(ABC):
    @property
    @abstractmethod
    def type(self) -> Any:
        ...

    @property
    def isPointer(self):
        return isinstance(self.completeType, PointerType)


# Object semantics but with custom equalByValue function
class SymEntry(Operand):
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

    def equalByValue(self, other):
        return self.name == other.name and self.completeType == other.completeType


class CastSymEntry(Operand):
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

    def equalByValue(self, other):
        return self.name == other.name and self.completeType == other.completeType


class Constant(Operand):
    def __init__(self, completeType, value):
        self.completeType = completeType
        self._value = value

    def __eq__(self, other):
        if not isinstance(other, Constant):
            return NotImplemented
        return self.completeType == other.completeType and self.value == other.value

    @property
    def value(self):
        return self._value

    @property
    def type(self):
        if self.isPointer:
            return "int"
        else:
            return self.completeType

    def __repr__(self):
        return f"Constant {self.completeType} {self.value}"

    # Because it doubles an AST Node
    # Maybe that is a bad idea
    def visit(self, context):
        return self


class StringConstant(Constant):

    def __init__(self, value):
        super().__init__(PointerType("char"), value)

    # @property
    # def value(self):
    #     return self._name

    def __repr__(self):
        return f"StringConstant {self.completeType} {self.value}"

    def visit(self, context):
        name = context.stringTable.addString(self._value)
        symbol = context.symbolTable.lookUp(name)
        if not symbol:
            symbol = SymEntry(PointerType("char"), name)
            symbol.impl = GlobalLabel(name)
            context.symbolTable.addSymbolEntry(name, symbol)
            if not symbol in context.dataSegment:
                # context.dataSegment[symbol] = self._value
                context.dataSegment[symbol.name] = (symbol.type, self._value)
        return symbol

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
