from address import *
from symEntry import *
import registerAllocator
from asmWriter import *

# Size of all local stack variables
def stackFrameSize(symbolTable):
    smallestOffset = 0
    for s in symbolTable.values():
        if isinstance(s.impl, ValueAddress):
            smallestOffset = min(s.impl.offset, smallestOffset)
    return -smallestOffset


# members:
# - live[symbol] = bool, whether symbol is live _at_ this instruction.
class IR:
    def __init__(self, resultAddr=None, lhsAddr=None, rhsAddr=None):
        self.resultAddr=resultAddr
        self.lhsAddr=lhsAddr
        self.rhsAddr=rhsAddr
        self.live = {}

    @property
    def exprAddr(self):
        return self.lhsAddr

    def updateLive(self, live):
        if self.resultAddr and isinstance(self.resultAddr, SymEntry):
            live[self.resultAddr] = False
        if self.lhsAddr and isinstance(self.lhsAddr, SymEntry):
            live[self.lhsAddr] = True
        if self.rhsAddr and isinstance(self.rhsAddr, SymEntry):
            live[self.rhsAddr] = True
        self.live = live.copy()

    def liveStr(self):
        if not self.live:
            return ""
        if self.resultAddr and isinstance(self.resultAddr, SymEntry):
            s1 = "L" if self.live[self.resultAddr] else "D"
        else:
            s1="?"
        if self.lhsAddr and isinstance(self.lhsAddr, SymEntry):
            s2 = "L" if self.live[self.lhsAddr] else "D"
        else:
            s2="?"
        if self.rhsAddr and isinstance(self.rhsAddr, SymEntry):
            s3 = "L" if self.live[self.rhsAddr] else "D"
        else:
            s3="?"
        return s1 + s2 + s3 + " "

    def extraDescription(self):
        return ""

    def __repr__(self):
        live = self.liveStr()
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
        return "".join([live, name,r,o1,o2,xtra, str(self.live)])

    # Similar to doLoadInRegister8 but only prepares the rhs for an assembler
    # instruction. Not loading to a register.
    # TODO: Move to registerAllocator?
    def loadRhs8(self, rhsAddr, asmWriter):
        ra = registerAllocator.RA
        if isinstance(rhsAddr, Constant):
            return rhsAddr.value
        elif isinstance(rhsAddr.impl, PointerAddress):
            # Must have the pointer in hl (or ix/iy). bc & de not supported by Z80
            regZ = ra.isInRegister(rhsAddr.impl.pointer, { "hl" })
            # Already in hl?
            if not regZ:
                otherReg = ra.isInRegister(rhsAddr.impl.pointer, { "bc", "de" })
                if otherReg:
                    # Copy from other register
                    asmWriter.loadRegisterWithRegister("hl", otherReg)
                else:
                    # Load pointer from memory
                    print(rhsAddr)
                    asmWriter.loadRegisterWithAddress("hl", rhsAddr.impl.pointer.impl)
                ra.loadSymbolInRegister(rhsAddr.impl.pointer, "hl")
            return "(hl)"
        # TODO this should check nextUse and not liveness
        else:
            regZ = ra.isInRegister(rhsAddr)
            if regZ:
                return regZ
            elif self.live[self.rhsAddr]:
                # Use via register as will be used later (hopefully without spilling)
                regZ = ra.getRegisterForSymbol(rhsAddr, { "b", "c", "d", "e", "h", "l" })
                asmWriter.loadRegisterWithAddress(regZ, rhsAddr.impl)
                ra.loadSymbolInRegister(rhsAddr, regZ)
                return regZ
            else:
                # Use directly from memory, e.g. add a, (ix + 42)
                return rhsAddr.impl.codeArg()

    def load8bitLhsAndRhs(self, asmWriter, transitive=False):
        ra = registerAllocator.RA

        if transitive:
            # if the rhs is already in register a, then swap them
            if isinstance(self.rhsAddr, SymEntry) and ra.isInRegister(self.rhsAddr) == "a":
                self.lhsAddr, self.rhsAddr = self.rhsAddr, self.lhsAddr

        ra.loadInA(self.lhsAddr)
        return self.loadRhs8(self.rhsAddr, asmWriter)

    def load16bitLhsAndRhs(self, transitive=False):
        ra = registerAllocator.RA

        if transitive:
            # if the rhs is already in register a, then swap them
            if isinstance(self.rhsAddr, SymEntry) and ra.isInRegister(self.rhsAddr) == "hl":
                self.lhsAddr, self.rhsAddr = self.rhsAddr, self.lhsAddr

        ra.loadInHL(self.lhsAddr)
        return ra.doLoadInRegister16(self.rhsAddr, { "bc", "de" } )


