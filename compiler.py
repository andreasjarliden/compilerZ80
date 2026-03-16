from ir import IR_FUNCTIONS
from symEntry import StackAddress
from astnodes import ASTContext
import ir
from blocks import BlockFactory
from symbolTable import SymbolTable
import registerAllocator
from collections import namedtuple

def astToThreeCode(ast, factory = BlockFactory(), symbolTable = SymbolTable()):
    context = ASTContext(factory, symbolTable)
    for n in ast:
        n.visit(context)
    return context.blockFactory.blocks()

def mapSymbols():
    for f in IR_FUNCTIONS:
        symbolTable = f.symbolTable
        # stack pointer points to last byte written, so first variable starts at one byte below SP
        offset = 0
        for symbol in symbolTable.values():
            if not symbol.impl:
                offset -= symbol.size
                symbol.impl = StackAddress(offset)

def updateLive(blocks):
    for b in blocks.values():
        vars = [ s.name for s in b.symbolTable.values() ]
        live = { v: not v.startswith("temp") for v in vars }
        for i in reversed(b.statements):
            # i.live = live.copy()
            i.updateLive(live)

def genCode(blocks):
    ir.asmFile.write("\t.org 08000h\n")
    ir.asmFile.write('\t#include "constants.asm"\n')
    ir.asmFile.write('\tjp\tmain\n')
    for b in blocks.values():
        print(f"\nBasic Block {b.name}\n")
        ir.asmFile.write(f'; Basic Block {b.name}\n')
        registerAllocator.RA = registerAllocator.Z80RegisterAllocator(ir.asmFile, b.symbolTable)
        for i in b.statements:
            registerAllocator.RA.currentInstruction = i
            i.genCode()
        # Spill everything live that is only in a register at the end of the block
        registerAllocator.RA.spillAll()
    ir.asmFile.write('\n\t#include "libc.asm"\n')

