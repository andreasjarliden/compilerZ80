from address import *
from symEntry import *
import registerAllocator
from asmWriter import *

# TODO maybe add asmWriter.write and then we can only use asmWriter
asmFile = None
asmWriter = AsmWriter(asmFile)

IR_FUNCTIONS = []


# Size of all local stack variables
def stackFrameSize(symbolTable):
    smallestOffset = 0
    for s in symbolTable.values():
        if isinstance(s.impl, StackAddress):
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
            live[self.resultAddr.name] = False
        if self.lhsAddr and isinstance(self.lhsAddr, SymEntry):
            live[self.lhsAddr.name] = True
        if self.rhsAddr and isinstance(self.rhsAddr, SymEntry):
            live[self.rhsAddr.name] = True
        self.live = live.copy()

    def liveStr(self):
        if not self.live:
            return ""
        if self.resultAddr and isinstance(self.resultAddr, SymEntry):
            s1 = "L" if self.live[self.resultAddr.name] else "D"
        else:
            s1="?"
        if self.lhsAddr and isinstance(self.lhsAddr, SymEntry):
            s2 = "L" if self.live[self.lhsAddr.name] else "D"
        else:
            s2="?"
        if self.rhsAddr and isinstance(self.rhsAddr, SymEntry):
            s3 = "L" if self.live[self.rhsAddr.name] else "D"
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
    def loadRhs8(self, rhsAddr):
        ra = registerAllocator.RA
        if isinstance(rhsAddr, Constant):
            return rhsAddr.value
        elif isinstance(rhsAddr.impl, PointerAddress):
            # Must have the pointer in hl (or ix/iy). bc & de not supported by Z80
            regZ = ra.isInRegister(rhsAddr.impl.pointer.name, { "hl" })
            # Already in hl?
            if not regZ:
                otherReg = ra.isInRegister(rhsAddr.impl.pointer.name, { "bc", "de" })
                if otherReg:
                    # Copy from other register
                    asmWriter.loadRegisterWithRegister("hl", otherReg)
                else:
                    # Load pointer from memory
                    asmWriter.loadRegisterWithAddress("hl", rhsAddr.impl.pointer.impl)
                ra.loadNameInRegister(rhsAddr.impl.pointer.name, "hl")
            return "(hl)"
        # TODO this should check nextUse and not liveness
        elif ra.isInRegister(rhsAddr.name) or self.live[self.rhsAddr.name]:
            # Use via register as already in register or will be used later
            regZ = ra.getRegisterForArg(rhsAddr.name, { "b", "c", "d", "e", "h", "l" })
            if rhsAddr.name not in ra.registers[regZ]:
                asmWriter.loadRegisterWithAddress(regZ, rhsAddr.impl)
                ra.loadNameInRegister(rhsAddr.name, regZ)
            return regZ
        else:
            # Use directly from memory, e.g. add a, (ix + 42)
            return rhsAddr.impl.codeArg()

    def load8bitLhsAndRhs(self, transitive=False):
        ra = registerAllocator.RA

        if transitive:
            # if the rhs is already in register a, then swap them
            if isinstance(self.rhsAddr, SymEntry) and ra.isInRegister(self.rhsAddr.name) == "a":
                self.lhsAddr, self.rhsAddr = self.rhsAddr, self.lhsAddr

        ra.loadInA(self.lhsAddr)
        return self.loadRhs8(self.rhsAddr)

    def load16bitLhsAndRhs(self, transitive=False):
        ra = registerAllocator.RA

        if transitive:
            # if the rhs is already in register a, then swap them
            if isinstance(self.rhsAddr, SymEntry) and ra.isInRegister(self.rhsAddr.name) == "hl":
                self.lhsAddr, self.rhsAddr = self.rhsAddr, self.lhsAddr

        ra.loadInHL(self.lhsAddr)
        return ra.doLoadInRegister16(self.rhsAddr, { "bc", "de" } )


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
    def __init__(self, function, hasStackFrame):
        super().__init__()
        self.function = function
        self.hasStackFrame = hasStackFrame

    def genCode(self):
        ra = registerAllocator.RA
        ra.spillAll()
        asmFile.write(f"{self.function.name}_exit:\n")
        global IR_FUNCTION
        IR_FUNCTION=None
        if self.hasStackFrame:
            asmFile.write('\t;Restore stack pointer (free local variables)\n')
            asmFile.write(f'\tld\tSP, IX\n')
        asmFile.write('\t;Restore previous frame pointer IX and return\n')
        asmFile.write(f'\tpop\tIX\n')
        asmFile.write(f'\tret\n\n')

