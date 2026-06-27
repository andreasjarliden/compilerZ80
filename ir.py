from address import *
from symEntry import *
import registerAllocator
from asmWriter import *
from symbolTable import stackFrameSize

def dropCast(o):
    if isinstance(o, CastSymEntry):
        return o.symEntry
    else:
        return o

# members:
# - live[symbol] = bool, whether symbol is live _at_ this instruction.
class IR:
    def __init__(self, resultAddr=None, lhsAddr=None, rhsAddr=None):
        self.resultAddr=dropCast(resultAddr)
        self.lhsAddr=dropCast(lhsAddr)
        self.rhsAddr=dropCast(rhsAddr)
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
        # return " ".join([live, name,r,o1,o2,xtra, str(self.live)])
        return " ".join([live, name,r,o1,o2,xtra])

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
                    asmWriter.loadRegisterWithAddress("hl", rhsAddr.impl.pointer.impl)
                ra.loadedSymbolInRegister(rhsAddr.impl.pointer, "hl")
            return "(hl)"
        # TODO this should check nextUse and not liveness
        else:
            regZ = ra.isInRegister(rhsAddr)
            if regZ:
                return regZ
            else:
                if isinstance(rhsAddr.impl, StackAddress):
                    if self.live[self.rhsAddr]:
                        # Use via register as will be used later (hopefully without spilling)
                        regZ = ra.getRegisterForSymbol(rhsAddr, { "b", "c", "d", "e", "h", "l" })
                        asmWriter.loadRegisterWithAddress(regZ, rhsAddr.impl)
                        ra.loadedSymbolInRegister(rhsAddr, regZ)
                        return regZ
                    else:
                        # Use directly from memory, e.g. add a, (ix + 42)
                        return rhsAddr.impl.codeArg()
                elif isinstance(rhsAddr.impl, GlobalAddress):
                    # We can only do ld a, (nnnn) so have to use a and then copy it to a different register
                    # Use via register as will be used later (hopefully without spilling)
                    ra.spillRegister("a")
                    asmWriter.loadRegisterWithAddress("a", rhsAddr.impl)
                    ra.loadedSymbolInRegister(rhsAddr, "a")
                    regZ = ra.getRegisterForSymbol(rhsAddr, { "b", "c", "d", "e", "h", "l" })
                    asmWriter.loadRegisterWithRegister(regZ, "a")
                    ra.copiedRegisterToRegister("a", regZ)
                    return regZ
                else:
                    error()

    def load8bitLhsAndRhs(self, asmWriter, transitive=False):
        ra = registerAllocator.RA

        if transitive:
            # if the rhs is already in register a, then swap them
            if isinstance(self.rhsAddr, SymEntry) and ra.isInRegister(self.rhsAddr) == "a":
                self.lhsAddr, self.rhsAddr = self.rhsAddr, self.lhsAddr

        # Load the rhs, first because we might have to temporarily use a, e.g.
        # ld a, (nnnn)
        # ld b, a    as there is no ld b, (nnnn)
        r = self.loadRhs8(self.rhsAddr, asmWriter)
        ra.loadInA(self.lhsAddr)
        return r

    def load16bitLhsAndRhs(self, transitive=False):
        ra = registerAllocator.RA

        if transitive:
            # if the rhs is already in register hl, then swap them
            if isinstance(self.rhsAddr, SymEntry) and ra.isInRegister(self.rhsAddr) == "hl":
                self.lhsAddr, self.rhsAddr = self.rhsAddr, self.lhsAddr

        ra.loadInHL(self.lhsAddr)
        return ra.doLoadInRegister16(self.rhsAddr, { "bc", "de" } )


class IRDefFun(IR):
    def __init__(self, function):
        super().__init__()
        self.function = function

    def extraDescription(self):
        return f"{self.function}"

    def genCode(self, asmWriter):
        asmWriter.write(self.function.name + ":\n");
        # Let IX be frame-pointer
        asmWriter.write('\t; Let IX be frame-pointer\n')
        asmWriter.write('\tpush\tIX\n')
        asmWriter.write('\tld\tIX, 0\n')
        asmWriter.write('\tadd\tIX, SP\n')

        # Reserve space for local variables
        if self.function.frameSize > 0:
            negSize=65536-self.function.frameSize
            negHexSize=f'{negSize:05x}h'
            asmWriter.write('\t; Reserve space for local variables\n')
            asmWriter.write(f'\tld\tHL, {negHexSize}\n')
            asmWriter.write(f'\tadd\tHL, SP\n')
            asmWriter.write(f'\tld\tSP, HL\n')

        asmWriter.write('\t; Function content\n')

