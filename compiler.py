from pprint import pprint
from ir import *
from parser import *
import registerAllocator

# Add external functions
addSymbolEntry("printHex16", Function("void", "printHex16", [], [Argument("int", None)]))
addSymbolEntry("printHex16", Function("void", "printHex8", [], [Argument("char", None)]))

print("Parsing")
print("=======")

ast = parser.parse("""
int add(int A, int B) {
    int C;
    C = A + B;
    return C + 1;
}
int foo(int N) {
    return add(N + 1, 2);
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
                symbol.impl = StackVariable(offset)

def determineNextUse():
    for b in BASIC_BLOCKS.values():
        for s in b.symbolTable.values():
            s.initLive()
        for i in reversed(b.statements):
            i.updateLive(b.symbolTable)

RA = None
def genCode():
    asmFile.write("\t.org 08000h\n")
    asmFile.write('\t#include "constants.asm"\n')
    asmFile.write('\tjp\tmain\n')
    for b in BASIC_BLOCKS.values():
        registerAllocator.RA = registerAllocator.Z80RegisterAllocator(asmFile, b.symbolTable)
        for i in b.statements:
            i.genCode()
    asmFile.write('\n\t#include "libc.asm"\n')

print("AST to 3-code")
print("=============")
astToThreeCode(ast)
determineNextUse()

print("BASIC_BLOCKS")
pprint(BASIC_BLOCKS)

print("IR_FUNCTIONS")
pprint(IR_FUNCTIONS)

print("Mapping symbols");
mapSymbols()

print("IR mapped symbols")
print("=================")
pprint(BASIC_BLOCKS)

genCode()