class IRIfVariable(IR):
    def __init__(self, lhsAddr, skipLabel):
        super().__init__(lhsAddr=lhsAddr)
        self.skipLabel = skipLabel

    def extraDescription(self):
        return f"{self.skipLabel}"

    def genCode(self):
        ra = registerAllocator.RA
        # Spill before the jump as this will end the basic block. A later call
        # to spillAll will be a no-op.
        ra.spillAll()
        # TODO handle 16 bits
        ra.loadInA(self.lhsAddr)
        asmFile.write(f'\tor\ta\n')
        asmFile.write(f'\tjr\tz, {self.skipLabel}\n') 

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

    def genCode(self):
        ra = registerAllocator.RA
        # Spill before the jump as this will end the basic block. A later call
        # to spillAll will be a no-op.
        ra.spillAll()
        (flag, transitive, flip) = self.operations[self.operation]
        if flip:
            (self.lhsAddr, self.rhsAddr) = (self.rhsAddr, self.lhsAddr)
        if self.lhsAddr.type == "char":
            regZ = self.load8bitLhsAndRhs(transitive)
            asmFile.write(f"\tcp\t{regZ}\n")
        elif self.lhsAddr.type == "int":
            regZ = self.load16bitLhsAndRhs(transitive)
            asmFile.write(f"\tsbc\thl, {regZ}\n")
        asmFile.write(f'\tjr\t{flag}, {self.skipLabel}\n') 

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

    def __eq__(self, other):
        if not isinstance(other, IRReturn):
            return NotImplemented
        return self.lhsAddr == other.lhsAddr and self.type == other.type

    def extraDescription(self):
        return f"type {self.type}"

    def genCode(self):
        ra = registerAllocator.RA
        if self.type == "char":
            ra.loadInA(self.lhsAddr)
        elif self.type =="int":
            ra.loadInHL(self.lhsAddr)
        ra.spillAll()
        asmFile.write(f'\tjr\t{IR_FUNCTION}_exit\n')

class IRArgument(IR):
    def __init__(self, exprAddr):
        super().__init__(lhsAddr=exprAddr)

    def genCode(self):
        ra = registerAllocator.RA
        if self.exprAddr.type == "char":
            if isinstance(self.lhsAddr, Constant):
                ra.loadInA(self.lhsAddr)
                asmFile.write(f'\tpush\taf\n')
            else:
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
                    ra.loadInA(self.lhsAddr)
                asmFile.write(f'\tpush\taf\n')
        elif self.exprAddr.type == "int":
            if isinstance(self.lhsAddr, Constant):
                ra.loadInHL(self.lhsAddr)
                asmFile.write(f'\tpush\thl\n')
            else:
                # If in the high byte of a register pair, push it directly
                regX = ra.isInRegister(self.lhsAddr.name, {'bc', 'de', 'hl' })
                if regX:
                    asmFile.write(f"\tpush\t{regX}\n")
                else:
                    ra.loadInHL(self.lhsAddr)
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
            ra = registerAllocator.RA
            returnRegisterForType = { "char": "a",
                                      "int": "hl" }
            if self.type == "char":
                reg = "a"
            elif self.type == "int":
                reg = "hl"
            else:
                error()
            ra.assignToNameWithRegister(self.resultAddr.name, returnRegisterForType[self.type])

