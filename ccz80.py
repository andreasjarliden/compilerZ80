from parser import parser
from compiler import astToThreeCode, updateLive, genCode, genDataSegment
from asmWriter import AsmWriter
from astnodes import ASTContext
from symbolTable import SymbolTable
import argparse
import pathlib

argParser = argparse.ArgumentParser()

argParser.add_argument('filename')

if __name__ == '__main__':
    args = argParser.parse_args()
    inputPath = pathlib.Path(args.filename)
    outputPath = inputPath.with_suffix('.asm')

    asmFile = open(outputPath, "w")
    asmWriter= AsmWriter(asmFile)
    symbolTable = SymbolTable()

    inputFile = open(inputPath, "r")

    ast = parser.parse(inputFile.read())
    astContext = ASTContext(symbolTable = symbolTable)
    blocks, dataSegment = astToThreeCode(ast, astContext)
    updateLive(blocks)
    genCode(blocks, asmWriter)
    genDataSegment(dataSegment, asmWriter)
