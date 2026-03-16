from pprint import pprint
import ir
import parser
from compiler import astToThreeCode, updateLive, mapSymbols, genCode
from asmWriter import AsmWriter

asmFile = open("a.asm", "w")
# TODO move the asmFile from IR
ir.asmFile = asmFile
ir.asmWriter = AsmWriter(ir.asmFile)

# Add external functions
# parser.addSymbolEntry("printHex16", parser.Function("void", "printHex16", [], [parser.Argument("int", None)]))
# parser.addSymbolEntry("printHex16", parser.Function("void", "printHex8", [], [parser.Argument("char", None)]))

print("Parsing")
print("=======")

ast = parser.parser.parse("""
char bar(char N) {
    return N + 1;
    }
char foo() {
    char A;
    char B;
    if (2 < 3) {
        A=bar(3);
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
