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

    print("Parsing")
    print("=======")

    ast = parser.parse("""
    char printHex16(int n);
    char printHex8(char n);
    char puts(char* s);
    char foo(char arg1, int arg2) {
        puts("First arg is ");
        printHex8(arg1);
        puts(" Second arg is ");
        printHex16(arg2);
        return arg1;
    }
    char main() {
        foo(1, 2);
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
