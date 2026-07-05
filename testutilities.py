from parser import parser
from lexer import lexer
from compiler import astToThreeCode, genCode, genDataSegment
from asmWriter import AsmWriter
from io import StringIO
from astnodes import ASTContext, updateLiveInBlock
from blocks import SingleBlockFactory
from symbolTable import SymbolTable
from typeEnv import TypeEnv

def compileToBlocks(code, symbolTable = None, typeEnv = None):
    if not symbolTable:
        symbolTable = SymbolTable()
    if not typeEnv:
        typeEnv = TypeEnv()
    lexer.lineno = 1
    ast = parser.parse(code)
    astContext = ASTContext(symbolTable = symbolTable,
                            typeEnv = typeEnv)
    blocks, dataSegment = astToThreeCode(ast, astContext)
    return blocks

def compile(code):
    lexer.lineno = 1
    ast = parser.parse(code)
    astContext = ASTContext()
    blocks, dataSegment = astToThreeCode(ast, astContext)
    asmWriter = AsmWriter(StringIO())
    genCode(blocks, asmWriter)
    genDataSegment(dataSegment, asmWriter)
    asmWriter.seek(0)
    return asmWriter.read()

def compileBlockToIR(code, symbolTable = None, typeEnv = None):
    if not symbolTable:
        symbolTable = SymbolTable()
    if not typeEnv:
        typeEnv = TypeEnv()
    lexer.lineno = 1
    ast = parser.parse(code)
    blockFactory = SingleBlockFactory()
    block = blockFactory.block
    astContext = ASTContext(blockFactory = blockFactory, symbolTable = symbolTable, typeEnv = typeEnv)
    blocks, _ = astToThreeCode(ast, astContext)
    block.exitSymbols = symbolTable.allSymbols()
    updateLiveInBlock(block)
    return block.statements
