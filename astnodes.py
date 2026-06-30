from dataclasses import dataclass, field
from typing import Any
from ir import *
from symbolTable import *
from blocks import BlockFactory
from error import Location, CompileError
from typeEnv import TypeEnv
from type_defs import StructType, StructField, simpleTypeForComplexType
import symbolTable
import registerAllocator
from copy import copy

class StringTable:
    def __init__(self):
        # String -> name
        self._table = {}
        self._count = 0

    def addString(self, s):
        if not s in self._table:
            self._table[s] = f"__str{self._count}"
            self._count += 1
        return self._table[s]


@dataclass
class ASTContext:
    blockFactory : Any = field(default_factory=BlockFactory)
    symbolTable : SymbolTable = field(default_factory=SymbolTable)
    typeEnv : Any = field(default_factory=TypeEnv)
    functionName : str = None
    dataSegment : dict[SymEntry, Any] = field(default_factory=dict)
    stringTable : StringTable = field(default_factory=StringTable)

    def exitBlock(self):
        self.blockFactory.exitBlock(self.symbolTable.allSymbols())


def createLabel(context):
    context.functionLabels += 1
    return f"{context.functionName}_l{context.functionLabels}"


def promoteIfNeededTo(rhsAddr, toType, toCompleteType, context, operation, location):
    if not isConvertableTo(rhsAddr.completeType, toCompleteType):
        raise CompileError(f"Can't convert {rhsAddr.completeType} to {toCompleteType} in {operation}", location)
    # Only IRPromote if we have to change the simple, concrete type
    if rhsAddr.type != toType:
        temp = context.symbolTable.addTemporary(toCompleteType)
        context.blockFactory.addIR(IRPromote(
            temp,
            rhsAddr,
            toCompleteType))
        return temp
    return rhsAddr

@dataclass(frozen=True)
class ASTNode:
    location : Location = field(default_factory=Location, compare=False, kw_only=True)


@dataclass
class MutableASTNode:
    location : Location = field(default_factory=Location, compare=False, kw_only=True)


@dataclass(frozen=True)
class String(ASTNode):
    string : str


@dataclass(frozen=True)
class Variable(ASTNode):
    name : str

    def visit(self, context):
        s = context.symbolTable.lookUp(self.name)
        if not s:
            raise CompileError(f"Attempting to reference unknown {self.name}", self.location)
        return s


@dataclass(frozen=True)
class Argument(ASTNode):
    completeType : Any
    name : str

    @property
    def type(self):
        if self.completeType[-1] == "*":
            # Pointers are handled as int
            return "int"
        else:
            return self.completeType


@dataclass(frozen=True)
class Function(ASTNode):
    pass


@dataclass(frozen=True)
class FunctionDeclaration(Function):
    type : str
    name : str
    arguments : tuple[Argument] = field(default_factory=tuple)

    def visit(self, context):
        # TODO, don't add self but a Function but without any statements
        context.symbolTable.addSymbolEntry(self.name, self)


class FunctionDefinition(Function):
    def __init__(self, t, name, statements, arguments=[], *, location):
        super().__init__(location=location)
        self.type = t
        self.name = name
        self.statements = statements
        self.arguments = arguments

    def __repr__(self):
        return "FunctionDefinition " + self.name + " with statements " + str(self.statements)

    def mapSymbols(self, symbolTable, context):
        # stack pointer points to last byte written, so first variable starts at one byte below SP
        offset = 0
        for symbol in symbolTable.values():
            if not symbol.impl:
                if "." in symbol.name:
                    continue
                offset -= context.typeEnv.sizeOfType(symbol.type)
                symbol.impl = StackAddress(offset)
        for symbol in symbolTable.values():
            if not symbol.impl:
                if "." in symbol.name:
                    s, field = symbol.name.split(".", 1)
                    se = symbolTable[s]
                    structTypeName = se.completeType.name
                    structType = context.typeEnv.lookupStructName(structTypeName)
                    fieldOffset = structType.fields[field].offset
                    symbol.impl = se.impl.cloneWithOffset(fieldOffset)

    def visit(self, context):
        context.symbolTable.addSymbolEntry(self.name, self)
        context.typeEnv.pushFrame()
        context.symbolTable.pushFrame()
        context.functionName = self.name
        context.functionLabels = 0
        context.blockFactory.enterBlock(self.name)
        # return address is at ix+2, ix+3. Rightmost argument (16-bit) is at ix+5, ix+4
        # If pushing AF, then A is at ix+5
        offset = 4
        for a in self.arguments:
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
        context.blockFactory.addIR(IRDefFun(self))
        for s in self.statements:
            s.visit(context)
        self.mapSymbols(symbolTable, context)
        # TODO mutable state
        self.frameSize = stackFrameSize(symbolTable)
        context.blockFactory.addIR(IRFunExit(self))
        context.exitBlock()
        context.symbolTable.popFrame()
        context.typeEnv.popFrame()
        context.functionName = None
        return symbolTable # for testing


