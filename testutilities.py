from parser import parser
from lexer import lexer
from compiler import astToThreeCode, updateLive, genCode, genDataSegment
from asmWriter import AsmWriter
from io import StringIO
from astnodes import ASTContext
from blocks import SingleBlockFactory
from symbolTable import SymbolTable
from typeEnv import TypeEnv

def compile(code):
    lexer.lineno = 1
    ast = parser.parse(code)
    astContext = ASTContext()
    blocks, dataSegment = astToThreeCode(ast, astContext)
    updateLive(blocks)
    asmWriter = AsmWriter(StringIO())
    genCode(blocks, asmWriter)
    genDataSegment(dataSegment, asmWriter)
    asmWriter.seek(0)
    return asmWriter.read()

def compileBlockToIR(code, symbolTable = SymbolTable(), typeEnv = TypeEnv()):
    lexer.lineno = 1
    ast = parser.parse(code)
    blockFactory = SingleBlockFactory()
    block = blockFactory.block
    astContext = ASTContext(blockFactory = blockFactory, symbolTable = symbolTable, typeEnv = typeEnv)
    blocks, _ = astToThreeCode(ast, astContext)
    block.exitSymbols = symbolTable.allSymbols()
    updateLive(blocks)
    return block.statements
