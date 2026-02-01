from pprint import pprint
from ir import *
from parser import parser

ast = parser.parse("""
main(char arg1, char arg2) {
    add(1, 2);
    foo();
    PRINT_HEX();
}

add(char a, char b) {
    return 1;
}

r42() {
    return 41;
}

foo() {
    char a;
    char b;
    b=r42();
    a=b+b+1;
    return a+1;
}""") 

print("AST")
pprint(ast)
print()

def astToThreeCode(ast):
    for n in ast:
        n.createIR()

def mapSymbols():
    for f in IR_FUNCTIONS:
        symbolTable = f._symbolTable
        # stack pointer points to last byte written, so first variable starts at one byte below SP
        offset = -1
        for symbol in symbolTable:
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
