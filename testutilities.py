
from parser import parser
from lexer import lexer
from compiler import astToThreeCode, updateLive, genCode, genDataSegment
from asmWriter import AsmWriter
from io import StringIO
from astnodes import ASTContext

def compile(code):
    lexer.lineno = 1
    asmWriter = AsmWriter(StringIO())
    ast = parser.parse(code)
    astContext = ASTContext()
    blocks, dataSegment = astToThreeCode(ast, astContext)
    updateLive(blocks)
    genCode(blocks, asmWriter)
    genDataSegment(dataSegment, asmWriter)
    asmWriter.seek(0)
    return asmWriter.read()
