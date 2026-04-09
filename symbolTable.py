from symEntry import SymEntry, StackAddress
from address import Temporary

class SymbolTable:
    def __init__(self):
        self.env = [{}]
    def addSymbol(self, completeType, name):
        entry = SymEntry(completeType, name)
        self.env[-1][name] = entry
        return entry
    def addSymbolEntry(self, name, entry):
        self.env[-1][name] = entry
    # TODO rename
    def currentSymbolTable(self):
        return self.env[-1]
    def addTemporary(self, completeType):
        temp = Temporary(completeType)
        return self.addSymbol(completeType, temp.name)
    def pushFrame(self, ):
        self.env.append({})
    def popFrame(self, ):
        self.env.pop()
    def lookUp(self, name):
        for frame in reversed(self.env):
            try:
                return frame[name]
            except KeyError:
                pass
        return None
    def allSymbols(self):
        symbols = set()
        for frame in self.env:
            symbols.update(frame.values())
        return symbols

    def __repr__(self):
        return f"SymbolTable {self.env}"

# Size of all local stack variables
def stackFrameSize(frame):
    smallestOffset = 0
    for s in frame.values():
        print(f"stackFrameSize checking {s=}")
        if isinstance(s.impl, StackAddress):
            print(f"stackFrameSize checking {s.impl.offset=} {smallestOffset=}")
            smallestOffset = min(s.impl.offset, smallestOffset)
            print(f"stackFrameSize {smallestOffset=}")
    return -smallestOffset

