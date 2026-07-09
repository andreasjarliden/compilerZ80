from symEntry import SymEntry, GlobalAddress, GlobalLabel
from type_defs import PointerType
# TODO move tyo symEntry?

class Constant:
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

    @property
    def isPointer(self):
        return isinstance(self.completeType, PointerType)

    def __repr__(self):
        return f"Constant {self.completeType} {self.value}"

    # Because it doubles an AST Node
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


class Temporary:
    NUM_TEMPS = 0
    def __init__(self, t):
        self.type = t
        self.name = f"temp{Temporary.NUM_TEMPS}"
        Temporary.NUM_TEMPS+=1

    def __repr__(self):
        return f"Temporary {self.type} {self.name}"