class IRDefFun(IR):
    def __init__(self, function, stackFrameSize):
        super().__init__()
        self.function = function
        self.stackFrameSize = stackFrameSize

    def extraDescription(self):
        return f"{self.function} {self.stackFrameSize=}"

    def genCode(self, asmWriter):
        asmWriter.write(self.function.name + ":\n");
        # Let IX be frame-pointer
        asmWriter.write('\t; Let IX be frame-pointer\n')
        asmWriter.write('\tpush\tIX\n')
        asmWriter.write('\tld\tIX, 0\n')
        asmWriter.write('\tadd\tIX, SP\n')

        # Reserve space for local variables
        if self.stackFrameSize > 0:
            negSize=65536-self.stackFrameSize
            negHexSize=f'{negSize:05x}h'
            asmWriter.write('\t; Reserve space for local variables\n')
            asmWriter.write(f'\tld\tHL, {negHexSize}\n')
            asmWriter.write(f'\tadd\tHL, SP\n')
            asmWriter.write(f'\tld\tSP, HL\n')

        asmWriter.write('\t; Function content\n')

class IRFunExit(IR):
    def __init__(self, function, hasStackFrame):
        super().__init__()
        self.function = function
        self.hasStackFrame = hasStackFrame

    def genCode(self, asmWriter):
        ra = registerAllocator.RA
        ra.spillAll()
        asmWriter.write(f"{self.function.name}_exit:\n")
        if self.hasStackFrame:
            asmWriter.write('\t;Restore stack pointer (free local variables)\n')
            asmWriter.write(f'\tld\tSP, IX\n')
        asmWriter.write('\t;Restore previous frame pointer IX and return\n')
        asmWriter.write(f'\tpop\tIX\n')
        asmWriter.write(f'\tret\n\n')

class IRIfVariable(IR):
    def __init__(self, lhsAddr, skipLabel):
        super().__init__(lhsAddr=lhsAddr)
        self.skipLabel = skipLabel

    def extraDescription(self):
        return f"{self.skipLabel}"

    def genCode(self, asmWriter):
        ra = registerAllocator.RA
        # Spill before the jump as this will end the basic block. A later call
        # to spillAll will be a no-op.
        ra.spillAll()
        # TODO handle 16 bits
        ra.loadInA(self.lhsAddr)
        asmWriter.write(f'\tor\ta\n')
        asmWriter.write(f'\tjr\tz, {self.skipLabel}\n') 

class IRIfRelation(IR):
    # operation : flag, transitive, flip lhs/rhs
    operations = {'==': ("nz", True, False),
                  '!=': ("z", True, False),
                  '<':  ("nc", False, False),
                  '>=': ("c", False, False),
                  '>':  ("nc", False, True), 
                  '<':  ("c", False, True) }
    def __init__(self, operation, lhsAddr, rhsAddr, skipLabel):
        super().__init__(lhsAddr=lhsAddr, rhsAddr=rhsAddr)
        self.skipLabel = skipLabel
        self.operation = operation

    def extraDescription(self):
        return f"{self.skipLabel}"

    def genCode(self, asmWriter):
        ra = registerAllocator.RA
        # Spill before the jump as this will end the basic block. A later call
        # to spillAll will be a no-op.
        ra.spillAll()
        (flag, transitive, flip) = self.operations[self.operation]
        if flip:
            (self.lhsAddr, self.rhsAddr) = (self.rhsAddr, self.lhsAddr)
        if self.lhsAddr.type == "char":
            regZ = self.load8bitLhsAndRhs(transitive, asmWriter)
            asmWriter.write(f"\tcp\t{regZ}\n")
        elif self.lhsAddr.type == "int":
            regZ = self.load16bitLhsAndRhs(transitive)
            asmWriter.write(f"\tsbc\thl, {regZ}\n")
        asmWriter.write(f'\tjr\t{flag}, {self.skipLabel}\n') 

