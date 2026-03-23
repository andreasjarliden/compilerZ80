import unittest
from io import StringIO
from symEntry import *
from address import *
from asmWriter import AsmWriter
from ir import *

RA = None
ALL_REGISTERS = {'a', 'b', 'c', 'd', 'e', 'h', 'l', 'bc', 'de', 'hl'}

class RegisterAllocator:
    def __init__(self, symbolTable):
        addresses = symbolTable.keys()
        self.symbolTable = symbolTable
        self.registers = {r: set() for r in ALL_REGISTERS}
        self.registers2 = {r: set() for r in ALL_REGISTERS}
        self.addresses = {a: {a} for a in addresses}
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
        return f"registers: {self.registers}\nfree registers: {self.freeRegisters}\naddresses: {self.addresses}\nsymbol table: {self.symbolTable}"

    def doSpill(self, reg, name):
        pass

    def doSpillToSymbol(self, reg, s):
        pass

    def _isFree(self, r):
        if self.registers[r]:
            return False
        for cr in self.coupledRegisters.get(r, ()):
            if self.registers[cr]:
                return False
        return True

    def _isFree2(self, r):
        if self.registers2[r]:
            return False
        for cr in self.coupledRegisters.get(r, ()):
            if self.registers2[cr]:
                return False
        return True

    @property
    def freeRegisters(self):
        free = []
        for r in self.registers:
            if self._isFree(r):
                free.append(r)
        return set(free)

    @property
    def freeRegisters2(self):
        free = []
        for r in self.registers2:
            if self._isFree2(r):
                free.append(r)
        return set(free)

    # TODO this spills even if the name is available in a different register.
    # Sometimes we want that (e.g. when spilling at end of block) but not
    # otherwise.
    def spillRegister(self, r):
        # Remove register from all addresses
        for n in self.registers[r]:
            self.addresses[n].remove(r)
            self.addresses[n].add(n)
            if self.currentInstruction.live[n]:
                self.doSpill(r, n)
        # Register no longer contains anything
        self.registers[r] = set()

    def spillRegister2(self, r):
        # Remove register from all addresses
        for s in self.registers2[r]:
            self.symbols[s].remove(r)
            self.symbols[s].add(s)
            # TODO use symbol instead of name for live
            if self.currentInstruction.live[s.name]:
                self.doSpillToSymbol(r, s)
        # Register no longer contains anything
        self.registers2[r] = set()

    def spillRegisterToSymbol(self, r, s):
        self.symbols[s].add(s)
        self.symbols[s].remove(r)
        self.doSpillToSymbol(r, s)
        self.registers2[r] = set()

    def removeNameForRegister(self, n, r):
        self.registers[r].remove(n)
        self.addresses[n].remove(r)

    def removeName(self, n):
        registers = self.addresses[n] & ALL_REGISTERS;
        for r in registers:
            self.registers[r].remove(n)
        self.addresses[n] = set()

    def _spillScore(self, r):
        score = 0
        # TODO also handle coupled registers
        for n in self.registers[r]:
            # If n is in some other register. Consider it free to spill.
            # (disregard if we have different groups of registers)
            if len(self.addresses[n]) > 1:
                continue
            # # Is n what we are assigning to? In that case free to spill TODO
            # # maybe not needed as we always have to load the lhs in A or HL
            # if n == ir.resultAddr.name:
            #     continue
            # Is dead?
            if not self.currentInstruction.live[n]:
                continue
            # Have to spill to n
            score += 1
        return score

    def _spillScore2(self, r):
        score = 0
        # TODO also handle coupled registers
        for s in self.registers2[r]:
            # If s is in some other register. Consider it free to spill.
            # (disregard if we have different groups of registers)
            if len(self.symbols[s]) > 1:
                continue
            # # Is s what we are assigning to? In that case free to spill TODO
            # # maybe not needed as we always have to load the lhs in A or HL
            # if n == ir.resultAddr.name:
            #     continue
            # Is dead?
            # TODO use symbols instead of name
            if not self.currentInstruction.live[s.name]:
                continue
            # Have to spill to n
            score += 1
        return score

    # TODO remove
    def spillName(self, n):
        if self.currentInstruction.live[n] and n not in self.addresses[n]:
            # pick one of register contining n
            r = next(iter(self.addresses[n]))
            # TODO if r contains two names, might it needlessly spill?
            print(f"spillRegister({r})")
            self.spillRegister(r)

    def spillSymbol(self, s):
        # TODO: This should use the symbol instead of name
        if self.currentInstruction.live[s.name] and s not in self.symbols[s]:
            # pick one of register contining n
            r = next(iter(self.symbols[s]))
            self.spillRegisterToSymbol(r, s)

    def spillAll(self):
        for n in self.addresses:
            self.spillName(n)

    def spillAllMatchingType(self, t):
        for n, s in self.symbolTable.items():
            if s.completeType == t:
                self.spillName(n)

    def spillAllMatchingType2(self, t):
        for s in self.symbols.keys():
            if s.completeType == t:
                self.spillSymbol(s)
            
    def _bestRegisterToSpill(self, possibleRegisters):
        return min(possibleRegisters, key=self._spillScore)

    def _bestRegisterToSpill2(self, possibleRegisters):
        return min(possibleRegisters, key=self._spillScore2)

    # Like getRegisterForArg but doesn't spill
    def decideRegisterForArg(self, name, possibleRegisters):
        # Already loaded?
        regs = self.addresses[name] & possibleRegisters
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
    def getRegisterForArg(self, name, possibleRegisters):
        # Already loaded?
        regs = self.addresses[name] & possibleRegisters
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

    # TODO this does not register the name as loaded in the register, maybe it
    # should. Maybe this should be private and there should be public version
    # that does all.
    def getRegisterForSymbol(self, symbol, possibleRegisters):
        # Already loaded?
        regs = self.symbols.get(symbol, set()) & possibleRegisters
        if regs:
            return regs.pop()
        # No, pick one of the free registers
        regs = self.freeRegisters2 & possibleRegisters
        if regs:
            return regs.pop()
        # No free, have to spill
        r = self._bestRegisterToSpill2(possibleRegisters)
        self.spillRegister2(r)
        # Spill any coupled register, e.g. spilling bc means also spilling b and c (if loaded). 
        for cr in self.coupledRegisters.get(r, ()):
            self.spillRegister2(cr)
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

    def isInRegister(self, name, possibleRegisters = ALL_REGISTERS):
        # Already loaded?
        regs = self.addresses[name] & possibleRegisters
        if regs:
            return regs.pop()
        else:
            return None

    # Note: This doesn't handle any spilling. r is assumed to be free.
    def loadNameInRegister(self, n, r):
        self.addresses[n].add(r)
        self.registers[r].add(n)

    def loadSymbolInRegister(self, s, r):
        self.symbols.setdefault(s, set())
        self.symbols[s].add(r)
        self.symbols[s].add(s)
        self.registers2[r].add(s)

    # Example: LD (ix+n), a
    def storeToName(self, n):
        self.addresses[n].add(n)

    # Example: LD (ix+n), a
    def storeToSymbol(self, s):
        self.symbols.setdefault(s, set())
        self.symbols[s].add(s)

    # Assigning to a name means that it is only the register that holds the
    # name, it has not been spilled to memory yet.
    def assignToNameWithRegister(self, n, r):
        self.registers[r].add(n)
        self.addresses[n] = { r }

    # Assigning to a name means that it is only the register that holds the
    # name, it has not been spilled to memory yet.
    def assignToSymbolWithRegister(self, s, r):
        self.symbols[s] = { r }
        self.registers2[r].add(s)


