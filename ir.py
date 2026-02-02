from address import *

asmFile = open("a.asm", "w")

IR = []
IR_FUNCTIONS = []

# Stack of symbol tables
ENV = [ {} ]
FUNCTION = None
FUNCTION_LABELS = 0

class SymEntry:
    def __init__(self, name):
        self.name = name
        self.impl = None

    def __repr__(self):
        return f"<SymEntry {self.name} {self.impl}>"

def addSymbol(name):
    entry = SymEntry(name)
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
def addTemporary():
    t = Temporary()
    return addSymbol(t.name)
def createLabel():
    global FUNCTION
    global FUNCTION_LABELS
    FUNCTION_LABELS += 1
    return f"{FUNCTION}_l{FUNCTION_LABELS}"
def exitLabel():
    global FUNCTION
    return f"{FUNCTION}_exit"


class StackVariable:
    def __init__(self, offset):
        self.offset = offset

    def __repr__(self):
        return f"Stack Variable offset {self.offset}"

    def codeArg(self):
        # Use ix - 1, as "ix-1" is interpreted as identifier "ix-1"
        if self.offset >= 0:
            return f"(ix + {self.offset})"
        else:
            return f"(ix - {-self.offset})"

# Size of all local stack variables
def stackFrameSize(symbolTable):
    smallestOffset = 0
    print(symbolTable)
    for s in symbolTable.values():
        smallestOffset = min(s.impl.offset, smallestOffset)
    return -smallestOffset

class IRDefFun:
    def __init__(self, function, symbolTable):
        self.function = function
        self.symbolTable = symbolTable
        IR_FUNCTIONS.append(self)

    def __repr__(self):
        return f"IRDefFun {self.function} symbolTable {self.symbolTable}"

    def genCode(self):
        global IR_FUNCTION
        IR_FUNCTION=self.function.name
        asmFile.write(self.function.name + ":\n");
        # Let IX be frame-pointer
        asmFile.write('\t; Let IX be frame-pointer\n')
        asmFile.write('\tpush\tIX\n')
        asmFile.write('\tld\tIX, 0\n')
        asmFile.write('\tadd\tIX, SP\n')

        # Reserve space for local variables
        size = stackFrameSize(self.symbolTable)
        if size > 0:
            negSize=65536-size
            negHexSize=f'{negSize:05x}h'
            asmFile.write('\t; Reserve space for local variables\n')
            asmFile.write(f'\tld\tHL, {negHexSize}\n')
            asmFile.write(f'\tadd\tHL, SP\n')
            asmFile.write(f'\tld\tSP, HL\n')

        asmFile.write('\t; Function content\n')

class IRFunExit:
    def __init__(self, function, symbolTable):
        self.function = function
        self.symbolTable = symbolTable

    def __repr__(self):
        return f"IRFunExit symbolTable {self.symbolTable}"

    def genCode(self):
        asmFile.write(f"{self.function.name}_exit:\n")
        global IR_FUNCTION
        IR_FUNCTION=None
        if len(self.symbolTable) > 0:
            asmFile.write('\t;Restore stack pointer (free local variables)\n')
            asmFile.write(f'\tld\tSP, IX\n')
        asmFile.write('\t;Restore previous frame pointer IX and return\n')
        asmFile.write(f'\tpop\tIX\n')
        asmFile.write(f'\tret\n\n')

class IRIf:
    def __init__(self, exprAddr, skipLabel):
        self.exprAddr = exprAddr
        self.skipLabel = skipLabel

    def __repr__(self):
        return f"IRIf {self.exprAddr} {self.skipLabel}"

    def genCode(self):
        # TODO duplication with e.g. IRReturn
        if isinstance(self.exprAddr, Flags):
            asmFile.write(f'\tjr\tnz, {self.skipLabel}\n') 
        else:
            if isinstance(self.exprAddr, Constant):
                asmFile.write(f'\tld\ta, {self.exprAddr.value}\n')
            elif isinstance(self.exprAddr.impl, StackVariable):
                asmFile.write(f'\tld\ta, {self.exprAddr.impl.codeArg()}\n')
            asmFile.write(f'\tor\ta\n')
            asmFile.write(f'\tjr\tz, {self.skipLabel}\n') 

class IRLabel:
    def __init__(self, label):
        self.label = label

    def __repr__(self):
        return f"IRLabel {self.label}"

    def genCode(self):
        asmFile.write(self.label + ":\n")

