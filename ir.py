from address import *
from symEntry import *
import registerAllocator

asmFile = open("a.asm", "w")

IR_FUNCTIONS = []

class DereferencedPointer:
    def __init__(self, t, address):
        self.type = t
        self.address = address

    def __repr__(self):
        return f"DereferencedPointer @{self.address}"

# Size of all local stack variables
def stackFrameSize(symbolTable):
    smallestOffset = 0
    print(symbolTable)
    for s in symbolTable.values():
        smallestOffset = min(s.impl.offset, smallestOffset)
    return -smallestOffset


class IR:
    def __init__(self, resultAddr=None, lhsAddr=None, rhsAddr=None):
        self.resultAddr=resultAddr
        self.lhsAddr=lhsAddr
        self.rhsAddr=rhsAddr

    @property
    def exprAddr(self):
        return self.lhsAddr

    def updateLive(self, symbolTable):
        if self.resultAddr and isinstance(self.resultAddr, SymEntry):
            # 1
            symEntry = symbolTable[self.resultAddr.name]
            self.resultNextUse = symEntry.nextUse
            self.resultLive = symEntry.live
            # 2
            symbolTable[self.resultAddr.name].live = False
            symbolTable[self.resultAddr.name].nextUse = None
        if self.lhsAddr and isinstance(self.lhsAddr, SymEntry):
            symEntry = symbolTable[self.lhsAddr.name]
            self.lhsNextUse = symEntry.nextUse
            self.lhsLive = symEntry.live
            # 3
            symbolTable[self.lhsAddr.name].live = True
        if self.rhsAddr and isinstance(self.rhsAddr, SymEntry):
            symEntry = symbolTable[self.rhsAddr.name]
            self.rhsNextUse = symEntry.nextUse
            self.rhsLive = symEntry.live
            # 3
            symbolTable[self.rhsAddr.name].live = True
            symbolTable[self.rhsAddr.name].nextUse = self
            symbolTable[self.rhsAddr.name].nextUse = self

    def liveStr(self):
        if self.resultAddr and isinstance(self.resultAddr, SymEntry):
            s1 = "L" if self.resultLive else "D"
        else:
            s1="?"
        if self.lhsAddr and isinstance(self.lhsAddr, SymEntry):
            s2 = "L" if self.lhsLive else "D"
        else:
            s2="?"
        if self.rhsAddr and isinstance(self.rhsAddr, SymEntry):
            s3 = "L" if self.rhsLive else "D"
        else:
            s3="?"
        return s1 + s2 + s3 + " "

    def nextUseStr(self):
        if self.resultAddr and isinstance(self.resultAddr, SymEntry):
            s1 = "U" if self.resultNextUse else "D"
        else:
            s1="?"
        if self.lhsAddr and isinstance(self.lhsAddr, SymEntry):
            s2 = "U" if self.lhsNextUse else "D"
        else:
            s2="?"
        if self.rhsAddr and isinstance(self.rhsAddr, SymEntry):
            s3 = "U" if self.rhsNextUse else "D"
        else:
            s3="?"
        return s1 + s2 + s3 + " "

    def extraDescription(self):
        return ""

    def __repr__(self):
        live = self.liveStr()
        nextUse = self.nextUseStr()
        name = self.__class__.__name__
        r = ""
        if self.resultAddr:
            r = str(self.resultAddr) + " = "
        o1 = ""
        if self.lhsAddr:
            o1 = str(self.lhsAddr) 
        o2 = ""
        if self.rhsAddr:
            o2 = " OP " + str(self.rhsAddr) 
        xtra = self.extraDescription()
        return "".join([live, nextUse, name,r,o1,o2,xtra])

    def load8bitLhsAndRhs(self, transitive=False):
        ra = registerAllocator.RA

        if transitive:
            # if the rhs is already in register a, then swap them
            if isinstance(self.rhsAddr, SymEntry) and ra.isInRegister(self.rhsAddr.name) == "a":
                self.lhsAddr, self.rhsAddr = self.rhsAddr, self.lhsAddr
                self.lhsNextUse, self.rhsNextUse = self.rhsNextUse, self.lhsNextUse

        ra.loadInA(self.lhsAddr)

        if isinstance(self.rhsAddr, Constant):
            return self.rhsAddr.value
        elif ra.isInRegister(self.rhsAddr.name) or self.rhsNextUse:
            regZ = ra.getRegisterForArg(self.rhsAddr.name, { "b", "c", "d", "e", "h", "l" })
            if self.rhsAddr.name not in ra.registers[regZ]:
                asmFile.write(f'\tld\t{regZ}, {self.rhsAddr.impl.codeArg()}\n')
                ra.loadNameInRegister(self.rhsAddr.name, regZ)
            return regZ
        else:
            return self.rhsAddr.impl.codeArg()


