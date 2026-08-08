from address import PointerType, GlobalLabel
from type_defs import simpleTypeForComplexType

class Operand:
    def __init__(self, completeType):
        self.completeType = completeType

    @property
    def type(self):
        return simpleTypeForComplexType(self.completeType)

    @property
    def isPointer(self):
        return isinstance(self.completeType, PointerType)


# Object semantics but with custom equalByValue function
class SymbolOperand(Operand):
    def __init__(self, completeType, n : str):
        super().__init__(completeType)
        # TODO maybe name should be optional, only used for debugging?
        self.name = n
        self.impl : ValueAddress | None = None

    def __repr__(self):
        return f"<SymbolOperand {self.completeType} {self.name} {self.impl}>"

    def equalByValue(self, other):
        return self.name == other.name and self.completeType == other.completeType


class CastSymbolOperand(Operand):
    def __init__(self, s : SymbolOperand, completeType):
        super().__init__(completeType)
        self.symbol = s

    def __repr__(self):
        return f"<CastSymbolOperand {self.completeType} {self.symbol}>"

    @property
    def name(self):
        return self.symbol.name

    @property
    def impl(self):
        return self.symbol.impl

    def equalByValue(self, other):
        return self.name == other.name and self.completeType == other.completeType


class ConstantOperand(Operand):
    def __init__(self, completeType, value):
        super().__init__(completeType)
        self._value = value

    def __eq__(self, other):
        if not isinstance(other, ConstantOperand):
            return NotImplemented
        return self.completeType == other.completeType and self.value == other.value

    @property
    def value(self):
        return self._value

    def __repr__(self):
        return f"ConstantOperand {self.completeType} {self.value}"

    # Because it doubles an AST Node
    # TODO: Maybe that is a bad idea
    def visit(self, context):
        return self


class StringConstantOperand(ConstantOperand):
    def __init__(self, value):
        super().__init__(PointerType("char"), value)

    def __repr__(self):
        return f"StringConstantOperand {self.completeType} {self.value}"

    def visit(self, context):
        name = context.stringTable.addString(self._value)
        symbol = context.symbolTable.lookUp(name)
        if not symbol:
            symbol = SymbolOperand(PointerType("char"), name)
            symbol.impl = GlobalLabel(name)
            context.symbolTable.addSymbolEntry(name, symbol)
            if not symbol in context.dataSegment:
                # context.dataSegment[symbol] = self._value
                context.dataSegment[symbol.name] = (symbol.type, self._value)
        return symbol
