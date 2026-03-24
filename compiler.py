from symEntry import StackAddress
from astnodes import ASTContext
from blocks import BlockFactory
from symbolTable import SymbolTable
import registerAllocator

def astToThreeCode(ast, factory = BlockFactory(), symbolTable = SymbolTable()):
    context = ASTContext(factory, symbolTable)
    for n in ast:
        n.visit(context)
    return context.blockFactory.blocks()

def updateLive(blocks):
    for b in blocks.values():
        vars = [ s.name for s in b.symbolTable.values() ]
        live = { v: not v.startswith("temp") for v in vars }
        for i in reversed(b.statements):
            # i.live = live.copy()
            i.updateLive(live)

def genCode(blocks, asmWriter):
    asmWriter.write("\t.org 08000h\n")
    asmWriter.write('\t#include "constants.asm"\n')
    asmWriter.write('\tjp\tmain\n')
    for b in blocks.values():
        print(f"\nBasic Block {b.name}\n")
        asmWriter.write(f'; Basic Block {b.name}\n')
        registerAllocator.RA = registerAllocator.Z80RegisterAllocator(asmWriter)
        for i in b.statements:
            registerAllocator.RA.currentInstruction = i
            i.genCode(asmWriter)
        # Spill everything live that is only in a register at the end of the block
        registerAllocator.RA.spillAll()
    asmWriter.write('\n\t#include "libc.asm"\n')

