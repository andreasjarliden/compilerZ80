from pprint import pprint
from ir import *
from parser import parser, addSymbolEntry, Function, Argument

# Add external functions
addSymbolEntry("printHex16", Function("void", "printHex16", [], [Argument(int, None)]))

ast = parser.parse("""
int add(int a, int b) {
    return a+b;
}

int main() {
    int a;
    int b;
    int c;
    a = 65530;
    b = 4;
    c = add(a, b);
    printHex16(c);
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
        offset = 0
        for symbol in symbolTable.values():
            if not symbol.impl:
                offset -= symbol.size
                symbol.impl = StackVariable(offset)

def genCode():
    asmFile.write("\t.org 08000h\n")
    asmFile.write('\t#include "constants.asm"\n')
    asmFile.write('\tjp\tmain\n')
    for i in IR:
        i.genCode()
    asmFile.write('\n\t#include "libc.asm"\n')

astToThreeCode(ast)

print("IR")
pprint(IR)

print("IR_FUNCTIONS")
pprint(IR_FUNCTIONS)

mapSymbols()

print("\nIR mapped symbols")
pprint(IR)

genCode()
