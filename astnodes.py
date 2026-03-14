from dataclasses import dataclass
from typing import Any
from ir import *

# Stack of symbol tables
ENV = [ {} ]
FUNCTION = None
FUNCTION_LABELS = 0

# TODO create real SymbolTable class
def addSymbol(t, completeType, name):
    entry = SymEntry(t, completeType, name)
    ENV[-1][name] = entry
    return entry
def addSymbolEntry(name, entry):
    ENV[-1][name] = entry
def enterFunction(name):
    global FUNCTION
    global FUNCTION_LABELS
    ENV.append({})
    FUNCTION = name
    FUNCTION_LABELS = 0
def exitFunction():
    global FUNCTION
    ENV.pop()
    FUNCTION = None
def currentSymbolTable():
    return ENV[-1]
def addTemporary(t, completeType):
    temp = Temporary(t)
    return addSymbol(t, completeType, temp.name)
def createLabel():
    global FUNCTION
    global FUNCTION_LABELS
    FUNCTION_LABELS += 1
    return f"{FUNCTION}_l{FUNCTION_LABELS}"

class Argument:
    def __init__(self, t, name):
        if t == "char" or t == "int":
            self.type = t
        elif t[0] == "*":
            # Pointers are handled as int
            self.type = "int"
        self.completeType = t
        self.name = name

    def __repr__(self):
        return f"Argument {self.type} {self.name}"

class Function:
    def __init__(self, t, name, statements, arguments=[]):
        self.type = t
        self.name = name
        self.statements = statements
        self.arguments = arguments
        addSymbolEntry(name, self)

    def __repr__(self):
        return "Function " + self.name + " with statements " + str(self.statements)

    def visit(self, context):
        enterFunction(self.name)
        context.blockFactory.enterBlock(self.name, currentSymbolTable())
        # return address is at ix+2, ix+3. Rightmost argument (16-bit) is at ix+5, ix+4
        # If pushing AF, then A is at ix+5
        offset = 4
        for a in reversed(self.arguments):
            symEntry = SymEntry(a.type, a.completeType, a.name)
            if a.type == "int":
                symEntry.impl = StackAddress(offset)
            elif a.type == "char":
                # 8 bit values are sent in the high byte
                symEntry.impl = StackAddress(offset+1)
            else:
                error()
            addSymbolEntry(a.name, symEntry)
            offset+=2
        context.blockFactory.addIR(IRDefFun(self, currentSymbolTable()))
        for s in self.statements:
            s.visit(context)
        context.blockFactory.addIR(IRFunExit(self, currentSymbolTable()))
        exitFunction()
        context.blockFactory.exitBlock()

@dataclass(frozen=True)
class If:
    expr : Any
    statements : list

    def visit(self, context):
        print(f"If.visit: expr {self.expr}")
        skipLabel = createLabel()
        if isinstance(self.expr, Variable):
            exprAddr = self.expr.visit(context)
            ir = IRIfVariable(exprAddr, skipLabel)
        elif isinstance(self.expr, Relation):
            print("Creating IRIfRelation")
            (lhsAddr, rhsAddr) = self.expr.visit(context)
            ir = IRIfRelation(self.expr.operation, lhsAddr, rhsAddr, skipLabel)
        else:
            error()
        context.blockFactory.addIR(ir)
        context.blockFactory.exitBlock()
        context.blockFactory.enterSubBlock(currentSymbolTable())
        for s in self.statements:
            s.visit(context)
        context.blockFactory.exitBlock()
        context.blockFactory.enterSubBlock(currentSymbolTable())
        context.blockFactory.addIR(IRLabel(skipLabel))

class VariableDefinition:
    def __init__(self, t, name):
        if t == "char" or t == "int":
            self.type = t
        elif t[0] == "*":
            # Pointers are handled as int
            self.type = "int"
        self.completeType = t
        self.name = name

    def __repr__(self):
        return f"variable definition {self.type} {self.name}"

    def visit(self, context):
        addSymbol(self.type, self.completeType, self.name)
        pass