class IRDefFun(IR):
    def __init__(self, function, symbolTable):
        super().__init__()
        self.function = function
        self.symbolTable = symbolTable
        IR_FUNCTIONS.append(self)

    def extraDescription(self):
        return f"{self.function} symbolTable {self.symbolTable}"

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

class IRFunExit(IR):
    def __init__(self, function, symbolTable):
        super().__init__()
        self.function = function
        self.symbolTable = symbolTable

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

class IRIf(IR):
    def __init__(self, exprAddr, skipLabel):
        super().__init__(lhsAddr=exprAddr)
        self.skipLabel = skipLabel

    def extraDescription(self):
        return f"{self.skipLabel}"

    def genCode(self):
        if isinstance(self.exprAddr, Flags):
            asmFile.write(f'\tjr\tnz, {self.skipLabel}\n') 
        else:
            if isinstance(self.exprAddr, Constant):
                asmFile.write(f'\tld\ta, {self.exprAddr.value}\n')
            else:
                ra = registerAllocator.RA
                ra.loadInA(self.lhsAddr)
            asmFile.write(f'\tor\ta\n')
            asmFile.write(f'\tjr\tz, {self.skipLabel}\n') 

class IRLabel(IR):
    def __init__(self, label):
        super().__init__()
        self.label = label

    def extraDescription(self):
        return f"{self.label}"

    def genCode(self):
        asmFile.write(self.label + ":\n")

class IRReturn(IR):
    def __init__(self, t, exprAddr):
        super().__init__(lhsAddr=exprAddr)
        self.type = t

    def extraDescription(self):
        return f"type {self.type}"

    def genCode(self):
        if self.type == "char":
            if isinstance(self.exprAddr, Constant):
                asmFile.write(f'\tld\ta, {self.exprAddr.value}\n')
            else:
                ra = registerAllocator.RA
                regX = ra.isInRegister(self.lhsAddr.name)
                if regX == "a":
                    return
                elif regX:
                    asmFile.write(f'\tld\ta, {regX}\n')
                else:
                    asmFile.write(f'\tld\ta, {self.lhsAddr.impl.codeArg()}\n')
        elif self.type =="int":
            if isinstance(self.exprAddr, Constant):
                asmFile.write(f'\tld\thl, {self.exprAddr.value}\n')
            elif isinstance(self.exprAddr.impl, StackVariable):
                asmFile.write(f'\tld\th, {self.exprAddr.impl.codeArg(+1)}\n')
                asmFile.write(f'\tld\tl, {self.exprAddr.impl.codeArg()}\n')
            else:
                error()
        asmFile.write(f'\tjr\t{IR_FUNCTION}_exit\n')

