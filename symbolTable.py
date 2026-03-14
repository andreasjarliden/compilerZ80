from symEntry import SymEntry
from address import Temporary

# Stack of symbol tables
ENV = [ {} ]

# TODO create real SymbolTable class
def addSymbol(t, completeType, name):
    entry = SymEntry(t, completeType, name)
    ENV[-1][name] = entry
    return entry
def addSymbolEntry(name, entry):
    ENV[-1][name] = entry
def currentSymbolTable():
    return ENV[-1]
def addTemporary(t, completeType):
    temp = Temporary(t)
    return addSymbol(t, completeType, temp.name)
def pushFrame():
    ENV.append({})
def popFrame():
    ENV.pop()
def lookup(name):
    for frame in reversed(ENV):
        try:
            return frame[name]
        except KeyError:
            pass
    return None

FUNCTION = None
FUNCTION_LABELS = 0
def enterFunction(name):
    global FUNCTION
    global FUNCTION_LABELS
    pushFrame()
    FUNCTION = name
    FUNCTION_LABELS = 0
def exitFunction():
    global FUNCTION
    popFrame()
    FUNCTION = None
def createLabel():
    global FUNCTION
    global FUNCTION_LABELS
    FUNCTION_LABELS += 1
    return f"{FUNCTION}_l{FUNCTION_LABELS}"