class IRLabel(IR):
    def __init__(self, label):
        super().__init__()
        self.label = label

    def extraDescription(self):
        return f"{self.label}"

    def genCode(self, asmWriter):
        asmWriter.write(self.label + ":\n")

class IRReturn(IR):
    def __init__(self, t, exprAddr, functionName):
        super().__init__(lhsAddr=exprAddr)
        self.type = t
        self.functionName = functionName

    def __eq__(self, other):
        if not isinstance(other, IRReturn):
            return NotImplemented
        return self.lhsAddr == other.lhsAddr and self.type == other.type

    def extraDescription(self):
        return f"type {self.type}"

    def genCode(self, asmWriter):
        ra = registerAllocator.RA
        if self.type == "char":
            ra.loadInA(self.lhsAddr)
        elif self.type =="int":
            ra.loadInHL(self.lhsAddr)
        ra.spillAll()
        asmWriter.write(f'\tjr\t{self.functionName}_exit\n')

class IRArgument(IR):
    def __init__(self, exprAddr):
        super().__init__(lhsAddr=exprAddr)

    def genCode(self, asmWriter):
        ra = registerAllocator.RA
        if self.exprAddr.type == "char":
            if isinstance(self.lhsAddr, Constant):
                ra.loadInA(self.lhsAddr)
                asmWriter.write(f'\tpush\taf\n')
            else:
                # If in the high byte of a register pair, push it directly
                regX = ra.isInRegister(self.lhsAddr, {'a', 'b', 'd', 'h'})
                if regX:
                    if regX == "a":
                        asmWriter.write("\tpush\taf\n")
                    elif regX == "b":
                        asmWriter.write("\tpush\tbc\n")
                    elif regX == "d":
                        asmWriter.write("\tpush\tde\n")
                    elif regX == "h":
                        asmWriter.write("\tpush\thl\n")
                    return
                # If in the low byte of a register pair, transfer it to a
                ra.getRegisterForSymbol(self.lhsAddr, {'a'})
                regX = ra.isInRegister(self.lhsAddr, {'c', 'e', 'l' })
                if regX:
                    asmWriter.write(f'\tld\ta, {regX}\n')
                else:
                    ra.loadInA(self.lhsAddr)
                asmWriter.write(f'\tpush\taf\n')
        elif self.exprAddr.type == "int":
            if isinstance(self.lhsAddr, Constant):
                ra.loadInHL(self.lhsAddr)
                asmWriter.write(f'\tpush\thl\n')
            else:
                # If in the high byte of a register pair, push it directly
                regX = ra.isInRegister(self.lhsAddr, {'bc', 'de', 'hl' })
                if regX:
                    asmWriter.write(f"\tpush\t{regX}\n")
                else:
                    ra.loadInHL(self.lhsAddr)
                    asmWriter.write(f'\tpush\thl\n')
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

    def genCode(self, asmWriter):
        asmWriter.write(f'\tcall\t{self.name}\n')
        for i in range(self.numArgs):
            asmWriter.write('\tpop\tbc\n') # Use a register we don't care about (yet)
        # if self.numArgs > 0:
            # asmWriter.write(f'\tld\thl, {2*self.numArgs}\n')
            # asmWriter.write(f'\tadd\thl, sp\n')
            # asmWriter.write(f'\tld\tsp, hl\n')
        if self.resultAddr:
            ra = registerAllocator.RA
            returnRegisterForType = { "char": "a",
                                      "int": "hl" }
            if self.type == "char":
                reg = "a"
            elif self.type == "int":
                reg = "hl"
            else:
                error()
            ra.assignToSymbolWithRegister(self.resultAddr, returnRegisterForType[self.type])

