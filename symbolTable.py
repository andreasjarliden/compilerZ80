from symEntry import SymEntry, StackAddress

class Temporary:
    NUM_TEMPS = 0
    def __init__(self, t):
        self.type = t
        self.name = f"temp{Temporary.NUM_TEMPS}"
        Temporary.NUM_TEMPS+=1

    def __repr__(self):
        return f"Temporary {self.type} {self.name}"

class SymbolTable:
    def __init__(self) ->None :
        self.env : list[dict[str, SymEntry]] = [{}]
    def addSymbol(self, completeType, name):
        entry = SymEntry(completeType, name)
        self.env[-1][name] = entry
        return entry
    def addSymbolEntry(self, name : str, entry : SymEntry):
        self.env[-1][name] = entry
    # TODO rename
    def currentSymbolTable(self):
        return self.env[-1]
    def addTemporary(self, completeType) -> SymEntry:
        temp = Temporary(completeType)
        return self.addSymbol(completeType, temp.name)
    def pushFrame(self) -> None :
        self.env.append({})
    def popFrame(self) -> None :
        self.env.pop()
    def lookUp(self, name : str) -> SymEntry | None:
        # TODO for preventing looking up StructType which is not hashable. Handle this in a better way.
        if not isinstance(name, str):
            return None
        for frame in reversed(self.env):
            try:
                return frame[name]
            except KeyError:
                pass
        return None
    def allSymbols(self) -> set[SymEntry] :
        symbols : set[SymEntry] = set()
        for frame in self.env:
            symbols.update(frame.values())
        return symbols

    def __repr__(self):
        return f"SymbolTable {self.env}"

# Size of all local stack variables
def stackFrameSize(frame) -> int:
    smallestOffset = 0
    for s in frame.values():
        if isinstance(s.impl, StackAddress):
            smallestOffset = min(s.impl.offset, smallestOffset)
    return -smallestOffset