class IRArgument(IR):
    def __init__(self, exprAddr):
        super().__init__(lhsAddr=exprAddr)

    def genCode(self):
        if self.exprAddr.type == "char":
            if isinstance(self.exprAddr, Constant):
                asmFile.write(f'\tld\ta, {self.exprAddr.value}\n')
                asmFile.write(f'\tpush\taf\n')
            else:
                ra = registerAllocator.RA
                # If in the high byte of a register pair, push it directly
                regX = ra.isInRegister(self.lhsAddr.name, {'a', 'b', 'd', 'h'})
                if regX:
                    if regX == "a":
                        asmFile.write("\tpush\taf\n")
                    elif regX == "b":
                        asmFile.write("\tpush\tbc\n")
                    elif regX == "d":
                        asmFile.write("\tpush\tde\n")
                    elif regX == "h":
                        asmFile.write("\tpush\thl\n")
                    return
                # If in the low byte of a register pair, transfer it to a
                ra.getRegisterForArg(self.lhsAddr.name, {'a'})
                regX = ra.isInRegister(self.lhsAddr.name, {'c', 'e', 'l' })
                if regX:
                    asmFile.write(f'\tld\ta, {regX}\n')
                else:
                    asmFile.write(f'\tld\ta, {self.exprAddr.impl.codeArg()}\n')
                asmFile.write(f'\tpush\taf\n')
        elif self.exprAddr.type == "int":
            if isinstance(self.exprAddr, Constant):
                asmFile.write(f'\tld\thl, {self.exprAddr.value}\n')
            elif isinstance(self.exprAddr.impl, StackVariable):
                asmFile.write(f'\tld\th, {self.exprAddr.impl.codeArg(+1)}\n')
                asmFile.write(f'\tld\tl, {self.exprAddr.impl.codeArg()}\n')
            else:
                error()
            asmFile.write(f'\tpush\thl\n')
        else:
            error()


class IRFunCall(IR):
    # addr=None creates a procedure call which ignores the return value
    def __init__(self, t, name, numArgs, addr=None):
        super().__init__(resultAddr=addr)
        self.type = t
        self.name = name
        self.numArgs = numArgs

    def extraDescription(self):
        return self.name

    def genCode(self):
        asmFile.write(f'\tcall\t{self.name}\n')
        for i in range(self.numArgs):
            asmFile.write('\tpop\tbc\n') # Use a register we don't care about (yet)
        # if self.numArgs > 0:
            # asmFile.write(f'\tld\thl, {2*self.numArgs}\n')
            # asmFile.write(f'\tadd\thl, sp\n')
            # asmFile.write(f'\tld\tsp, hl\n')
        if self.resultAddr:
            if self.type == "char":
                ra = registerAllocator.RA
                ra.copyFromRegisterToName("a", self.resultAddr.name)
            elif self.type == "int":
                asmFile.write(f'\tld\t{self.resultAddr.impl.codeArg(+1)}, h\n')
                asmFile.write(f'\tld\t{self.resultAddr.impl.codeArg()}, l\n')
            else:
                error()

class IRAddressOf(IR):
    def __init__(self, symEntry, resAddr):
        super().__init__(resultAddr=resAddr, lhsAddr=symEntry)

    def genCode(self):
        if isinstance(self.exprAddr.impl, StackVariable):
            # Compute pointer based on ix and offset
            offset = self.exprAddr.impl.offset
            negOffset = 65536+offset
            negHexOffset = f'{negOffset:05x}h'
            # TODO maybe better to use IY instead of HL?
            # TODO Optimize for small values with INC
            asmFile.write(f'\tpush\tix\n')
            asmFile.write(f'\tpop\thl\n')
            asmFile.write(f'\tld\tde, {negHexOffset}\n')
            asmFile.write(f'\tadd\thl, de\n')
            # Store the pointer
            lhs_low = self.resultAddr.impl.codeArg()
            lhs_high = self.resultAddr.impl.codeArg(+1)
            asmFile.write(f'\tld\t{lhs_high}, h\n')
            asmFile.write(f'\tld\t{lhs_low}, l\n')
        else:
            error()