class IRAddressOf(IR):
    def __init__(self, symEntry, resAddr):
        super().__init__(resultAddr=resAddr, lhsAddr=symEntry)

    def genCode(self):
        ra = registerAllocator.RA
        # print(f'IRAddressOf spilling {self.lhsAddr.name} ra {ra}')
        # ra.spillName(self.lhsAddr.name)
        # Compute pointer based on ix and offset
        offset = self.exprAddr.impl.offset
        negOffset = 65536+offset
        negHexOffset = f'{negOffset:05x}h'
        # Might as well require HL
        regX = ra.getRegisterForArg(self.resultAddr.name, { "hl" })
        regT = ra.getTemporaryRegister({ "bc", "de" })
        # TODO maybe better to use IY instead of HL if small offset?
        asmFile.write(f'\tld\t{regX[0]}, ixh\n')
        asmFile.write(f'\tld\t{regX[1]}, ixl\n')
        # TODO Optimize for small values with INC / DEC
        asmFile.write(f'\tld\t{regT}, {negHexOffset}\n')
        asmFile.write(f'\tadd\t{regX}, {regT}\n')
        ra.loadNameInRegister(self.resultAddr.name, regX)

class IRDereference(IR):
    def __init__(self, symEntry, resAddr):
        super().__init__(resultAddr=resAddr, lhsAddr=symEntry)

    def genCode(self):
        ra = registerAllocator.RA
        t = self.lhsAddr.completeType
        ra.spillAllMatchingType(t)


class IRAssign(IR):
    def __init__(self, lvalue, rhsAddress):
        # TODO avoid use of lhsAddr for the rhs.  Use better naming convention
        super().__init__(resultAddr=lvalue, lhsAddr=rhsAddress)

    def genCode(self):
        ra = registerAllocator.RA
        # If we are assigning to variable that has no more uses, store it
        # directly to memory. Note: this is somewhat different from being
        # live.
        # TODO Just always assign to register for now
        # TODO could probably use loadRhs8
        if True: # self.live[self.resultAddr.name]:
            # Stores to register
            if self.resultAddr.type == "char":
                reg = ra.doLoadInRegister8(self.lhsAddr, { "a", "b", "c", "d", "e", "h", "l" })
            elif self.resultAddr.type == "int":
                reg = ra.doLoadInRegister16(self.lhsAddr, { "bc", "de", "hl" })
            ra.assignToNameWithRegister(self.resultAddr.name, reg)
        else:
            # Stores directly to memory
            if self.resultAddr.type == "char":
                if isinstance(self.lhsAddr, Constant):
                    asmFile.write(f'\tld\t{self.resultAddr.impl.codeArg()}, {self.lhsAddr.value}\n')
                else:
                    regY = ra.isInRegister(self.lhsAddr.name, { "a", "b", "c", "d", "e", "h", "l" })
                    if regY:
                        asmFile.write(f'\tld\t{self.resultAddr.impl.codeArg()}, {regY}\n')
                    else:
                        # TODO use a free register instead of always reg a
                        ra.getRegisterForArg(self.lhsAddr.name , { "a" }) # TODO Only to spill it if needed. Better shorthand?
                        asmFile.write(f'\tld\ta, {self.lhsAddr.impl.codeArg()}\n')
                        asmFile.write(f'\tld\t{self.resultAddr.impl.codeArg()}, a\n')
                        ra.loadNameInRegister(self.lhsAddr.name, "a")
            elif self.resultAddr.type == "int":
                # TODO handle constants
                regY = ra.isInRegister(self.lhsAddr.name, { "bc", "de", "hl" })
                if regY:
                    asmFile.write(f'\tld\t{self.resultAddr.impl.codeArg(+1)}, {regY[0]}\n')
                    asmFile.write(f'\tld\t{self.resultAddr.impl.codeArg()}, {regY[1]}\n')
                else:
                    ra.getRegisterForArg(self.lhsAddr.name , { "a" }) # TODO Only to spill it if needed. Better shorthand?
                    asmFile.write(f'\tld\ta, {self.lhsAddr.impl.codeArg()}\n')
                    asmFile.write(f'\tld\t{self.resultAddr.impl.codeArg()}, a\n')
                    asmFile.write(f'\tld\ta, {self.lhsAddr.impl.codeArg(+1)}\n')
                    asmFile.write(f'\tld\t{self.resultAddr.impl.codeArg(+1)}, a\n')
            ra.storeToName(self.resultAddr.name)


