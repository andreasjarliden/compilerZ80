from symEntry import SymEntry
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
    def lookup(self, name):
        for frame in reversed(self.env):
            try:
                return frame[name]
            except KeyError:
                pass
        return None
    def __repr__(self):
        return f"SymbolTable {id(self)=} {self.env}"
