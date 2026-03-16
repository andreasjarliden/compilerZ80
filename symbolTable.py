from symEntry import SymEntry
from address import Temporary

class SymbolTable:
    def __init__(self):
        self.env = [{}]
    def addSymbol(self, t, completeType, name):
        entry = SymEntry(t, completeType, name)
        self.env[-1][name] = entry
        return entry
    def addSymbolEntry(self, name, entry):
        self.env[-1][name] = entry
    # TODO rename
    def currentSymbolTable(self):
        return self.env[-1]
    def addTemporary(self, t, completeType):
        temp = Temporary(t)
        return self.addSymbol(t, completeType, temp.name)
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

FUNCTION = None
FUNCTION_LABELS = 0
def createLabel():
    global FUNCTION
    global FUNCTION_LABELS
    FUNCTION_LABELS += 1
    return f"{FUNCTION}_l{FUNCTION_LABELS}"
