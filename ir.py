from address import Constant, Temporary, Symbol

asmFile = open("a.asm", "w")

IR = []
IR_FUNCTIONS = []

# Stack of symbol tables
ENV = [ {} ]

class SymEntry:
    def __init__(self, name):
        self._name = name
        self.impl = None

    def __repr__(self):
        return f"SymEntry {self._name} {self.impl}"

def addSymbol(name):
    entry = SymEntry(name)
    ENV[-1][name] = entry
    return entry
def pushSymbolTable():
    ENV.append({})
def popSymbolTable():
    ENV.pop()
def currentSymbolTable():
    return ENV[-1]

class StackVariable:
    def __init__(self, offset):
        self._offset = offset

    def __repr__(self):
        return f"Stack Variable offset {self._offset}"

    def codeArg(self):
        # Use ix - 1, as "ix-1" is interpreted as identifier "ix-1"
        if self._offset >= 0:
            return f"(ix + {self._offset})"
        else:
            return f"(ix - {-self._offset})"

def createTemporary():
    t = Temporary()
    addSymbol(t._name)
    return t

class IRDefFun:
    def __init__(self, function, symbolTable):
        self._function = function
        self._symbolTable = symbolTable
        IR_FUNCTIONS.append(self)

    def __repr__(self):
        return f"IRDefFun symbolTable {self._symbolTable}"

    def genCode(self):
        asmFile.write(self._function._name + ":\n");
        # Let IX be frame-pointer
        asmFile.write('\t; Let IX be frame-pointer\n')
        asmFile.write('\tpush\tIX\n')
        asmFile.write('\tld\tIX, 0\n')
        asmFile.write('\tadd\tIX, SP\n')

        # Reserve space for local variables
        localSize = len(self._symbolTable)
        if localSize > 0:
            negSize=65536-localSize
            negHexSize=f'{negSize:05x}h'
            asmFile.write('\t; Reserve space for local variables\n')
            asmFile.write(f'\tld\tHL, {negHexSize}\n')
            asmFile.write(f'\tadd\tHL, SP\n')
            asmFile.write(f'\tld\tSP, HL\n')

        asmFile.write('\t; Function content\n')

class IRFunExit:
    def __init__(self, symbolTable):
        self._symbolTable = symbolTable

    def __repr__(self):
        return f"IRFunExit symbolTable {self._symbolTable}"

    def genCode(self):
        if len(self._symbolTable) > 0:
            asmFile.write('\t;Restore stack pointer (free local variables)\n')
            asmFile.write(f'\tld\tSP, IX\n')
        asmFile.write('\t;Restore previous frame pointer IX and return\n')
        asmFile.write(f'\tpop\tIX\n')
        asmFile.write(f'\tret\n\n')


class IRReturn:
    def __init__(self, exprAddr):
        self._exprAddr = exprAddr

    def __repr__(self):
        return "IRReturn " + str(self._exprAddr)

    def genCode(self):
        # TODO should also add jump to return
        if isinstance(self._exprAddr.impl, StackVariable):
            asmFile.write(f'\tld\ta, {self._exprAddr.impl.codeArg()}\n')
        elif isinstance(self._exprAddr, Constant):
            asmFile.write(f'\tld\ta, {self._exprAddr.value}\n')
        else:
            error()
        

class IRFunCall:
    def __init__(self, name):
        self._addr = createTemporary()
        self._name = name

    def __repr__(self):
        return "IRFunCall " + self._name

    def genCode(self):
        asmFile.write(f'\tcall\t{self._name}\n')
        # TODO store result

class IRAssign:
    def __init__(self, symEntry, rhsAddress):
        self._symEntry = symEntry
        self._rhsAddress = rhsAddress

    def __repr__(self):
        return f"IRAssign {self._symEntry} = {self._rhsAddress}"

    def genCode(self):
        if isinstance(self._symEntry.impl, StackVariable):
            lhs = self._symEntry.impl.codeArg()
        else:
            error()
        if isinstance(self._rhsAddress, Constant):
            value = self._rhsAddress._value
            asmFile.write(f'\tld\t{lhs}, {value}\n')
        elif isinstance(self._rhsAddress.impl, StackVariable):
            asmFile.write(f'\tld\ta, {self._rhsAddress.impl.codeArg()}\n')
            asmFile.write(f'\tld\t{lhs}, a\n')
        else:
            error()

class IRAdd:
    def __init__(self, addrLhs, addrRhs):
        t = createTemporary()
        self._addr = currentSymbolTable()[t._name]
        self._lhsAddr = addrLhs
        self._rhsAddr = addrRhs

    def __repr__(self):
        return f"IRAdd {self._addr} = {self._lhsAddr} + {self._rhsAddr}"

    def genCode(self):
        if isinstance(self._lhsAddr.impl, StackVariable):
            lhs = self._lhsAddr.impl.codeArg()
            asmFile.write(f'\tld\ta, {lhs}\n')
        else:
            error()
        if isinstance(self._rhsAddr, Constant):
            asmFile.write(f'\tadd\ta, {self._rhsAddr._value}\n')
        elif isinstance(self._rhsAddr.impl, StackVariable):
            asmFile.write(f'\tadd\ta, {self._rhsAddr.impl.codeArg()}\n')
        else:
            error()
        asmFile.write(f'\tld\t{self._addr.impl.codeArg()}, a\n')
