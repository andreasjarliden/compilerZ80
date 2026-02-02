from pprint import pprint
from ir import *
from parser import parser

ast = parser.parse("""
main() {
    add(1, add(2, 3));
    PRINT_HEX();
}

add(char a, char b) {
    return a + b;
}

""") 

print("AST")
pprint(ast)
print()

def astToThreeCode(ast):
    for n in ast:
        n.createIR()

def mapSymbols():
    for f in IR_FUNCTIONS:
        symbolTable = f.symbolTable
        # stack pointer points to last byte written, so first variable starts at one byte below SP
        offset = -1
        for symbol in symbolTable:
            if not symbolTable[symbol].impl:
                symbolTable[symbol].impl = StackVariable(offset)
                offset-=1

def genCode():
    asmFile.write("\t.org 08000h\n")
    asmFile.write('\t#include "constants.asm"\n')
    for i in IR:
        i.genCode()

astToThreeCode(ast)

print("IR")
pprint(IR)

print("IR_FUNCTIONS")
pprint(IR_FUNCTIONS)

mapSymbols()

print("\nIR mapped symbols")
pprint(IR)

genCode()
