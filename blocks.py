from pprint import pformat
from symbolTable import *

class BasicBlock:
    def __init__(self, symbolTable, name):
        self.statements = []
        self.symbolTable = symbolTable
        self.name = name

    def __repr__(self):
        return f"Symbol table: {self.symbolTable}\nStatements:\n{pformat(self.statements)}\n\n"

class BlockFactory:
    def __init__(self):
        self.basicBlocks = {}
        self.blockPrefix = None

    def enterBlock(self, name, symbolTable):
        self.currentBlockName = name
        self.blockPrefix = name
        self.blockNumber = 0
        self.enterSubBlock(symbolTable)

    def enterSubBlock(self, symbolTable):
        self.currentBlockName = f"{self.blockPrefix}_{self.blockNumber:04}"
        self.currentBlock = BasicBlock(symbolTable, self.currentBlockName)
        self.blockNumber+=1

    def exitBlock(self):
        self.basicBlocks[self.currentBlockName] = self.currentBlock

    def blocks(self):
        return self.basicBlocks

    def addIR(self, ir):
        self.currentBlock.statements.append(ir)

class SingleBlockFactory:
    def __init__(self, symbolTable):
        self.block = BasicBlock(symbolTable, "block")

    def addIR(self, ir):
        self.block.statements.append(ir)

    def blocks(self):
        return { self.block.name: self.block }

