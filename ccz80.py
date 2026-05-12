from parser import parser
from compiler import astToThreeCode, updateLive, genCode, genDataSegment
from asmWriter import AsmWriter
from astnodes import ASTContext
from symbolTable import SymbolTable
from error import CompileError
import argparse
import subprocess
import sys
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
    asmWriter = AsmWriter(asmFile)

    try:
        ast = parser.parse(preprocess(inputPath))
        symbolTable = SymbolTable()
        astContext = ASTContext(symbolTable = symbolTable)
        blocks, dataSegment = astToThreeCode(ast, astContext)
        updateLive(blocks)
        genCode(blocks, asmWriter)
        genDataSegment(dataSegment, asmWriter)
    except CompileError as e:
        print(f"{e.location.file}:{e.location.line}:{e.message}", file=sys.stderr)
        outputPath.unlink(missing_ok=True)
        sys.exit(1)