class IRAssignToPointer(IR):
    def __init__(self, lvalue, rhsAddress):
        super().__init__(resultAddr=lvalue, lhsAddr=rhsAddress)

    def genCode(self):
        ra = registerAllocator.RA

        t = self.resultAddr.completeType[1:]
        ra.spillAllMatchingType(t)

        if self.resultAddr.completeType == "*char":
            if isinstance(self.lhsAddr, Constant):
                regX = ra.doLoadInRegister16(self.resultAddr, { "bc", "de", "hl" } ) 
                asmFile.write(f'\tld\t({regX}), {self.lhsAddr.value}\n')
            else:
                regX = ra.doLoadInRegister16(self.resultAddr, { "bc", "de", "hl" } ) 
                # Carefull not to trigger a spill of regX by using a coupled register
                regY = ra.doLoadInRegister8(self.lhsAddr, { "a", "b", "c", "d", "e", "h", "l" } - ra.coupledRegisters[regX])
                asmFile.write(f'\tld\t({regX}), {regY}\n')
        elif self.resultAddr.completeType == "*int":
            if isinstance(self.lhsAddr, Constant):
                regX = ra.doLoadInRegister16(self.resultAddr, { "bc", "de", "hl" } ) 
                asmFile.write(f'\tld\t({regX}), {self.lhsAddr.value & 0xff}\n')
                asmFile.write(f'\tinc\t{regX}\n')
                asmFile.write(f'\tld\t({regX}), {self.lhsAddr.value >> 8 & 0xff}\n')
                if self.live[self.resultAddr.name]:
                    asmFile.write(f'\tdec\t{regX}\n')
                else:
                    ra.removeNameForRegister(self.resultAddr.name, regX)
            else:
                regY = ra.doLoadInRegister16(self.lhsAddr, { "bc", "de", "hl" } )
                regX = ra.doLoadInRegister16(self.resultAddr, { "bc", "de", "hl" } - {regY}) 
                asmFile.write(f'\tld\t({regX}), {regY[1]}\n')
                asmFile.write(f'\tinc\t{regX}\n')
                asmFile.write(f'\tld\t({regX}), {regY[0]}\n')
                if self.live[self.resultAddr.name]:
                    asmFile.write(f'\tdec\t{regX}\n')
                else:
                    ra.removeNameForRegister(self.resultAddr.name, regX)
        else:
            error()


class IRAdd(IR):
    def __init__(self, addr, addrLhs, addrRhs):
        super().__init__(addr, addrLhs, addrRhs)

    def genCode(self):
        ra = registerAllocator.RA
        ra.removeName(self.resultAddr.name)
        if self.lhsAddr.type == "char":
            regZ = self.load8bitLhsAndRhs(transitive=True)
            ra.spillRegister("a")
            asmFile.write(f"\tadd\ta, {regZ}\n")
            ra.loadNameInRegister(self.resultAddr.name, "a")
        elif self.lhsAddr.type == "int":
            regZ = self.load16bitLhsAndRhs(transitive=True)
            ra.spillRegister("hl")
            asmFile.write(f"\tadd\thl, {regZ}\n")
            ra.loadNameInRegister(self.resultAddr.name, "hl")
        else:
            error()


class IREqual(IR):
    def __init__(self, lhsAddr, rhsAddr):
        super().__init__(lhsAddr=lhsAddr, rhsAddr=rhsAddr)
        self.addr = Flags()

    def genCode(self):
        if self.lhsAddr.type == "char":
            regZ = self.load8bitLhsAndRhs()
            asmFile.write(f"\tcp\t{regZ}\n")
        elif self.lhsAddr.type == "int":
            regZ = self.load16bitLhsAndRhs()
            asmFile.write(f"\tsbc\thl, {regZ}\n")
