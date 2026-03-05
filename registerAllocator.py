import unittest
from io import StringIO
from symEntry import *
from address import *
from asmWriter import AsmWriter
from ir import *

RA = None
ALL_REGISTERS = {'a', 'b', 'c', 'd', 'e', 'h', 'l', 'bc', 'de', 'hl'}

class RegisterAllocator:
    def __init__(self, addresses):
        self.registers = {r: set() for r in ALL_REGISTERS}
        self.addresses = {a: {a} for a in addresses}
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
        return f"registers: {self.registers}\nfree registers: {self.freeRegisters}\naddresses: {self.addresses}"

    def doSpill(self, reg, name):
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

    # TODO this spills even if the name is available in a different register.
    # Sometimes we want that (e.g. when spilling at end of block) but not
    # otherwise.
    def spillRegister(self, r):
        # Remove register from all addresses
        for n in self.registers[r]:
            if self.currentInstruction.live[n]:
                self.addresses[n].remove(r)
                self.addresses[n].add(n)
                self.doSpill(r, n)
        # Register no longer contains anything
        self.registers[r] = set()

    def removeNameForRegister(self, n, r):
        self.registers[r].remove(n)
        self.addresses[n].remove(r)

    def spillScore(self, r):
        score = 0
        print(f"Determining spill Score for {r} with live {self.currentInstruction.live}")
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

    def spillName(self, n):
        print(f"spillName {n} isLive {self.currentInstruction.live[n]} and addresses {self.addresses[n]}")
        if self.currentInstruction.live[n] and n not in self.addresses[n]:
            # pick one of register contining n
            r = next(iter(self.addresses[n] - set(n)))
            self.spillRegister(r)

    def spillAll(self):
        for n in self.addresses:
            self.spillName(n)

    def spillAllMatchingType(self, t, symbolTable):
        for n, s in symbolTable.items():
            if s.completeType == t:
                self.spillName(n)
            
    def bestRegisterToSpill(self, possibleRegisters):
        print(f"bestRegisterToSpill possible {possibleRegisters}")
        return min(possibleRegisters, key=self.spillScore)

    def isInRegiser(self, name, possibleRegisters):
        # Already loaded?
        regs = self.addresses[name] & possibleRegisters
        if regs:
            return regs.pop()

    # Like getRegisterForArg but doesn't spill
    def decideRegisterForArg(self, name, possibleRegisters):
        # Already loaded?
        regs = self.addresses[name] & possibleRegisters
        if regs:
            return regs.pop()
        # No, pick one of the free registers
        regs = self.freeRegisters & possibleRegisters
        if regs:
            return regs.pop()
        # No free, have to spill
        return self.bestRegisterToSpill(possibleRegisters)

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
        r = self.bestRegisterToSpill(possibleRegisters)
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
        r = self.bestRegisterToSpill(possibleRegisters)
        self.spillRegister(r)
        # Spill any coupled register, e.g. spilling bc means also spilling b and c (if loaded). 
        for cr in self.coupledRegisters.get(r, ()):
            self.spillRegister(cr)
        return r

    # TODO test
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

    # Example: LD (ix+n), a
    def storeToName(self, n):
        self.addresses[n].add(n)

    # Assigning to a name means that it is only the register that holds the
    # name, it has not been spilled to memory yet.
    def assignToNameWithRegister(self, n, r):
        self.registers[r].add(n)
        self.addresses[n] = { r }


class Z80RegisterAllocator(RegisterAllocator):
    def __init__(self, asmFile, symbolTable):
        super().__init__(symbolTable.keys())
        self.symbolTable = symbolTable
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

    def doLoadInRegister8(self, address, possibleRegisters):
        if isinstance(address, Constant):
            regX = self.getTemporaryRegister(possibleRegisters)
            self.asmFile.write(f'\tld\t{regX}, {address.value}\n')
            return regX
        elif isinstance(address.impl, PointerAddress):
            regY = self.isInRegister(address.impl.pointer.name, { "bc", "de", "hl" })
            if not regY:
                name = address.impl.pointer.name 
                regY = self.getRegisterForArg(name, { "bc", "de", "hl" } )
                self.asmWriter.loadRegisterWithAddress(regY, address.impl.pointer.impl)
                self.loadNameInRegister(name, regY)
            regX = self.getRegisterForArg(address.name, possibleRegisters)
            # ld regX, (regY)
            self.writeAsmLoadRegisterFromPointer(regX, regY, address.impl.pointer.name)
            return regX
        else:
            regY = self.isInRegister(address.name, possibleRegisters)
            if regY:
                return regY
            regX = self.getRegisterForArg(address.name, possibleRegisters)
            regY = self.isInRegister(address.name, { "a", "b", "c", "d", "e", "h", "l" } )
            if regY:
                self.asmWriter.loadRegisterWithRegister(regX, regY)
            else:
                self.asmWriter.loadRegisterWithAddress(regX, address.impl)
            self.loadNameInRegister(address.name, regX)
            return regX

    def doLoadInRegister16(self, address, possibleRegisters):
        # Is constant?
        if isinstance(address, Constant):
            regX = self.getTemporaryRegister(possibleRegisters)
            self.asmFile.write(f'\tld\t{regX}, {address.value}\n')
            return regX
        elif isinstance(address.impl, PointerAddress):
            regY = self.isInRegister(address.impl.pointer.name, { "bc", "de", "hl" })
            # This is the dereferenced address (equal to the ptr for now)
            regX = self.decideRegisterForArg(address.name, possibleRegisters)
            if not regY:
                name = address.impl.pointer.name 
                # Don't use the register we will load to
                regY = self.getRegisterForArg(name, { "bc", "de", "hl" } - { regX })
                self.asmWriter.loadRegisterWithAddress(regY, address.impl.pointer.impl)
                self.loadNameInRegister(name, regY)
            # Are we loading from the same register that we're loading from?
            # Copy the pointer to a different register
            # (It is common that the pointer is already in HL and that we must load into HL)
            elif regX == regY:
                name = address.impl.pointer.name 
                regY2 = self.getRegisterForArg(address.impl.pointer.name, { "bc", "de", "hl" } - { regX } )
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
            if not regY:
                regX = self.getRegisterForArg(address.name, possibleRegisters)
                self.asmWriter.loadRegisterWithAddress(regX, address.impl)
                self.loadNameInRegister(address.name, regX)
                return regX
            return regY

    def loadInHL(self, address):
        return self.doLoadInRegister16(address, { "hl" })


