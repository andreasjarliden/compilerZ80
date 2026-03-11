from pprint import pprint
import ir
# from ir import *
from parser import *
from compiler import *
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
    if (2 < 3) {
        A=2;
    }
    }
""") 

print("AST")
print("===")
pprint(ast)
print()

print("AST to 3-code")
print("=============")
blocks = astToThreeCode(ast)
updateLive(blocks)

print("BASIC_BLOCKS")
pprint(blocks)

print("Mapping symbols");
mapSymbols()

print("IR mapped symbols")
print("=================")
pprint(blocks)
print()

genCode(blocks)
