from symEntry import StackAddress
from astnodes import ASTContext
from blocks import BlockFactory
from symbolTable import SymbolTable
import registerAllocator

def astToThreeCode(ast, factory = BlockFactory(), symbolTable = SymbolTable()):
    context = ASTContext(factory, symbolTable)
    for n in ast:
        n.visit(context)
    return context.blockFactory.blocks(), context.dataSegment
    # return context.blockFactory.blocks()

def updateLive(blocks):
    for b in blocks.values():
        print(f"updateLive {b.name} {b.symbolTable=}")
        live = { s: not s.name.startswith("temp") for s in b.symbolTable}
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
            print(f"In block {registerAllocator.RA.currentInstruction.live=}")
            i.genCode(asmWriter)
        # Spill everything live that is only in a register at the end of the block
        print(f"About to spill at end of block {registerAllocator.RA.currentInstruction.live=}")
        registerAllocator.RA.spillAll()
    asmWriter.write('\n\t#include "libc.asm"\n')

C_TO_ASM_MAPPING = { "char": "int8",
                     "int": "int16" }

def genDataSegment(dataSegment, asmWriter):
    asmWriter.write("\n\n")
    for s in dataSegment:
        asmWriter.write(f"{s.name}:\t.{C_TO_ASM_MAPPING[s.completeType]}\t0\n")

