from pprint import pprint
import ir
from parser import parser
from symbolTable import SymbolTable
from astnodes import Function, Argument
from compiler import astToThreeCode, updateLive, genCode, genDataSegment
from asmWriter import AsmWriter
from astnodes import ASTContext

if __name__ == "__main__":
    asmFile = open("a.asm", "w")
    asmWriter= AsmWriter(asmFile)

    symbolTable = SymbolTable()
    # Add external functions
    symbolTable.addSymbolEntry("printHex16", Function("void", "printHex16", [], [Argument("int", None)]))
    symbolTable.addSymbolEntry("printHex8", Function("void", "printHex8", [], [Argument("char", None)]))
    symbolTable.addSymbolEntry("puts", Function("void", "puts", [], [Argument("char*", None)]))

    print("Parsing")
    print("=======")

    ast = parser.parse("""
    char* FOO = "hello";
    char main() {
        FOO = "bar";
        puts(FOO);
        }
    """) 

    print("AST")
    print("===")
    pprint(ast)
    print()

    print("AST to 3-code")
    print("=============")
    astContext = ASTContext(symbolTable = symbolTable)
    blocks, dataSegment = astToThreeCode(ast, astContext)
    updateLive(blocks)

    print("BASIC_BLOCKS")
    pprint(blocks)

    genCode(blocks, asmWriter)
    genDataSegment(dataSegment, asmWriter)