class VariableAssignment:
    def __init__(self, lvalue, rhs):
        self.lvalue = lvalue
        self.rhs = rhs;

    def __repr__(self):
        return f"variable assignment {self.lvalue} = {self.rhs}"

    def visit(self, context):
        lvalue = self.lvalue.visit(context)
        print(f"Variable assignment lvalue {lvalue}")
        rhsAddr = self.rhs.visit(context)
        context.blockFactory.addIR(IRAssign(lvalue, rhsAddr))

class DerefPointerAssignment:
    def __init__(self, lvalue, rhs):
        self.lvalue = lvalue
        self.rhs = rhs;

    def __repr__(self):
        return f"Deref pointer assignment *{self.lvalue} = {self.rhs}"

    def visit(self, context):
        lvalue = self.lvalue.visit(context)
        rhsAddr = self.rhs.visit(context)
        context.blockFactory.addIR(IRAssignToPointer(lvalue, rhsAddr, currentSymbolTable()))

class Variable:
    def __init__(self, name):
        self.type = None
        self.completeType = None
        self.name = name

    def __repr__(self):
        return f"<Variable type {self.type} complete type {self.completeType} name {self.name}>"

    def visit(self, context):
        symEntry = currentSymbolTable()[self.name]
        self.type = symEntry.type
        self.completeType = symEntry.completeType
        return currentSymbolTable()[self.name]

class AddressOf:
    def __init__(self, expr):
        self.expr = expr

    def __repr__(self):
        return f"AddressOf {self.expr}"

    def visit(self, context):
        exprAddr = self.expr.visit(context)
        irAddressOf = IRAddressOf(exprAddr, addTemporary("int", "*" + exprAddr.completeType))
        context.blockFactory.addIR(irAddressOf)
        return irAddressOf.resultAddr

class Dereference:
    def __init__(self, expr):
        self.expr = expr

    def __repr__(self):
        return f"Dereference {self.expr}"

    def visit(self, context):
        pointer = self.expr.visit(context)
        print(f"Dereference: created code for pointer receiving {self.expr} address {pointer}")
        ct = pointer.completeType[1:] # remove leading *
        if pointer.completeType.startswith("*"):
            t = "int"
        else:
            t = ct
        deref = IRDereference(pointer, addTemporary(t, ct), currentSymbolTable())
        context.blockFactory.addIR(deref)
        deref.resultAddr.impl = PointerAddress(pointer)
        return deref.resultAddr

class FunctionCall:
    def __init__(self, name, arguments=[]):
        self.name = name
        self.arguments = arguments
        self.storeResult = False
        self.type = currentSymbolTable()[name].type
        print(f"Function call for {name} which is returning {self.type}")

    def __repr__(self):
        return f"call {self.name} with args {self.arguments}"

    def visit(self, context):
        for a in reversed(self.arguments):
            exprAddress = a.visit(context)
            context.blockFactory.addIR(IRArgument(exprAddress))
        if self.storeResult:
            irfuncall = IRFunCall(self.type, self.name, len(self.arguments), addr=addTemporary(self.type, self.type))
            context.blockFactory.addIR(irfuncall)
            return irfuncall.resultAddr
        else:
            irfuncall = IRFunCall(self.type, self.name, len(self.arguments))
            context.blockFactory.addIR(irfuncall)

@dataclass(frozen=True)
class Return:
    expr : Any

    def visit(self, context):
        # Function is in the symbol table above the current one
        t = ENV[-2][FUNCTION].type
        exprAddress = self.expr.visit(context)
        context.blockFactory.addIR(IRReturn(t, exprAddress))

@dataclass(frozen=True)
class Add:
    lhs : Any
    rhs : Any

    def visit(self, context):
        lhsAddr = self.lhs.visit(context)
        rhsAddr = self.rhs.visit(context)
        t = lhsAddr.type # TODO promote
        ct = lhsAddr.completeType
        irAdd = IRAdd(addTemporary(t, ct), lhsAddr, rhsAddr)
        context.blockFactory.addIR(irAdd)
        return irAdd.resultAddr

@dataclass(frozen=True)
class Relation:
    operation : str
    lhs : Any
    rhs : Any

    def visit(self, context):
        return (self.lhs.visit(context), self.rhs.visit(context))