class IRFunExit(IR):
    def __init__(self, function):
        super().__init__()
        self.function = function

    def genCode(self, asmWriter):
        ra = registerAllocator.RA
        ra.spillAll()
        asmWriter.write(f"{self.function.name}_exit:\n")
        if self.function.frameSize > 0:
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
        if self.lhsAddr.type == "char":
            ra.loadInA(self.lhsAddr)
            # TODO if lhsAddr was just computed and not loaded, the or will not be needed
            asmWriter.write(f'\tor\ta\n')
        elif self.lhsAddr.type == "int":
            ra.loadInHL(self.lhsAddr)
            # TODO if lhsAddr was just computed and not loaded, the or will not be needed
            asmWriter.write(f'\tld\ta, h\n')
            asmWriter.write(f'\tor\tl\n')
        else:
            error()
        # Spill before the jump as this will end the basic block. A later call
        # to spillAll will be a no-op.
        # TODO a temp expression that we just check is no longer live but will
        # be spilled for real. Avoidable?
        ra.spillAll()
        # TODO smart relative jump selection
        # asmWriter.write(f'\tjr\tz, {self.skipLabel}\n') 
        asmWriter.write(f'\tjp\tz, {self.skipLabel}\n') 

class IRSpillAll(IR):
    def __init__(self):
        super().__init__()

    def genCode(self, asmWriter):
        ra = registerAllocator.RA
        ra.spillAll()


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
            regZ = self.load8bitLhsAndRhs(asmWriter, transitive)
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

class IRJump(IR):
    def __init__(self, label):
        super().__init__()
        self.label = label

    def extraDescription(self):
        return f"{self.label}"

    def genCode(self, asmWriter):
        asmWriter.write(f"\tjp\t{self.label}\n")

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
        else:
            print(f"IRReturn returning type {self.type}")
            error();
        ra.spillAll()
        asmWriter.write(f'\tjr\t{self.functionName}_exit\n')

class IRArgument(IR):
    def __init__(self, exprAddr):
        super().__init__(lhsAddr=exprAddr)

    def genCode(self, asmWriter):
        asmWriter.write(f"\t; Argument {self.lhsAddr}\n")
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
                # TODO can't this use bc, de also?
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
        asmWriter.write(f"\t; Function call {self.name}\n")
        ra = registerAllocator.RA
        # TODO only spill what might be accessed by the called function
        ra.spillAll()
        asmWriter.write(f'\tcall\t{self.name}\n')
        for i in range(self.numArgs):
            asmWriter.write('\tpop\tbc\n') # Use a register we don't care about (yet)
        # if self.numArgs > 0:
            # asmWriter.write(f'\tld\thl, {2*self.numArgs}\n')
            # asmWriter.write(f'\tadd\thl, sp\n')
            # asmWriter.write(f'\tld\tsp, hl\n')
        if self.resultAddr:
            returnRegisterForType = { "char": "a",
                                      "int": "hl" }
            if self.type == "char":
                reg = "a"
            elif self.type == "int":
                reg = "hl"
            else:
                error()
            ra.assignedToSymbolWithRegister(self.resultAddr, returnRegisterForType[self.type])

class IRAddressOf(IR):
    def __init__(self, symEntry, resAddr):
        super().__init__(resultAddr=resAddr, lhsAddr=symEntry)

    def genCode(self, asmWriter):
        print(f"IRAddressOf {self.exprAddr}")
        ra = registerAllocator.RA
        if isinstance(self.exprAddr.impl, StackAddress):
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
            ra.loadedSymbolInRegister(self.resultAddr, regX)
        elif isinstance(self.exprAddr.impl, GlobalAddress):
            self.resultAddr.impl = GlobalLabel(self.exprAddr.impl.name)

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
        asmWriter.write(f"\t; Assign to {self.resultAddr.name}\n")
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
            else:
                error()
            ra.verify()
            ra.assignedToSymbolWithRegister(self.resultAddr, reg)
            ra.verify()
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
                        ra.loadedSymbolInRegister(self.lhsAddr, "a")
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
            ra.storedToSymbol(self.resultAddr)


