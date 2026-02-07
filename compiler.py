from pprint import pprint
from ir import *
from parser import parser, addSymbolEntry, Function, Argument

# Add external functions
addSymbolEntry("printHex16", Function("void", "printHex16", [], [Argument("int", None)]))
addSymbolEntry("printHex16", Function("void", "printHex8", [], [Argument("char", None)]))

print("Parsing")
print("=======")

ast = parser.parse("""
int main() {
    int a;
    int b;
    int* p;
    p=&a;
    p=p+65534;
    *p=8;
    printHex16(b);
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
                symbol.impl = StackVariable(symbol.type, offset)

def genCode():
    asmFile.write("\t.org 08000h\n")
    asmFile.write('\t#include "constants.asm"\n')
    asmFile.write('\tjp\tmain\n')
    for i in IR:
        i.genCode()
    asmFile.write('\n\t#include "libc.asm"\n')

print("AST to 3-code")
print("=============")
astToThreeCode(ast)

print("IR")
print("==")
pprint(IR)

print("IR_FUNCTIONS")
pprint(IR_FUNCTIONS)

print("Mapping symbols");
mapSymbols()

print("IR mapped symbols")
print("=================")
pprint(IR)

genCode()
