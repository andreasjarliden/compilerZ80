from pprint import pprint
import ir
# from ir import *
from parser import *
import registerAllocator

asmFile = open("a.asm", "w")
ir.asmFile = asmFile
ir.asmWriter = AsmWriter(ir.asmFile)

# Add external functions
addSymbolEntry("printHex16", Function("void", "printHex16", [], [Argument("int", None)]))
addSymbolEntry("printHex16", Function("void", "printHex8", [], [Argument("char", None)]))

print("Parsing")
print("=======")

ast = parser.parse("""
char foo() {
    char A;
    char B;
    A=2;
    B=A+1;
    }
""") 

print("AST")
print("===")
pprint(ast)
print()

def astToThreeCode(ast):
    for n in ast:
        n.visit()

def mapSymbols():
    for f in IR_FUNCTIONS:
        symbolTable = f.symbolTable
        # stack pointer points to last byte written, so first variable starts at one byte below SP
        offset = 0
        for symbol in symbolTable.values():
            if not symbol.impl:
                offset -= symbol.size
                symbol.impl = StackAddress(offset)

def updateLive():
    for b in BASIC_BLOCKS.values():
        vars = [ s.name for s in b.symbolTable.values() ]
        live = { v: not v.startswith("temp") for v in vars }
        for i in reversed(b.statements):
            i.live = live.copy()
            i.updateLive(live)

RA = None
def genCode():
    asmFile.write("\t.org 08000h\n")
    asmFile.write('\t#include "constants.asm"\n')
    asmFile.write('\tjp\tmain\n')
    for b in BASIC_BLOCKS.values():
        print(f"\nBasic Block {b.name}\n")
        asmFile.write(f'; Basic Block {b.name}\n')
        registerAllocator.RA = registerAllocator.Z80RegisterAllocator(asmFile, b.symbolTable)
        for i in b.statements:
            registerAllocator.RA.currentInstruction = i
            i.genCode()
        # Spill everything live that is only in a register at the end of the block
        registerAllocator.RA.spillAll()
    asmFile.write('\n\t#include "libc.asm"\n')

print("AST to 3-code")
print("=============")
astToThreeCode(ast)
updateLive()

print("BASIC_BLOCKS")
pprint(BASIC_BLOCKS)

# print("IR_FUNCTIONS")
# pprint(IR_FUNCTIONS)

print("Mapping symbols");
mapSymbols()

print("IR mapped symbols")
print("=================")
pprint(BASIC_BLOCKS)
print()

genCode()
