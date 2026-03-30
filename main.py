from pprint import pprint
import ir
from parser import parser
from symbolTable import SymbolTable
from astnodes import Function, Argument
from compiler import astToThreeCode, updateLive, genCode, genDataSegment
from asmWriter import AsmWriter

if __name__ == "__main__":
    asmFile = open("a.asm", "w")
    asmWriter= AsmWriter(asmFile)

    symbolTable = SymbolTable()
    # Add external functions
    symbolTable.addSymbolEntry("printHex16", Function("void", "printHex16", [], [Argument("int", None)]))
    symbolTable.addSymbolEntry("printHex8", Function("void", "printHex8", [], [Argument("char", None)]))
    symbolTable.addSymbolEntry("printString", Function("void", "printString", [], [Argument("char*", None)]))

    print("Parsing")
    print("=======")

    ast = parser.parse("""
    char* str = "Hello World";
    char main() {
        char* p;
        p = str;
        printString(p);
        }
    """) 

    print("AST")
    print("===")
    pprint(ast)
    print()

    print("AST to 3-code")
    print("=============")
    blocks, dataSegment = astToThreeCode(ast, symbolTable=symbolTable)
    updateLive(blocks)

    print("BASIC_BLOCKS")
    pprint(blocks)

    genCode(blocks, asmWriter)
    genDataSegment(dataSegment, asmWriter)