class IRReturn:
    def __init__(self, exprAddr):
        self.exprAddr = exprAddr

    def __repr__(self):
        return "IRReturn " + str(self.exprAddr)

    def genCode(self):
        if isinstance(self.exprAddr, Constant):
            asmFile.write(f'\tld\ta, {self.exprAddr.value}\n')
        elif isinstance(self.exprAddr.impl, StackVariable):
            asmFile.write(f'\tld\ta, {self.exprAddr.impl.codeArg()}\n')
        else:
            error()
        asmFile.write(f'\tjr\t{IR_FUNCTION}_exit\n')

class IRArgument:
    def __init__(self, exprAddr):
        self.exprAddr = exprAddr

    def __repr__(self):
        return f"IRArgument {self.exprAddr}"

    def genCode(self):
        if isinstance(self.exprAddr, Constant):
            asmFile.write(f'\tld\ta, {self.exprAddr.value}\n')
        elif isinstance(self.exprAddr.impl, StackVariable):
            asmFile.write(f'\tld\ta, {self.exprAddr.impl.codeArg()}\n')
        else:
            error()
        asmFile.write(f'\tpush\taf\n')

class IRFunCall:
    def __init__(self, name, numArgs, ignoreValue=False):
        if ignoreValue:
            self.addr = None
        else:
            self.addr = addTemporary()
        self.name = name
        self.numArgs = numArgs

    def __repr__(self):
        return "IRFunCall " + self.name

    def genCode(self):
        asmFile.write(f'\tcall\t{self.name}\n')
        if self.numArgs > 0:
            asmFile.write(f'\tld\thl, {2*self.numArgs}\n')
            asmFile.write(f'\tadd\thl, sp\n')
            asmFile.write(f'\tld\tsp, hl\n')
        if self.addr:
            asmFile.write(f'\tld\t{self.addr.impl.codeArg()}, a\n')

class IRAssign:
    def __init__(self, symEntry, rhsAddress):
        self.symEntry = symEntry
        self.rhsAddress = rhsAddress

    def __repr__(self):
        return f"IRAssign {self.symEntry} = {self.rhsAddress}"

    def genCode(self):
        if isinstance(self.symEntry.impl, StackVariable):
            lhs = self.symEntry.impl.codeArg()
        else:
            error()
        if isinstance(self.rhsAddress, Constant):
            value = self.rhsAddress.value
            asmFile.write(f'\tld\t{lhs}, {value}\n')
        elif isinstance(self.rhsAddress.impl, StackVariable):
            asmFile.write(f'\tld\ta, {self.rhsAddress.impl.codeArg()}\n')
            asmFile.write(f'\tld\t{lhs}, a\n')
        else:
            error()

class IRAdd:
    def __init__(self, addrLhs, addrRhs):
        self.addr = addTemporary()
        self.lhsAddr = addrLhs
        self.rhsAddr = addrRhs

    def __repr__(self):
        return f"IRAdd {self.addr} = {self.lhsAddr} + {self.rhsAddr}"

    def genCode(self):
        if isinstance(self.lhsAddr.impl, StackVariable):
            lhs = self.lhsAddr.impl.codeArg()
            asmFile.write(f'\tld\ta, {lhs}\n')
        else:
            error()
        if isinstance(self.rhsAddr, Constant):
            asmFile.write(f'\tadd\ta, {self.rhsAddr.value}\n')
        elif isinstance(self.rhsAddr.impl, StackVariable):
            asmFile.write(f'\tadd\ta, {self.rhsAddr.impl.codeArg()}\n')
        else:
            error()
        asmFile.write(f'\tld\t{self.addr.impl.codeArg()}, a\n')

class IREqual:
    def __init__(self, addrLhs, addrRhs):
        self.addr = Flags()
        self.lhsAddr = addrLhs
        self.rhsAddr = addrRhs

    def __repr__(self):
        return f"IREqual {self.addr} = {self.lhsAddr} == {self.rhsAddr}"

    def genCode(self):
        if isinstance(self.lhsAddr.impl, StackVariable):
            lhs = self.lhsAddr.impl.codeArg()
            asmFile.write(f'\tld\ta, {lhs}\n')
        else:
            error()
        if isinstance(self.rhsAddr, Constant):
            asmFile.write(f'\tcp\t{self.rhsAddr.value}\n')
        elif isinstance(self.rhsAddr.impl, StackVariable):
            asmFile.write(f'\tcp\t{self.rhsAddr.impl.codeArg()}\n')
        else:
            error()
