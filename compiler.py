from astnodes import ASTContext
from blocks import BlockFactory
from symbolTable import SymbolTable
from astnodes import String
import registerAllocator

def astToThreeCode(ast, factory = BlockFactory(), symbolTable = SymbolTable()):
    context = ASTContext(factory, symbolTable)
    for n in ast:
        n.visit(context)
    return context.blockFactory.blocks(), context.dataSegment

def updateLive(blocks):
    for b in blocks.values():
        live = { s: not s.name.startswith("temp") for s in b.exitSymbols}
        for i in reversed(b.statements):
            i.updateLive(live)

def genCode(blocks, asmWriter):
    asmWriter.write("\t.org 08000h\n")
    asmWriter.write('\t#include "constants.asm"\n')
    asmWriter.write('\tjp\tmain\n')
    for b in blocks.values():
        asmWriter.write(f'; Basic Block {b.name}\n')
        registerAllocator.RA = registerAllocator.Z80RegisterAllocator(asmWriter)
        for i in b.statements:
            registerAllocator.RA.currentInstruction = i
            i.genCode(asmWriter)
            registerAllocator.RA.verify()
        # Spill everything live that is only in a register at the end of the block
        registerAllocator.RA.spillAll()
    asmWriter.write('\n\t#include "libc.asm"\n')

C_TO_ASM_MAPPING = { "char": "int8",
                     "int": "int16" }

def genDataSegment(dataSegment, asmWriter):
    asmWriter.write("\n\n")
    for s, v in dataSegment.items():
        if isinstance(v, String):
            asmWriter.write(f'{s.name}:\t.string\t"{v.string}\\0"\n')
        else:
            asmWriter.write(f"{s.name}:\t.{C_TO_ASM_MAPPING[s.completeType]}\t{v}\n")

