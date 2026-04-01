from symEntry import SymEntry, GlobalAddress
# TODO move tyo symEntry?

class Constant:
    def __init__(self, completeType, value):
        self.completeType = completeType
        self._value = value

    def __eq__(self, other):
        if not isinstance(other, Constant):
            return NotImplemented
        return self.type == other.type and self.value == other.value

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
        return self.completeType.endswith("*")

    def __repr__(self):
        return f"Constant {self.completeType} {self.value}"

    # Because it doubles an AST Node
    def visit(self, context):
        return self


class StringConstant(Constant):

    def __init__(self, value):
        super().__init__("char*", value)

    # @property
    # def value(self):
    #     return self._name

    def __repr__(self):
        return f"StringConstant {self.completeType} {self.value}"

    def visit(self, context):
        name = context.stringTable.addString(self._value)
        symbol = context.symbolTable.lookUp(name)
        if not symbol:
            symbol = SymEntry("char*", name)
            symbol.impl = GlobalAddress(name)
            context.symbolTable.addSymbolEntry(name, symbol)
            context.dataSegment[symbol] = self._value
        print(f"Adding string {symbol.name} equal to {self._value} in dataSegment")
        return symbol


class Temporary:
    NUM_TEMPS = 0
    def __init__(self, t):
        self.type = t
        self.name = f"temp{Temporary.NUM_TEMPS}"
        Temporary.NUM_TEMPS+=1

    def __repr__(self):
        return f"Temporary {self.type} {self.name}"