class IRAssign(IR):
    def __init__(self, lvalue, rhsAddress):
        super().__init__(resultAddr=lvalue, lhsAddr=rhsAddress)

    def genCode(self):
        ra = registerAllocator.RA
        print("Before IRAssign")
        print(str(ra))
        regY = ra.getRegisterForArg(self.lhsAddr.name, { "a", "b", "c", "d", "e", "h", "l" })
        if self.lhsAddr.name not in ra.registers[regY]:
            # We know it must be loaded from memory. Otherwise we would have gotten a register directly.
            asmFile.write(f'\tld\t{regY}, {self.lhsAddr.impl.codeArg()}\n')
            ra.loadNameInRegister(self.lhsAddr.name, regY)
        ra.copyFromRegisterToName(regY, self.resultAddr.name)
        print("After IRAssign")
        print(str(ra))

        # print(f"IRAssign::genCode resultAddress {self.resultAddr} exprAddr {self.exprAddr}")
        # if self.resultAddr.type == "char":
        #     # Prepare lvalue
        #     if isinstance(self.resultAddr, DereferencedPointer):
        #         impl = self.resultAddr.address.impl
        #         if not isinstance(impl, StackVariable):
        #             error()
        #         # Load the pointer into hl
        #         asmFile.write(f'\tld\th, {impl.codeArg(+1)}\n')
        #         asmFile.write(f'\tld\tl, {impl.codeArg()}\n')
        #         lhs = "(hl)"
        #     elif isinstance(self.resultAddr.impl, StackVariable):
        #         lhs = self.resultAddr.impl.codeArg()
        #     else:
        #         error()
        #
        #     # Assign
        #     if isinstance(self.exprAddr, Constant):
        #         value = self.exprAddr.value
        #         asmFile.write(f'\tld\t{lhs}, {value}\n')
        #     elif isinstance(self.exprAddr.impl, StackVariable):
        #         asmFile.write(f'\tld\ta, {self.exprAddr.impl.codeArg()}\n')
        #         asmFile.write(f'\tld\t{lhs}, a\n')
        #     else:
        #         error()
        # elif self.resultAddr.type == "int":
        #     # Prepare lvalue
        #     if isinstance(self.resultAddr, DereferencedPointer):
        #         impl = self.resultAddr.address.impl
        #         if not isinstance(impl, StackVariable):
        #             error()
        #         # Load the pointer into hl
        #         asmFile.write(f'\tld\th, {impl.codeArg(+1)}\n')
        #         asmFile.write(f'\tld\tl, {impl.codeArg()}\n')
        #         if isinstance(self.exprAddr, Constant):
        #             value = self.exprAddr.value
        #             asmFile.write(f'\tld\t(hl), {value & 0xff}\n')
        #             asmFile.write(f'\tinc\thl\n')
        #             asmFile.write(f'\tld\t(hl), {value >> 8 & 0xff}\n')
        #         elif isinstance(self.exprAddr.impl, StackVariable):
        #             asmFile.write(f'\tld\ta, {self.exprAddr.impl.codeArg()}\n')
        #             asmFile.write(f'\tld\t(hl), a\n')
        #             asmFile.write(f'\tinc\thl\n')
        #             asmFile.write(f'\tld\ta, {self.exprAddr.impl.codeArg(+1)}\n')
        #             asmFile.write(f'\tld\t(hl), a\n')
        #         else:
        #             error()
        #         return
        #     elif isinstance(self.resultAddr.impl, StackVariable):
        #         lhs_low = self.resultAddr.impl.codeArg()
        #         lhs_high = self.resultAddr.impl.codeArg(+1)
        #     else:
        #         error()
        #     if isinstance(self.exprAddr, Constant):
        #         value = self.exprAddr.value
        #         asmFile.write(f'\tld\t{lhs_low}, {value & 0xff}\n')
        #         asmFile.write(f'\tld\t{lhs_high}, {value >> 8 & 0xff}\n')
        #     elif isinstance(self.exprAddr.impl, StackVariable):
        #         asmFile.write(f'\tld\ta, {self.exprAddr.impl.codeArg()}\n')
        #         asmFile.write(f'\tld\t{lhs_low}, a\n')
        #         asmFile.write(f'\tld\ta, {self.exprAddr.impl.codeArg(+1)}\n')
        #         asmFile.write(f'\tld\t{lhs_high}, a\n')
        #     else:
        #         error()


