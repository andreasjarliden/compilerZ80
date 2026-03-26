import unittest
from io import StringIO
from symEntry import *
from address import *
from asmWriter import AsmWriter
from ir import *
from symEntry import StackAddress, PointerAddress

RA = None
ALL_REGISTERS = {'a', 'b', 'c', 'd', 'e', 'h', 'l', 'bc', 'de', 'hl'}

class RegisterAllocator:
    def __init__(self):
        self.registers = {r: set() for r in ALL_REGISTERS}
        self.symbols = {}
        self.coupledRegisters = { 'bc': ('b', 'c'),
                                 'b': ['bc'],
                                 'c': ('bc',),
                                 'de': ('d', 'e'),
                                 'd': ['de'],
                                 'e': ('de',),
                                 'hl': ('h', 'l'),
                                 'h': ['hl'],
                                 'l': ('hl',) }
        self.currentInstruction = None

    def __repr__(self):
        return f"registers: {self.registers}\nfree registers: {self.freeRegisters}\nsymbols: {self.symbols}"

    def doSpillToSymbol(self, reg, s):
        pass

    def isFree(self, r):
        if self.registers[r]:
            return False
        for cr in self.coupledRegisters.get(r, ()):
            if self.registers[cr]:
                return False
        return True

    @property
    def freeRegisters(self):
        free = []
        for r in self.registers:
            if self.isFree(r):
                free.append(r)
        return set(free)

    def spillRegister(self, r):
        # Remove register from all addresses
        symbols = self.registers[r].copy()
        for s in symbols:
            self.spillRegisterToSymbol(r, s)

    def spillRegisterToSymbol(self, r, s):
        self.symbols[s].add(s)
        self.symbols[s].remove(r)
        if self.currentInstruction.live[s]:
            self.doSpillToSymbol(r, s)
        self.registers[r].remove(s)

    def removeSymbolForRegister(self, s, r):
        self.registers[r].remove(s)
        self.symbols[s].remove(r)

    # TODO test
    def removeSymbol(self, s):
        registers = self.symbols.get(s, set()) & ALL_REGISTERS;
        for r in registers:
            self.registers[r].remove(s)
        self.symbols[s] = set()

    def _spillScore(self, r):
        score = 0
        # TODO also handle coupled registers
        for s in self.registers[r]:
            # If s is in some other register. Consider it free to spill.
            # (disregard if we have different groups of registers)
            if len(self.symbols[s]) > 1:
                continue
            # # Is s what we are assigning to? In that case free to spill TODO
            # # maybe not needed as we always have to load the lhs in A or HL
            # if n == ir.resultAddr.name:
            #     continue
            # Is dead?
            if not self.currentInstruction.live[s]:
                continue
            # Have to spill to n
            score += 1
        return score

    def spillSymbol(self, s):
        # Already stored in memory?
        if s not in self.symbols[s]:
            # pick one of register contining n
            r = next(iter(self.symbols[s]))
            self.spillRegisterToSymbol(r, s)

    def spillAll(self):
        for s in self.symbols:
            self.spillSymbol(s)

    def spillAllMatchingType(self, t):
        for s in self.symbols.keys():
            if s.completeType == t:
                self.spillSymbol(s)
            
    def _bestRegisterToSpill(self, possibleRegisters):
        return min(possibleRegisters, key=self._spillScore)

    # Like getRegisterForArg but doesn't spill
    def decideRegisterForSymbol(self, symbol, possibleRegisters):
        # Already loaded?
        regs = self.symbols.get(symbol, set()) & possibleRegisters
        pass
        if regs:
            return regs.pop()
        # No, pick one of the free registers
        regs = self.freeRegisters & possibleRegisters
        if regs:
            return regs.pop()
        # No free, have to spill
        return self._bestRegisterToSpill(possibleRegisters)

    # TODO this does not register the name as loaded in the register, maybe it
    # should. Maybe this should be private and there should be public version
    # that does all.
    def getRegisterForSymbol(self, symbol, possibleRegisters):
        # Already loaded?
        regs = self.symbols.get(symbol, set()) & possibleRegisters
        if regs:
            return regs.pop()
        # No, pick one of the free registers
        regs = self.freeRegisters & possibleRegisters
        if regs:
            return regs.pop()
        # No free, have to spill
        r = self._bestRegisterToSpill(possibleRegisters)
        self.spillRegister(r)
        # Spill any coupled register, e.g. spilling bc means also spilling b and c (if loaded). 
        for cr in self.coupledRegisters.get(r, ()):
            self.spillRegister(cr)
        return r

    # Get a register, spilling if necessary
    def getTemporaryRegister(self, possibleRegisters):
        # pick one of the free registers
        regs = self.freeRegisters & possibleRegisters
        if regs:
            return regs.pop()
        # No free, have to spill
        r = self._bestRegisterToSpill(possibleRegisters)
        self.spillRegister(r)
        # Spill any coupled register, e.g. spilling bc means also spilling b and c (if loaded). 
        for cr in self.coupledRegisters.get(r, ()):
            self.spillRegister(cr)
        return r

    def isInRegister(self, symbol, possibleRegisters = ALL_REGISTERS):
        # Already loaded?
        regs = self.symbols.get(symbol, set()) & possibleRegisters
        if regs:
            return regs.pop()
        else:
            return None

    def loadSymbolInRegister(self, s, r):
        self.symbols.setdefault(s, set())
        self.symbols[s].add(r)
        self.symbols[s].add(s)
        self.registers[r].add(s)

    # Example: LD (ix+n), a
    def storeToSymbol(self, s):
        self.symbols.setdefault(s, set())
        self.symbols[s].add(s)

    # Assigning to a name means that it is only the register that holds the
    # name, it has not been spilled to memory yet.
    def assignToSymbolWithRegister(self, s, r):
        self.symbols[s] = { r }
        self.registers[r].add(s)