class IRAssignToPointer(IR):
    def __init__(self, lvalue, rhsAddress):
        # Note, we are USING the pointer, not replacing it
        super().__init__(lhsAddr=lvalue, rhsAddr=rhsAddress)

    # def updateLive(self, live):
    #     if self.resultAddr and isinstance(self.resultAddr, SymEntry):
    #         # Don't update live to False as we are only assigning through the pointer
    #         pass
    #         # live[self.resultAddr] = False
    #     if self.lhsAddr and isinstance(self.lhsAddr, SymEntry):
    #         live[self.lhsAddr] = True
    #     if self.rhsAddr and isinstance(self.rhsAddr, SymEntry):
    #         live[self.rhsAddr] = True
    #     self.live = live.copy()

    def genCode(self, asmWriter):
        asmWriter.write(f"\t; Assign via pointer {self.lhsAddr.name}\n")
        ra = registerAllocator.RA

        t = self.lhsAddr.completeType[:-1]

        if self.lhsAddr.completeType == "char*":
            if isinstance(self.rhsAddr, Constant):
                regX = ra.doLoadInRegister16(self.lhsAddr, { "bc", "de", "hl" } ) 
                asmWriter.write(f'\tld\t({regX}), {self.rhsAddr.value}\n')
            else:
                regX = ra.doLoadInRegister16(self.lhsAddr, { "bc", "de", "hl" } ) 
                # Carefull not to trigger a spill of regX by using a coupled register
                regY = ra.doLoadInRegister8(self.rhsAddr, { "a", "b", "c", "d", "e", "h", "l" } - ra.coupledRegisters[regX])
                asmWriter.write(f'\tld\t({regX}), {regY}\n')
        elif self.lhsAddr.completeType == "int*":
            if isinstance(self.rhsAddr, Constant):
                regX = ra.doLoadInRegister16(self.lhsAddr, { "bc", "de", "hl" } ) 
                asmWriter.write(f'\tld\t({regX}), {self.rhsAddr.value & 0xff}\n')
                asmWriter.write(f'\tinc\t{regX}\n')
                asmWriter.write(f'\tld\t({regX}), {self.rhsAddr.value >> 8 & 0xff}\n')
                if self.live[self.lhsAddr]:
                    asmWriter.write(f'\tdec\t{regX}\n')
                else:
                    ra.removeSymbolForRegister(self.lhsAddr, regX)
            else:
                regY = ra.doLoadInRegister16(self.rhsAddr, { "bc", "de", "hl" } )
                regX = ra.doLoadInRegister16(self.lhsAddr, { "bc", "de", "hl" } - {regY}) 
                if regX == "hl":
                    asmWriter.write(f'\tld\t({regX}), {regY[1]}\n')
                    asmWriter.write(f'\tinc\t{regX}\n')
                    asmWriter.write(f'\tld\t({regX}), {regY[0]}\n')
                else:
                    # No ld (bc/de), r instruction only ld (bc/de), a
                    ra.spillRegister("a")
                    asmWriter.write(f'\tld\ta, {regY[1]}\n')
                    asmWriter.write(f'\tld\t({regX}), a\n')
                    asmWriter.write(f'\tinc\t{regX}\n')
                    asmWriter.write(f'\tld\ta, {regY[0]}\n')
                    asmWriter.write(f'\tld\t({regX}), a\n')
                if self.live[self.lhsAddr]:
                    asmWriter.write(f'\tdec\t{regX}\n')
                else:
                    ra.removeSymbolForRegister(self.lhsAddr, regX)
        else:
            error()
        # We might have invalidated something of type t
        ra.spillAllMatchingType(t)


class IRAdd(IR):
    def __init__(self, addr, addrLhs, addrRhs):
        super().__init__(addr, addrLhs, addrRhs)

    def genCode(self, asmWriter):
        ra = registerAllocator.RA
        ra.verify()
        ra.removeSymbol(self.resultAddr)
        ra.verify()
        if self.lhsAddr.type == "char":
            regZ = self.load8bitLhsAndRhs(asmWriter, transitive=True)
            ra.verify()
            ra.spillRegister("a")
            ra.verify()
            asmWriter.write(f"\tadd\ta, {regZ}\n")
            ra.loadedSymbolInRegister(self.resultAddr, "a")
        elif self.lhsAddr.type == "int":
            regZ = self.load16bitLhsAndRhs(transitive=True)
            ra.verify()
            ra.spillRegister("hl")
            ra.verify()
            asmWriter.write(f"\tadd\thl, {regZ}\n")
            ra.loadedSymbolInRegister(self.resultAddr, "hl")
            ra.verify()
        else:
            error()


class IRSub(IR):
    def __init__(self, addr, addrLhs, addrRhs):
        super().__init__(addr, addrLhs, addrRhs)

    def genCode(self, asmWriter):
        ra = registerAllocator.RA
        ra.verify()
        # ra.removeSymbol(self.resultAddr)
        if self.lhsAddr.type == "char":
            ra.verify()
            regZ = self.load8bitLhsAndRhs(asmWriter, transitive=False)
            ra.verify()
            ra.spillRegister("a")
            ra.verify()
            asmWriter.write(f"\tsub\ta, {regZ}\n")
            ra.loadedSymbolInRegister(self.resultAddr, "a")
        elif self.lhsAddr.type == "int":
            regZ = self.load16bitLhsAndRhs(transitive=False)
            ra.spillRegister("hl")
            asmWriter.write(f"\tor\ta\n") # Clears Carry flag without changing A
            asmWriter.write(f"\tsbc\thl, {regZ}\n")
            ra.loadedSymbolInRegister(self.resultAddr, "hl")
        else:
            error()