class IRAdd(IR):
    def __init__(self, addr, addrLhs, addrRhs):
        super().__init__(addr, addrLhs, addrRhs)

    def genCode(self):
        ra = registerAllocator.RA
        regZ = self.load8bitLhsAndRhs(transitive=True)
        asmFile.write(f"\tadd\ta, {regZ}\n")
        ra.operationToNameWithRegister(self.resultAddr.name, "a")

        # if self.lhsAddr.type == "char":
        #     if isinstance(self.lhsAddr, Constant):
        #         asmFile.write(f'\tld\ta, {self.lhsAddr.value}\n')
        #     elif isinstance(self.lhsAddr.impl, StackVariable):
        #         lhs = self.lhsAddr.impl.codeArg()
        #         asmFile.write(f'\tld\ta, {lhs}\n')
        #     else:
        #         error()
        #     if isinstance(self.rhsAddr, Constant):
        #         asmFile.write(f'\tadd\ta, {self.rhsAddr.value}\n')
        #     elif isinstance(self.rhsAddr.impl, StackVariable):
        #         asmFile.write(f'\tadd\ta, {self.rhsAddr.impl.codeArg()}\n')
        #     else:
        #         error()
        #     asmFile.write(f'\tld\t{self.resultAddr.impl.codeArg()}, a\n')
        # elif self.lhsAddr.type == "int":
        #     if isinstance(self.lhsAddr.impl, StackVariable):
        #         lhs_hi = self.lhsAddr.impl.codeArg(+1)
        #         lhs_low = self.lhsAddr.impl.codeArg()
        #         asmFile.write(f'\tld\th, {lhs_hi}\n')
        #         asmFile.write(f'\tld\tl, {lhs_low}\n')
        #     else:
        #         error()
        #     if isinstance(self.rhsAddr, Constant):
        #         asmFile.write(f'\tld\tde, {self.rhsAddr.value}\n')
        #         asmFile.write(f'\tadd\thl, de\n')
        #     elif isinstance(self.rhsAddr.impl, StackVariable):
        #         rhs_hi = self.rhsAddr.impl.codeArg(+1)
        #         rhs_low = self.rhsAddr.impl.codeArg()
        #         asmFile.write(f'\tld\td, {rhs_hi}\n')
        #         asmFile.write(f'\tld\te, {rhs_low}\n')
        #         asmFile.write(f'\tadd\thl, de\n')
        #     else:
        #         error()
        #     asmFile.write(f'\tld\t{self.resultAddr.impl.codeArg(+1)}, h\n')
        #     asmFile.write(f'\tld\t{self.resultAddr.impl.codeArg()}, l\n')
        # else:
        #     error()
        #

class IREqual(IR):
    def __init__(self, lhsAddr, rhsAddr):
        super().__init__(lhsAddr=lhsAddr, rhsAddr=rhsAddr)
        self.addr = Flags()

    def genCode(self):
        if self.lhsAddr.type == "char":
            regZ = self.load8bitLhsAndRhs()
            asmFile.write(f"\tcp\t{regZ}\n")
        elif self.lhsAddr.type == "int":
            if isinstance(self.lhsAddr.impl, StackVariable):
                lhs_hi = self.lhsAddr.impl.codeArg(+1)
                lhs_low = self.lhsAddr.impl.codeArg()
                asmFile.write(f'\tld\th, {lhs_hi}\n')
                asmFile.write(f'\tld\tl, {lhs_low}\n')
            else:
                error()
            if isinstance(self.rhsAddr, Constant):
                asmFile.write(f'\tld\tde, {self.rhsAddr.value}\n')
                asmFile.write(f'\tsbc\thl, de\n')
            elif isinstance(self.rhsAddr.impl, StackVariable):
                rhs_hi = self.rhsAddr.impl.codeArg(+1)
                rhs_low = self.rhsAddr.impl.codeArg()
                asmFile.write(f'\tld\th, {rhs_hi}\n')
                asmFile.write(f'\tld\tl, {rhs_low}\n')
                asmFile.write(f'\tsbc\thl, de\n')
            else:
                error()

