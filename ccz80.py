from parser import parser
from compiler import astToThreeCode, updateLive, genCode, genDataSegment
from asmWriter import AsmWriter
from astnodes import ASTContext
from symbolTable import SymbolTable
import argparse
import subprocess
from pathlib import Path

argParser = argparse.ArgumentParser()

argParser.add_argument('filename')

def preprocess(file : str | Path):
    path = Path(file)
    result = subprocess.run(["cpp", str(path)],
                            text=True,
                            stdout=subprocess.PIPE,
                            stdin=subprocess.PIPE)
    if result.returncode != 0:
        raise RuntimeError(f"Error invocing cpp: {result.stderr})")

    return result.stdout

if __name__ == '__main__':
    args = argParser.parse_args()
    inputPath = Path(args.filename)
    outputPath = inputPath.with_suffix('.asm')

    asmFile = open(outputPath, "w")
    asmWriter= AsmWriter(asmFile)
    symbolTable = SymbolTable()

    # inputFile = open(inputPath, "r")

    # ast = parser.parse(inputFile.read())
    ast = parser.parse(preprocess(inputPath))
    astContext = ASTContext(symbolTable = symbolTable)
    blocks, dataSegment = astToThreeCode(ast, astContext)
    updateLive(blocks)
    genCode(blocks, asmWriter)
    genDataSegment(dataSegment, asmWriter)