class Z80RegisterAllocator(RegisterAllocator):
    def __init__(self, asmFile, symbolTable):
        super().__init__(symbolTable)
        self.asmFile = asmFile
        self.asmWriter = AsmWriter(asmFile)

    def doSpill(self, r, name):
        self.asmFile.write(f"; spill register {r} to var {name}\n")
        offset = self.symbolTable[name].impl.offset
        if self.symbolTable[name].type == 'char':
            self.asmFile.write(f"\tld\t(ix + {offset}), {r}\n")
        if self.symbolTable[name].type == 'int':
            self.asmFile.write(f"\tld\t(ix + {offset+1}), {r[0]}\n")
            self.asmFile.write(f"\tld\t(ix + {offset}), {r[1]}\n")

    def doSpillToSymbol(self, r, s):
        self.asmFile.write(f"; spill register {r} to var {s.name}\n")
        offset = s.impl.offset
        if s.type == 'char':
            self.asmFile.write(f"\tld\t(ix + {offset}), {r}\n")
        if s.type == 'int':
            self.asmFile.write(f"\tld\t(ix + {offset+1}), {r[0]}\n")
            self.asmFile.write(f"\tld\t(ix + {offset}), {r[1]}\n")


    # E.g. ld a, (de)
    def writeAsmLoadRegisterFromPointer(self, r, rp, pointerName):
        if len(r) == 1:
            self.asmFile.write(f'\tld\t{r}, ({rp})\n')
        elif len(r) == 2:
            self.asmFile.write(f'\tld\t{r[1]}, ({rp})\n')
            self.asmFile.write(f'\tinc\t{rp}\n')
            self.asmFile.write(f'\tld\t{r[0]}, ({rp})\n')
            if self.currentInstruction.live[pointerName]:
                self.asmFile.write(f'\tdec\t{rp}\n')
            else:
                self.removeNameForRegister(pointerName, rp)

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
            regY = self.isInRegister(address.impl.pointer.name, allPointerRegisters)
            regX = self.decideRegisterForArg(address.name, possibleRegisters)
            if not regY:
                name = address.impl.pointer.name 
                # Don't use the register we will load to
                regY = self.getRegisterForArg(name, allPointerRegisters - { regX })
                self.asmWriter.loadRegisterWithAddress(regY, address.impl.pointer.impl)
                self.loadNameInRegister(name, regY)
            # Are we loading from the same register that we're loading from?
            # Copy the pointer to a different register
            # (It is common that the pointer is already in HL and that we must load into HL)
            elif regX == regY:
                name = address.impl.pointer.name 
                regY2 = self.getRegisterForArg(address.impl.pointer.name, allPointerRegisters - { regX } )
                self.asmWriter.loadRegisterWithRegister(regY2, regY)
                self.loadNameInRegister(address.name, regY2)
                regY = regY2
            # We decided on regX above, now get it for real, spilling if needed
            regX = self.getRegisterForArg(address.name, { regX } )
            # ld regX, (regY)
            self.writeAsmLoadRegisterFromPointer(regX, regY, address.impl.pointer.name)
            self.loadNameInRegister(address.name, regX)
            return regX
        else:
            regY = self.isInRegister(address.name, possibleRegisters)
            if regY:
                return regY
            regX = self.getRegisterForArg(address.name, possibleRegisters)
            regY = self.isInRegister(address.name, allRegisters )
            if regY:
                self.asmWriter.loadRegisterWithRegister(regX, regY)
            else:
                self.asmWriter.loadRegisterWithAddress(regX, address.impl)
            # self.loadSymEntryInRegister(address, regX)
            self.loadNameInRegister(address.name, regX)
            return regX



