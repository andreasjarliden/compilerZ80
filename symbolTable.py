from symEntry import SymEntry
from address import Temporary

# Stack of symbol tables
ENV = [ {} ]
FUNCTION = None
FUNCTION_LABELS = 0

# TODO create real SymbolTable class
def addSymbol(t, completeType, name):
    entry = SymEntry(t, completeType, name)
    ENV[-1][name] = entry
    return entry
def addSymbolEntry(name, entry):
    ENV[-1][name] = entry
def enterFunction(name):
    global FUNCTION
    global FUNCTION_LABELS
    ENV.append({})
    FUNCTION = name
    FUNCTION_LABELS = 0
def exitFunction():
    global FUNCTION
    ENV.pop()
    FUNCTION = None
def currentSymbolTable():
    return ENV[-1]
def addTemporary(t, completeType):
    temp = Temporary(t)
    return addSymbol(t, completeType, temp.name)
def createLabel():
    global FUNCTION
    global FUNCTION_LABELS
    FUNCTION_LABELS += 1
    return f"{FUNCTION}_l{FUNCTION_LABELS}"