@dataclass(frozen=True)
class If(ASTNode):
    expr : Any
    statements : list

    def visit(self, context):
        skipLabel = createLabel(context)
        if isinstance(self.expr, Relation):
            (lhsAddr, rhsAddr) = self.expr.visit(context)
            ir = IRIfRelation(self.expr.operation, lhsAddr, rhsAddr, skipLabel)
        else:
            exprAddr = self.expr.visit(context)
            ir = IRIfVariable(exprAddr, skipLabel)
        context.blockFactory.addIR(ir)
        context.exitBlock()
        context.blockFactory.enterSubBlock()
        for s in self.statements:
            s.visit(context)
        context.blockFactory.addIR(IRSpillAll())
        context.exitBlock()
        context.blockFactory.enterSubBlock()
        context.blockFactory.addIR(IRLabel(skipLabel))


@dataclass(frozen=True)
class While(ASTNode):
    expr : Any
    statements : list

    def visit(self, context):
        ra = registerAllocator.RA
        # TODO should spill all be part of exitBlock?
        context.blockFactory.addIR(IRSpillAll())
        context.exitBlock()
        loopLabel = createLabel(context)
        context.blockFactory.addIR(IRLabel(loopLabel))
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
        context.blockFactory.enterSubBlock()
        for s in self.statements:
            s.visit(context)
        context.blockFactory.addIR(IRSpillAll())
        context.exitBlock()
        context.blockFactory.addIR(IRJump(loopLabel))
        context.blockFactory.enterSubBlock()
        context.blockFactory.addIR(IRLabel(skipLabel))

VALID_TYPES = { 'void', 'char', 'int' }
def verifyType(t, location, typeEnv):
    if isinstance(t, StructType):
        if not typeEnv.lookupStructName(t.name):
            raise CompileError(f"Unknown struct {t.name}", location)
        return True
    elif t[-1] == '*':
        return verifyType(t[:-1], location, typeEnv);
    if not t in VALID_TYPES:
        raise CompileError(f"Unknown type {t}", location)

@dataclass(frozen=True)
class VariableDefinition(ASTNode):
    completeType : Any
    name : str
    value : Any = None # TODO rename to rhs?

    @property
    def type(self):
        if self.completeType[-1] == "*":
            # Pointers are handled as int
            return "int"
        else:
            return self.completeType

    def visit(self, context):
        tComplete = self.completeType
        s = context.symbolTable.lookUp(tComplete)
        if s and isinstance(s.impl, TypeAddress):
            tComplete = s.impl.completeType
        else:
            verifyType(self.completeType, self.location, context.typeEnv)
        symbol = SymEntry(tComplete, self.name)
        context.symbolTable.addSymbolEntry(self.name, symbol)
        if not context.functionName:
            symbol.impl = GlobalAddress(self.name)
            if self.value:
                address = self.value.visit(context)
                if isinstance(address, SymEntry):
                    value = address.name
                elif isinstance(address, Constant):
                    value = address.value
                else:
                    error()
                # if self.completeType == "char*":
                #     value = self.value.value
                # else:
                #     value = self.value.value
            else:
                value = 0
            # value = self.value.visit(context) if self.value else Constant(self.completeType, 0)
            context.dataSegment[symbol.name] = (symbol.type, value)
        else:
            if self.value:
                rhsAddr = promoteIfNeededTo(self.value.visit(context), self.type, tComplete, context, "assignment", self.location)
                context.blockFactory.addIR(IRAssign(symbol, rhsAddr))