class IRAddressOf(IR):
    def __init__(self, symEntry, resAddr):
        super().__init__(resultAddr=resAddr, lhsAddr=symEntry)

    def genCode(self, asmWriter):
        ra = registerAllocator.RA
        # print(f'IRAddressOf spilling {self.lhsAddr.name} ra {ra}')
        # ra.spillName(self.lhsAddr.name)
        # Compute pointer based on ix and offset
        offset = self.exprAddr.impl.offset
        negOffset = 65536+offset
        negHexOffset = f'{negOffset:05x}h'
        # Might as well require HL
        regX = ra.getRegisterForSymbol(self.resultAddr, { "hl" })
        regT = ra.getTemporaryRegister({ "bc", "de" })
        # TODO maybe better to use IY instead of HL if small offset?
        asmWriter.write(f'\tld\t{regX[0]}, ixh\n')
        asmWriter.write(f'\tld\t{regX[1]}, ixl\n')
        # TODO Optimize for small values with INC / DEC
        asmWriter.write(f'\tld\t{regT}, {negHexOffset}\n')
        asmWriter.write(f'\tadd\t{regX}, {regT}\n')
        ra.loadSymbolInRegister(self.resultAddr, regX)

class IRDereference(IR):
    def __init__(self, symEntry, resAddr):
        super().__init__(resultAddr=resAddr, lhsAddr=symEntry)

    def genCode(self, asmWriter):
        ra = registerAllocator.RA
        t = self.lhsAddr.completeType
        ra.spillAllMatchingType(t)


class IRAssign(IR):
    def __init__(self, lvalue, rhsAddress):
        # TODO avoid use of lhsAddr for the rhs.  Use better naming convention
        super().__init__(resultAddr=lvalue, lhsAddr=rhsAddress)

    def genCode(self, asmWriter):
        ra = registerAllocator.RA
        # If we are assigning to variable that has no more uses, store it
        # directly to memory. Note: this is somewhat different from being
        # live.
        # TODO Just always assign to register for now
        # TODO could probably use loadRhs8
        if True: # self.live[self.resultAddr]:
            # Stores to register
            if self.resultAddr.type == "char":
                reg = ra.doLoadInRegister8(self.lhsAddr, { "a", "b", "c", "d", "e", "h", "l" })
            elif self.resultAddr.type == "int":
                reg = ra.doLoadInRegister16(self.lhsAddr, { "bc", "de", "hl" })
            ra.assignToSymbolWithRegister(self.resultAddr, reg)
        else:
            # Stores directly to memory
            if self.resultAddr.type == "char":
                if isinstance(self.lhsAddr, Constant):
                    asmWriter.write(f'\tld\t{self.resultAddr.impl.codeArg()}, {self.lhsAddr.value}\n')
                else:
                    regY = ra.isInRegister(self.lhsAddr, { "a", "b", "c", "d", "e", "h", "l" })
                    if regY:
                        asmWriter.write(f'\tld\t{self.resultAddr.impl.codeArg()}, {regY}\n')
                    else:
                        # TODO use a free register instead of always reg a
                        ra.getRegisterForSymbol(self.lhsAddr, { "a" })
                        asmWriter.write(f'\tld\ta, {self.lhsAddr.impl.codeArg()}\n')
                        asmWriter.write(f'\tld\t{self.resultAddr.impl.codeArg()}, a\n')
                        ra.loadSymbolInRegister(self.lhsAddr, "a")
            elif self.resultAddr.type == "int":
                # TODO handle constants
                regY = ra.isInRegister(self.lhsAddr, { "bc", "de", "hl" })
                if regY:
                    asmWriter.write(f'\tld\t{self.resultAddr.impl.codeArg(+1)}, {regY[0]}\n')
                    asmWriter.write(f'\tld\t{self.resultAddr.impl.codeArg()}, {regY[1]}\n')
                else:
                    ra.spillRegister("a")
                    # TODO use a free register instead of always reg a
                    ra.getRegisterForSymbol(self.lhsAddr, { "a" }) # TODO Only to spill it if needed. Better shorthand?
                    asmWriter.write(f'\tld\ta, {self.lhsAddr.impl.codeArg()}\n')
                    asmWriter.write(f'\tld\t{self.resultAddr.impl.codeArg()}, a\n')
                    asmWriter.write(f'\tld\ta, {self.lhsAddr.impl.codeArg(+1)}\n')
                    asmWriter.write(f'\tld\t{self.resultAddr.impl.codeArg(+1)}, a\n')
            ra.storeToSymbol(self.resultAddr)


