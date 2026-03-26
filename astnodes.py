from dataclasses import dataclass, field
from typing import Any
from ir import *
from symbolTable import *
import symbolTable

@dataclass
class ASTContext:
    blockFactory : Any 
    symbolTable : SymbolTable = SymbolTable()
    functionName : str = None
    dataSegment : list[SymEntry] = field(default_factory=list)

def createLabel(context):
    context.functionLabels += 1
    return f"{context.functionName}_l{context.functionLabels}"

@dataclass(frozen=True)
class Variable:
    name : str

    def visit(self, context):
        return context.symbolTable.lookUp(self.name)

@dataclass(frozen=True)
class Argument:
    completeType : Any
    name : str

    @property
    def type(self):
        if self.completeType[0] == "*":
            # Pointers are handled as int
            return "int"
        else:
            return self.completeType


class Function:
    def __init__(self, t, name, statements, arguments=[]):
        self.type = t
        self.name = name
        self.statements = statements
        self.arguments = arguments

    def __repr__(self):
        return "Function " + self.name + " with statements " + str(self.statements)

    def mapSymbols(symbolTable):
        # stack pointer points to last byte written, so first variable starts at one byte below SP
        offset = 0
        for symbol in symbolTable.values():
            if not symbol.impl:
                offset -= symbol.size
                symbol.impl = StackAddress(offset)

    def visit(self, context):
        context.symbolTable.addSymbolEntry(self.name, self)
        context.symbolTable.pushFrame()
        context.functionName = self.name
        context.functionLabels = 0
        # context.blockFactory.enterBlock(self.name, context.symbolTable.allSymbols())
        context.blockFactory.enterBlock(self.name)
        # return address is at ix+2, ix+3. Rightmost argument (16-bit) is at ix+5, ix+4
        # If pushing AF, then A is at ix+5
        offset = 4
        for a in reversed(self.arguments):
            symEntry = SymEntry(a.completeType, a.name)
            if a.type == "int":
                symEntry.impl = StackAddress(offset)
            elif a.type == "char":
                # 8 bit values are sent in the high byte
                symEntry.impl = StackAddress(offset+1)
            else:
                error()
            context.symbolTable.addSymbolEntry(a.name, symEntry)
            offset+=2
        symbolTable = context.symbolTable.currentSymbolTable()
        frameSize = stackFrameSize(symbolTable)
        context.blockFactory.addIR(IRDefFun(self, frameSize))
        for s in self.statements:
            s.visit(context)
        Function.mapSymbols(symbolTable)
        hasStackFrame = len(symbolTable) > 0
        context.blockFactory.addIR(IRFunExit(self, hasStackFrame))
        print(f"At end of block, {context.symbolTable.allSymbols()=}")
        context.blockFactory.exitBlock(context.symbolTable.allSymbols())
        context.symbolTable.popFrame()
        context.functionName = None

@dataclass(frozen=True)
class If:
    expr : Any
    statements : list

    def visit(self, context):
        skipLabel = createLabel(context)
        if isinstance(self.expr, Variable):
            exprAddr = self.expr.visit(context)
            ir = IRIfVariable(exprAddr, skipLabel)
        elif isinstance(self.expr, Relation):
            (lhsAddr, rhsAddr) = self.expr.visit(context)
            ir = IRIfRelation(self.expr.operation, lhsAddr, rhsAddr, skipLabel)
        else:
            error()
        context.blockFactory.addIR(ir)
        context.blockFactory.exitBlock()
        context.blockFactory.enterSubBlock(context.symbolTable.currentSymbolTable())
        for s in self.statements:
            s.visit(context)
        context.blockFactory.exitBlock()
        context.blockFactory.enterSubBlock(context.symbolTable.currentSymbolTable())
        context.blockFactory.addIR(IRLabel(skipLabel))

@dataclass(frozen=True)
class VariableDefinition:
    completeType : Any
    name : str

    @property
    def type(self):
        if self.completeType[0] == "*":
            # Pointers are handled as int
            return "int"
        else:
            return self.completeType

    def visit(self, context):
        symbol = SymEntry(self.completeType, self.name)
        context.symbolTable.addSymbolEntry(self.name, symbol)
        if not context.functionName:
            # Handle global variables as PointerAddresses
            symbol.impl = PointerAddress(None)
            context.dataSegment.append(symbol)


@dataclass(frozen=True)
class VariableAssignment:
    lvalue : Any
    rhs : Any

    def visit(self, context):
        lvalue = self.lvalue.visit(context)
        rhsAddr = self.rhs.visit(context)
        context.blockFactory.addIR(IRAssign(lvalue, rhsAddr))

@dataclass(frozen=True)
class DerefPointerAssignment:
    lvalue : Any
    rhs : Any

    def visit(self, context):
        lvalue = self.lvalue.visit(context)
        rhsAddr = self.rhs.visit(context)
        context.blockFactory.addIR(IRAssignToPointer(lvalue, rhsAddr))


@dataclass(frozen=True)
class AddressOf:
    expr : Any

    def visit(self, context):
        exprAddr = self.expr.visit(context)
        irAddressOf = IRAddressOf(exprAddr, addTemporary("int", "*" + exprAddr.completeType))
        context.blockFactory.addIR(irAddressOf)
        return irAddressOf.resultAddr

@dataclass(frozen=True)
class Dereference:
    expr : Any

    def visit(self, context):
        pointer = self.expr.visit(context)
        ct = pointer.completeType[1:] # remove leading *
        if pointer.completeType.startswith("*"):
            t = "int"
        else:
            t = ct
        deref = IRDereference(pointer, addTemporary(t, ct))
        context.blockFactory.addIR(deref)
        deref.resultAddr.impl = PointerAddress(pointer)
        return deref.resultAddr

class FunctionCall:
    def __init__(self, name, arguments=[]):
        self.name = name
        self.arguments = arguments
        self.storeResult = False

    def __repr__(self):
        return f"call {self.name} with args {self.arguments}"

    def visit(self, context):
        self.type = context.symbolTable.lookUp(self.name).type
        for a in reversed(self.arguments):
            exprAddress = a.visit(context)
            context.blockFactory.addIR(IRArgument(exprAddress))
        if self.storeResult:
            irfuncall = IRFunCall(self.type, self.name, len(self.arguments), addr=context.symbolTable.addTemporary(self.type))
            context.blockFactory.addIR(irfuncall)
            return irfuncall.resultAddr
        else:
            irfuncall = IRFunCall(self.type, self.name, len(self.arguments))
            context.blockFactory.addIR(irfuncall)

@dataclass(frozen=True)
class Return:
    expr : Any

    def visit(self, context):
        t = context.symbolTable.lookUp(context.functionName).type
        exprAddress = self.expr.visit(context)
        context.blockFactory.addIR(IRReturn(t, exprAddress, context.functionName))

@dataclass(frozen=True)
class Add:
    lhs : Any
    rhs : Any

    def visit(self, context):
        lhsAddr = self.lhs.visit(context)
        rhsAddr = self.rhs.visit(context)
        ct = lhsAddr.completeType
        irAdd = IRAdd(context.symbolTable.addTemporary(ct), lhsAddr, rhsAddr)
        context.blockFactory.addIR(irAdd)
        return irAdd.resultAddr

@dataclass(frozen=True)
class Relation:
    operation : str
    lhs : Any
    rhs : Any

    def visit(self, context):
        return (self.lhs.visit(context), self.rhs.visit(context))