def isConvertableTo(fromType, toType):
    if fromType == toType:
        return True
    if fromType == "char" and toType == "int":
        return True
    if fromType == "void*" and toType[-1]=="*":
        return True
    return False


@dataclass(frozen=True)
class Cast(ASTNode):
    completeType : Any
    value : Any = None 

    def visit(self, context):
        valueAddr = self.value.visit(context)
        if isinstance(valueAddr, Constant):
            temp = copy(valueAddr)
            temp.completeType = self.completeType
            return temp
        else:
            t = CastSymEntry(valueAddr, self.completeType)
            return t


@dataclass(frozen=True)
class VariableAssignment(ASTNode):
    lvalue : Any
    rhs : Any

    def visit(self, context):
        if not (isinstance(self.lvalue, Variable) or 
                isinstance(self.lvalue, Dereference) or 
                isinstance(self.lvalue, StructFieldReference)):
            raise CompileError(f"Can't assign to non-lvalue {self.lvalue}", self.location)
        lvalue = self.lvalue.visit(context)
        rhsAddr = promoteIfNeededTo(self.rhs.visit(context), lvalue.type, lvalue.completeType, context, "assignment", self.location)
        # rhsAddr = self.rhs.visit(context)
        # if not isConvertableTo(rhsAddr.completeType, lvalue.completeType):
        #     raise CompileError(f"Can't assign {lvalue.completeType} from {rhsAddr.completeType}", self.location)
        # if rhsAddr.completeType != lvalue.completeType:
        #     temp = context.symbolTable.addTemporary(lvalue.completeType)
        #     context.blockFactory.addIR(IRPromote(
        #         temp,
        #         rhsAddr,
        #         lvalue.completeType))
        #     rhsAddr = temp
        context.blockFactory.addIR(IRAssign(lvalue, rhsAddr))


@dataclass(frozen=True)
class DerefPointerAssignment(ASTNode):
    lvalue : Any
    rhs : Any

    def visit(self, context):
        lvalue = self.lvalue.visit(context)
        rhsAddr = self.rhs.visit(context)
        context.blockFactory.addIR(IRAssignToPointer(lvalue, rhsAddr))


@dataclass(frozen=True)
class AddressOf(ASTNode):
    expr : Any

    def visit(self, context):
        exprAddr = self.expr.visit(context)
        irAddressOf = IRAddressOf(exprAddr, context.symbolTable.addTemporary(exprAddr.completeType + "*"))
        context.blockFactory.addIR(irAddressOf)
        return irAddressOf.resultAddr


@dataclass(frozen=True)
class Dereference(ASTNode):
    expr : Any

    def visit(self, context):
        pointer = self.expr.visit(context)
        if not pointer.isPointer:
            raise CompileError(f"Attempt to dereference non-pointer {self.expr.name} of type {pointer.completeType}", location=self.location)
        ct = pointer.completeType[:-1] # remove trailing *
        deref = IRDereference(pointer, context.symbolTable.addTemporary(ct))
        context.blockFactory.addIR(deref)
        deref.resultAddr.impl = PointerAddress(pointer)
        return deref.resultAddr


@dataclass
class FunctionCall(MutableASTNode):
    name : str
    arguments : list[Argument] = field(default_factory=list)

    def __post_init__(self):
        self.storeResult = False

    def setStoreResult(self):
        self.storeResult = True

    def visit(self, context):
        fun = context.symbolTable.lookUp(self.name)
        if not fun:
            raise CompileError(f"Attempting to call unknown function {self.name}", self.location)
        if not isinstance(fun, Function):
            raise CompileError(f"Attempting to call non-function {self.name}", self.location)
        if len(fun.arguments) != len(self.arguments):
            raise CompileError(f"Attempting to call function {self.name} with {len(self.arguments)} arguments but expected {len(fun.arguments)}", self.location)
        for fa, a in zip(reversed(fun.arguments), reversed(self.arguments)):
            # exprAddress = a.visit(context)
            exprAddress = promoteIfNeededTo(a.visit(context), fa.type, fa.completeType, context, f"argument {fa.name}", self.location)
            context.blockFactory.addIR(IRArgument(exprAddress))
        t = simpleTypeForComplexType(fun.type)
        if self.storeResult:
            print(f"FunctionCall {fun=} creating IRFunCall")
            irfuncall = IRFunCall(t, self.name, len(self.arguments), addr=context.symbolTable.addTemporary(fun.type))
            context.blockFactory.addIR(irfuncall)
            return irfuncall.resultAddr
        else:
            irfuncall = IRFunCall(t, self.name, len(self.arguments))
            context.blockFactory.addIR(irfuncall)