class IRBitwiseOr(IR):
    def __init__(self, addr, addrLhs, addrRhs):
        super().__init__(addr, addrLhs, addrRhs)

    def genCode(self, asmWriter):
        ra = registerAllocator.RA
        ra.verify()
        ra.removeSymbol(self.resultAddr)
        ra.verify()
        if self.lhsAddr.type == "char":
            regZ = self.load8bitLhsAndRhs(asmWriter, transitive=True)
            ra.verify()
            ra.spillRegister("a")
            ra.verify()
            asmWriter.write(f"\tor\ta, {regZ}\n")
            ra.assignedToSymbolWithRegister(self.resultAddr, "a")
        elif self.lhsAddr.type == "int":
            regLhs = ra.doLoadInRegister16(self.lhsAddr, { "bc", "de", "hl" } )
            regRhs = ra.doLoadInRegister16(self.rhsAddr, { "bc", "de", "hl" } - { regLhs })
            # TODO, I think we could re-use regLhs or regRhs for this
            regRes = ra.getRegisterForSymbol(self.resultAddr, { "bc", "de", "hl" } - { regLhs, regRhs })
            ra.spillRegister("a")
                                           
            asmWriter.write(f"\tld\ta, {regLhs[0]}\n")
            asmWriter.write(f"\tor\t{regRhs[0]}\n")
            asmWriter.write(f"\tld\t{regRes[0]}, a\n")

            asmWriter.write(f"\tld\ta, {regLhs[1]}\n")
            asmWriter.write(f"\tor\t{regRhs[1]}\n")
            asmWriter.write(f"\tld\t{regRes[1]}, a\n")

            ra.assignedToSymbolWithRegister(self.resultAddr, regRes)
            ra.verify()
        else:
            error()
            

class IRBitwiseAnd(IR):
    def __init__(self, addr, addrLhs, addrRhs):
        super().__init__(addr, addrLhs, addrRhs)

    def genCode(self, asmWriter):
        ra = registerAllocator.RA
        ra.verify()
        ra.removeSymbol(self.resultAddr)
        ra.verify()
        if self.lhsAddr.type == "char":
            regZ = self.load8bitLhsAndRhs(asmWriter, transitive=True)
            ra.verify()
            ra.spillRegister("a")
            ra.verify()
            asmWriter.write(f"\tand\ta, {regZ}\n")
            ra.assignedToSymbolWithRegister(self.resultAddr, "a")
        elif self.lhsAddr.type == "int":
            regLhs = ra.doLoadInRegister16(self.lhsAddr, { "bc", "de", "hl" } )
            regRhs = ra.doLoadInRegister16(self.rhsAddr, { "bc", "de", "hl" } - { regLhs })
            # TODO, I think we could re-use regLhs or regRhs for this
            regRes = ra.getRegisterForSymbol(self.resultAddr, { "bc", "de", "hl" } - { regLhs, regRhs })
            ra.spillRegister("a")
                                           
            asmWriter.write(f"\tld\ta, {regLhs[0]}\n")
            asmWriter.write(f"\tand\t{regRhs[0]}\n")
            asmWriter.write(f"\tld\t{regRes[0]}, a\n")

            asmWriter.write(f"\tld\ta, {regLhs[1]}\n")
            asmWriter.write(f"\tand\t{regRhs[1]}\n")
            asmWriter.write(f"\tld\t{regRes[1]}, a\n")

            ra.assignedToSymbolWithRegister(self.resultAddr, regRes)
            ra.verify()
        else:
            error()


class IRPromote(IR):
    def __init__(self, addr, exprAddr, toType):
        super().__init__(resultAddr=addr, lhsAddr=exprAddr)
        self.toType = toType

    def genCode(self, asmWriter):
        asmWriter.write(f"\t; Promote {self.resultAddr} from {self.lhsAddr}\n")
        ra = registerAllocator.RA
        reg16 = ra.decideRegisterForSymbol(self.resultAddr, { "bc", "de", "hl" })
        reg16_hi = reg16[0]
        reg16_lo = reg16[1]
        if isinstance(self.lhsAddr, Constant):
            asmWriter.write(f"\tld\t{reg16}, {self.lhsAddr.value}\n")
            ra.loadedSymbolInRegister(self.resultAddr, reg16)
            return
        reg8 = ra.isInRegister(self.lhsAddr, { "a", "b", "c", "d", "e", "h", "l" })
        asmWriter.write(f"\tld\t{reg16_hi}, 0\n")
        if reg8:
            if reg16_lo != reg8:
                asmWriter.loadRegisterWithRegister(reg16_lo, reg8)
        else:
            asmWriter.loadRegisterWithAddress(reg16_lo, self.lhsAddr.impl)
        ra.loadedSymbolInRegister(self.resultAddr, reg16)

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



