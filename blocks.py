from pprint import pformat
from symbolTable import *

class BasicBlock:
    def __init__(self, name):
        self.statements = []
        # TODO rename to e.g. symbols?
        self.symbolTable = None
        self.name = name

    def __repr__(self):
        return f"Symbol table: {self.symbolTable}\nStatements:\n{pformat(self.statements)}\n\n"

class BlockFactory:
    def __init__(self):
        self.basicBlocks = {}
        self.blockPrefix = None

    def enterBlock(self, name):
        self.currentBlockName = name
        self.blockPrefix = name
        self.blockNumber = 0
        self.enterSubBlock()

    def enterSubBlock(self):
        self.currentBlockName = f"{self.blockPrefix}_{self.blockNumber:04}"
        self.currentBlock = BasicBlock(self.currentBlockName)
        self.blockNumber+=1

    def exitBlock(self, allSymbols):
        self.currentBlock.symbolTable = allSymbols
        self.basicBlocks[self.currentBlockName] = self.currentBlock

    def blocks(self):
        return self.basicBlocks

    def addIR(self, ir):
        self.currentBlock.statements.append(ir)

class SingleBlockFactory:
    def __init__(self):
        self.block = BasicBlock("block")

    def addIR(self, ir):
        self.block.statements.append(ir)

    def blocks(self):
        return { self.block.name: self.block }