@dataclass(frozen=True)
class Return(ASTNode):
    expr : Any

    def visit(self, context):
        completeType = context.symbolTable.lookUp(context.functionName).type
        simpleType = simpleTypeForComplexType(completeType)
        exprAddress = self.expr.visit(context)
        context.blockFactory.addIR(IRReturn(simpleType, exprAddress, context.functionName))


# TODO much duplication for the binary operations
@dataclass(frozen=True)
class Add(ASTNode):
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
class Subtraction(ASTNode):
    lhs : Any
    rhs : Any

    def visit(self, context):
        lhsAddr = self.lhs.visit(context)
        rhsAddr = self.rhs.visit(context)
        ct = lhsAddr.completeType
        irAdd = IRSub(context.symbolTable.addTemporary(ct), lhsAddr, rhsAddr)
        context.blockFactory.addIR(irAdd)
        return irAdd.resultAddr


@dataclass(frozen=True)
class BitwiseOr(ASTNode):
    lhs : Any
    rhs : Any

    def visit(self, context):
        lhsAddr = self.lhs.visit(context)
        rhsAddr = self.rhs.visit(context)
        ct = lhsAddr.completeType
        ir = IRBitwiseOr(context.symbolTable.addTemporary(ct), lhsAddr, rhsAddr)
        context.blockFactory.addIR(ir)
        return ir.resultAddr


@dataclass(frozen=True)
class BitwiseAnd(ASTNode):
    lhs : Any
    rhs : Any

    def visit(self, context):
        lhsAddr = self.lhs.visit(context)
        rhsAddr = self.rhs.visit(context)
        ct = lhsAddr.completeType
        ir = IRBitwiseAnd(context.symbolTable.addTemporary(ct), lhsAddr, rhsAddr)
        context.blockFactory.addIR(ir)
        return ir.resultAddr


@dataclass(frozen=True)
class Relation(ASTNode):
    operation : str
    lhs : Any
    rhs : Any

    def visit(self, context):
        return (self.lhs.visit(context), self.rhs.visit(context))

@dataclass(frozen=True)
class TypeDef(ASTNode):
    name : str
    completeType : str

    def visit(self, context):
        symbol = SymEntry(self.completeType, self.name)
        context.symbolTable.addSymbolEntry(self.name, symbol)
        symbol.impl = TypeAddress(completeType=self.completeType)

@dataclass(frozen=True)
class StructDefinition(ASTNode):
    name : str
    fields : tuple[VariableDefinition]

    def visit(self, context):
        if context.typeEnv.lookupStructName(self.name):
            raise CompileError(f"Redefinition of struct {self.name}", self.location)
        fields = {}
        offset = 0;
        for f in self.fields:
            fields[f.name] = StructField(type=f.type, name=f.name, offset=offset)
            offset += context.typeEnv.sizeOfType(f.type)
        s = StructType(self.name, fields)
        context.typeEnv.addStruct(s)
        return s

@dataclass(frozen=True)
class StructFieldReference(ASTNode):
    structVar : Any
    field : str

    def visit(self, context):
        structAddr = self.structVar.visit(context);
        struct = context.typeEnv.lookupStructName(structAddr.completeType.name)
        try:
            offset = struct.fields[self.field].offset
        except KeyError:
            print(self.structVar)
            raise CompileError(f"Unknown field {self.field} in struct {struct.name}", self.location)
        name = f"{self.structVar.name}.{self.field}"
        if not context.symbolTable.lookUp(name):
            symEntry = SymEntry(struct.fields[self.field].type, name)
            context.symbolTable.addSymbolEntry(symEntry.name, symEntry)
        return context.symbolTable.lookUp(name)
        print(f"StructFieldReference {id(symEntry)} {field}")
        return symEntry

