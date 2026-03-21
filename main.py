from pprint import pprint
import ir
from parser import parser
from symbolTable import SymbolTable
from astnodes import Function, Argument
from compiler import astToThreeCode, updateLive, genCode
from asmWriter import AsmWriter

if __name__ == "__main__":
    asmFile = open("a.asm", "w")
    asmWriter= AsmWriter(asmFile)

    symbolTable = SymbolTable()
    # Add external functions
    symbolTable.addSymbolEntry("printHex16", Function("void", "printHex16", [], [Argument("int", None)]))
    symbolTable.addSymbolEntry("printHex16", Function("void", "printHex8", [], [Argument("char", None)]))

    print("Parsing")
    print("=======")

    ast = parser.parse("""
    char A;
    char main() {
        A=1;
        }
    """) 

    print("AST")
    print("===")
    pprint(ast)
    print()

    print("AST to 3-code")
    print("=============")
    blocks = astToThreeCode(ast, symbolTable=symbolTable)
    updateLive(blocks)

    print("BASIC_BLOCKS")
    pprint(blocks)

    genCode(blocks, asmWriter)