class IRAssignToPointer(IR):
    def __init__(self, lvalue, rhsAddress):
        super().__init__(resultAddr=lvalue, lhsAddr=rhsAddress)

    def genCode(self, asmWriter):
        ra = registerAllocator.RA

        t = self.resultAddr.completeType[1:]
        ra.spillAllMatchingType(t)

        if self.resultAddr.completeType == "*char":
            if isinstance(self.lhsAddr, Constant):
                regX = ra.doLoadInRegister16(self.resultAddr, { "bc", "de", "hl" } ) 
                asmWriter.write(f'\tld\t({regX}), {self.lhsAddr.value}\n')
            else:
                regX = ra.doLoadInRegister16(self.resultAddr, { "bc", "de", "hl" } ) 
                # Carefull not to trigger a spill of regX by using a coupled register
                regY = ra.doLoadInRegister8(self.lhsAddr, { "a", "b", "c", "d", "e", "h", "l" } - ra.coupledRegisters[regX])
                asmWriter.write(f'\tld\t({regX}), {regY}\n')
        elif self.resultAddr.completeType == "*int":
            if isinstance(self.lhsAddr, Constant):
                regX = ra.doLoadInRegister16(self.resultAddr, { "bc", "de", "hl" } ) 
                asmWriter.write(f'\tld\t({regX}), {self.lhsAddr.value & 0xff}\n')
                asmWriter.write(f'\tinc\t{regX}\n')
                asmWriter.write(f'\tld\t({regX}), {self.lhsAddr.value >> 8 & 0xff}\n')
                if self.live[self.resultAddr]:
                    asmWriter.write(f'\tdec\t{regX}\n')
                else:
                    ra.removeSymbolForRegister(self.resultAddr, regX)
            else:
                regY = ra.doLoadInRegister16(self.lhsAddr, { "bc", "de", "hl" } )
                regX = ra.doLoadInRegister16(self.resultAddr, { "bc", "de", "hl" } - {regY}) 
                asmWriter.write(f'\tld\t({regX}), {regY[1]}\n')
                asmWriter.write(f'\tinc\t{regX}\n')
                asmWriter.write(f'\tld\t({regX}), {regY[0]}\n')
                if self.live[self.resultAddr]:
                    asmWriter.write(f'\tdec\t{regX}\n')
                else:
                    ra.removeSymbolForRegister(self.resultAddr, regX)
        else:
            error()


class IRAdd(IR):
    def __init__(self, addr, addrLhs, addrRhs):
        super().__init__(addr, addrLhs, addrRhs)

    def genCode(self, asmWriter):
        ra = registerAllocator.RA
        ra.removeSymbol(self.resultAddr)
        if self.lhsAddr.type == "char":
            regZ = self.load8bitLhsAndRhs(asmWriter, transitive=True)
            ra.spillRegister("a")
            asmWriter.write(f"\tadd\ta, {regZ}\n")
            ra.loadSymbolInRegister(self.resultAddr, "a")
        elif self.lhsAddr.type == "int":
            regZ = self.load16bitLhsAndRhs(transitive=True)
            ra.spillRegister("hl")
            asmWriter.write(f"\tadd\thl, {regZ}\n")
            ra.loadSymbolInRegister(self.resultAddr, "hl")
        else:
            error()


class IREqual(IR):
    def __init__(self, lhsAddr, rhsAddr):
        super().__init__(lhsAddr=lhsAddr, rhsAddr=rhsAddr)
        self.addr = Flags()

    def genCode(self, asmWriter):
        if self.lhsAddr.type == "char":
            regZ = self.load8bitLhsAndRhs(asmWriter)
            asmWriter.write(f"\tcp\t{regZ}\n")
        elif self.lhsAddr.type == "int":
            regZ = self.load16bitLhsAndRhs()
            asmWriter.write(f"\tsbc\thl, {regZ}\n")