class Z80RegisterAllocator(RegisterAllocator):
    def __init__(self, asmFile):
        super().__init__()
        self.asmFile = asmFile
        self.asmWriter = AsmWriter(asmFile)

    def doSpillToSymbol(self, r, s):
        self.asmFile.write(f"; spill register {r} to var {s.name}\n")
        if isinstance(s.impl, StackAddress):
            offset = s.impl.offset
            if s.type == 'char':
                self.asmFile.write(f"\tld\t(ix + {offset}), {r}\n")
            if s.type == 'int':
                self.asmFile.write(f"\tld\t(ix + {offset+1}), {r[0]}\n")
                self.asmFile.write(f"\tld\t(ix + {offset}), {r[1]}\n")
        elif isinstance(s.impl, PointerAddress):
            pointer = s.impl.pointer
            if s.type == 'char':
                self.asmFile.write(f"\tld\t({s.name}), {r}\n")
            if s.type == 'int':
                self.asmFile.write(f"\tld\t({pointer+1}), {r[0]}\n")
                self.asmFile.write(f"\tld\t({pointer}), {r[1]}\n")


    # E.g. ld a, (de)
    def writeAsmLoadRegisterFromPointer(self, r, rp, pointer):
        if len(r) == 1:
            self.asmFile.write(f'\tld\t{r}, ({rp})\n')
        elif len(r) == 2:
            self.asmFile.write(f'\tld\t{r[1]}, ({rp})\n')
            self.asmFile.write(f'\tinc\t{rp}\n')
            self.asmFile.write(f'\tld\t{r[0]}, ({rp})\n')
            if self.currentInstruction.live[pointer]:
                self.asmFile.write(f'\tdec\t{rp}\n')
            else:
                self.removeSymbolForRegister(pointer, rp)

    def loadInA(self, address):
        return self.doLoadInRegister8(address, { "a" } )

    def loadInHL(self, address):
        return self.doLoadInRegister16(address, { "hl" })

    def doLoadInRegister8(self, address, possibleRegisters):
        return self.doLoadInRegister(address, possibleRegisters, { "a", "b", "c", "d", "e", "h", "l" }, { "bc", "de", "hl" })

    def doLoadInRegister16(self, address, possibleRegisters):
        return self.doLoadInRegister(address, possibleRegisters, { "bc", "de", "hl" }, { "bc", "de", "hl" })

    def doLoadInRegister(self, address, possibleRegisters, allRegisters, allPointerRegisters):
        if isinstance(address, Constant):
            regX = self.getTemporaryRegister(possibleRegisters)
            self.asmFile.write(f'\tld\t{regX}, {address.value}\n')
            return regX
        elif isinstance(address.impl, PointerAddress):
            regY = self.isInRegister(address.impl.pointer, allPointerRegisters)
            regX = self.decideRegisterForSymbol(address, possibleRegisters)
            if not regY:
                # Don't use the register we will load to
                regY = self.getRegisterForSymbol(address.impl.pointer, allPointerRegisters - { regX })
                self.asmWriter.loadRegisterWithAddress(regY, address.impl.pointer.impl)
                self.loadSymbolInRegister(address.impl.pointer, regY)
            # Are we loading from the same register that we're loading from?
            # Copy the pointer to a different register
            # (It is common that the pointer is already in HL and that we must load into HL)
            elif regX == regY:
                regY2 = self.getRegisterForSymbol(address.impl.pointer, allPointerRegisters - { regX } )
                self.asmWriter.loadRegisterWithRegister(regY2, regY)
                self.loadSymbolInRegister(address, regY2)
                regY = regY2
            # We decided on regX above, now get it for real, spilling if needed
            regX = self.getRegisterForSymbol(address, { regX } )
            # ld regX, (regY)
            self.writeAsmLoadRegisterFromPointer(regX, regY, address.impl.pointer)
            self.loadSymbolInRegister(address, regX)
            return regX
        else:
            regY = self.isInRegister(address, possibleRegisters)
            if regY:
                return regY
            regX = self.getRegisterForSymbol(address, possibleRegisters)
            regY = self.isInRegister(address, allRegisters )
            if regY:
                self.asmWriter.loadRegisterWithRegister(regX, regY)
            else:
                self.asmWriter.loadRegisterWithAddress(regX, address.impl)
            # self.loadSymEntryInRegister(address, regX)
            self.loadSymbolInRegister(address, regX)
            return regX

