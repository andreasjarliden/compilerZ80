from dataclasses import dataclass, field
from typing import Any
from ir import *
from symbolTable import *
from blocks import BlockFactory
from error import Location, CompileError
from typeEnv import TypeEnv
from type_defs import StructType, PointerType, StructField, simpleTypeForComplexType
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

def updateLiveInBlock(block):
    live = { s: not s.name.startswith("temp") for s in block.exitSymbols}
    for i in reversed(block.statements):
        i.updateLive(live)

@dataclass
class ASTContext:
    blockFactory : Any = field(default_factory=BlockFactory)
    symbolTable : SymbolTable = field(default_factory=SymbolTable)
    typeEnv : Any = field(default_factory=TypeEnv)
    functionName : str = None
    dataSegment : dict[SymEntry, Any] = field(default_factory=dict)
    stringTable : StringTable = field(default_factory=StringTable)
    stackOffset : int = field(default = 0, init=False)

    def exitBlock(self):
        self.blockFactory._exitBlock(self.symbolTable.allSymbols())
        updateLiveInBlock(self.blockFactory.currentBlock)
        self.blockFactory.currentBlock = None

    def newSubBlock(self):
        self.exitBlock();
        self.blockFactory.enterSubBlock()

    def resetStackFrame(self):
        self.stackOffset = 0;

    def createTemporary(self, completeType):
        t = self.symbolTable.addTemporary(completeType)
        self.addLocal(t)
        return t

    def addLocal(self, symbol : SymEntry):
        # stack pointer points to last byte written, so first variable starts at one byte below SP
        self.stackOffset -= self.typeEnv.sizeOfType(symbol.type)
        symbol.impl = StackAddress(self.stackOffset)

    def pushFrame(self):
        self.typeEnv.pushFrame()
        self.symbolTable.pushFrame()
        
    def popFrame(self):
        self.symbolTable.popFrame()
        self.typeEnv.popFrame()


def createLabel(context):
    context.functionLabels += 1
    return f"{context.functionName}_l{context.functionLabels}"


def promoteIfNeededTo(rhsAddr, toType, toCompleteType, context, operation, location):
    if not isConvertableTo(rhsAddr.completeType, toCompleteType):
        raise CompileError(f"Can't convert {rhsAddr.completeType} to {toCompleteType} in {operation}", location)
    # Only IRPromote if we have to change the simple, concrete type
    if rhsAddr.type == toType:
        return rhsAddr
    if isinstance(rhsAddr, Constant):
        return Constant(toCompleteType, rhsAddr.value)
    temp = context.createTemporary(toCompleteType)
    context.blockFactory.addIR(IRPromote(
        temp,
        rhsAddr,
        toCompleteType))
    return temp

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
        if isinstance(self.completeType, PointerType):
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
        verifyType(self.type, self.location, context.typeEnv)
        for a in self.arguments:
            verifyType(a.completeType, a.location, context.typeEnv)
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

    def visit(self, context):
        verifyType(self.type, self.location, context.typeEnv)
        context.symbolTable.addSymbolEntry(self.name, self)
        context.pushFrame()
        context.resetStackFrame()
        context.functionName = self.name
        context.functionLabels = 0
        context.blockFactory.enterBlock(self.name)
        # return address is at ix+2, ix+3. Rightmost argument (16-bit) is at ix+5, ix+4
        # If pushing AF, then A is at ix+5
        offset = 4
        for a in self.arguments:
            verifyType(a.completeType, a.location, context.typeEnv)
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
        # TODO mutable state
        self.frameSize = stackFrameSize(symbolTable)
        context.blockFactory.addIR(IRFunExit(self))
        context.exitBlock()
        context.popFrame()
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
        # Note: IRIf handles the spilling
        context.newSubBlock()
        context.pushFrame()
        for s in self.statements:
            s.visit(context)
        context.blockFactory.addIR(IRSpillAll())
        context.newSubBlock()
        context.blockFactory.addIR(IRLabel(skipLabel))
        context.popFrame()


@dataclass(frozen=True)
class While(ASTNode):
    expr : Any
    statements : list

    def visit(self, context):
        ra = registerAllocator.RA
        context.blockFactory.addIR(IRSpillAll())
        context.newSubBlock()
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
        context.newSubBlock()
        context.pushFrame()
        for s in self.statements:
            s.visit(context)
        context.blockFactory.addIR(IRSpillAll())
        context.blockFactory.addIR(IRJump(loopLabel))
        context.newSubBlock()
        context.blockFactory.addIR(IRLabel(skipLabel))
        context.popFrame()

VALID_TYPES = { 'void', 'char', 'int' }
def verifyType(t, location, typeEnv):
    if isinstance(t, StructType):
        if not typeEnv.lookupStructName(t.name):
            raise CompileError(f"Unknown struct {t.name}", location)
        return True
    elif isinstance(t, PointerType): 
        return verifyType(t.toType, location, typeEnv);
    if not t in VALID_TYPES:
        raise CompileError(f"Unknown type {t}", location)

@dataclass(frozen=True)
class VariableDefinition(ASTNode):
    completeType : Any
    name : str
    value : Any = None # TODO rename to rhs?

    @property
    def type(self):
        if isinstance(self.completeType, StructType):
            return self.completeType
        if isinstance(self.completeType, PointerType):
            # Pointers are handled as int
            return "int"
        else:
            return self.completeType

    def visit(self, context):
        if self.name in context.symbolTable.currentSymbolTable():
            raise CompileError(f"Attempt to define already defined {self.name}", self.location)
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
            context.addLocal(symbol)
            if self.value:
                rhsAddr = promoteIfNeededTo(self.value.visit(context), self.type, tComplete, context, "assignment", self.location)
                context.blockFactory.addIR(IRAssign(symbol, rhsAddr))

def promotedType(t1, ct1, t2, ct2):
    if t1 == t2:
        return t1, ct1
    if t1 == "char" and t2 == "int":
        return "int", ct2
    if t1 == "int" and t2 == "char":
        return "int", ct1

def isConvertableTo(fromType, toType):
    if fromType == toType:
        return True
    if fromType == "char" and toType == "int":
        return True
    if fromType == PointerType("void") and isinstance(toType, PointerType):
        return True
    if isinstance(fromType, PointerType) and toType == PointerType("void"):
        return True
    return False


def isArithmeticConvertableTo(fromType, toType):
    if fromType == toType:
        return True
    if fromType == "char" and toType == "int":
        return True
    if fromType == "void*" and isinstance(toType, PointerType):
        return True
    if isinstance(fromType, PointerType) and toType == PointerType("void"):
        return True
    if fromType == "char" and isinstance(toType, PointerType):
        return True
    if fromType == "int" and isinstance(toType, PointerType):
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
        rhsAddr = self.rhs.visit(context)
        rhsAddr = promoteIfNeededTo(rhsAddr, lvalue.type, lvalue.completeType, context, "assignment", self.location)
        # TODO should move all of this into IRAssign
        if isinstance(self.lvalue, Dereference):
            context.blockFactory.addIR(IRAssignToPointer(lvalue.impl.pointer, rhsAddr))
        elif isinstance(self.lvalue, StructFieldReference) and isinstance(self.lvalue.structVar, Dereference):
            context.blockFactory.addIR(IRAssignToPointer(lvalue.impl.pointer, rhsAddr))
        else:
            context.blockFactory.addIR(IRAssign(lvalue, rhsAddr))

@dataclass(frozen=True)
class AddressOf(ASTNode):
    expr : Any

    def visit(self, context):
        exprAddr = self.expr.visit(context)
        irAddressOf = IRAddressOf(exprAddr, context.createTemporary(PointerType(exprAddr.completeType)))
        context.blockFactory.addIR(irAddressOf)
        return irAddressOf.resultAddr


@dataclass(frozen=True)
class Dereference(ASTNode):
    expr : Any

    def visit(self, context):
        pointer = self.expr.visit(context)
        if not pointer.isPointer:
            raise CompileError(f"Attempt to dereference non-pointer {self.expr.name} of type {pointer.completeType}", location=self.location)
        ct = pointer.completeType.toType
        if ct == "void":
            raise CompileError(f"Attempt to dereference void pointer {self.expr.name}", location=self.location)
        ir = IRDereference(pointer, context.createTemporary(ct))
        context.blockFactory.addIR(ir)
        ir.resultAddr.impl = PointerAddress(pointer)
        return ir.resultAddr


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
            irfuncall = IRFunCall(t, self.name, len(self.arguments), addr=context.createTemporary(fun.type))
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
        def computeByteOffset(address, resultType):
            instanceType = resultType.toType
            if instanceType == "void":
                sizeOf = 1
            else:
                sizeOf = context.typeEnv.sizeOfType(instanceType)
            if isinstance(address, Constant):
                return Constant(resultType, address.value * sizeOf)
            else:
                if sizeOf == 1:
                    return address
                irMul = IRMul(context.createTemporary(resultType), address, Constant("int", sizeOf))
                context.blockFactory.addIR(irMul)
                return irMul.resultAddr

        lhsAddr = self.lhs.visit(context)
        rhsAddr = self.rhs.visit(context)
        if lhsAddr.isPointer and rhsAddr.isPointer:
            raise CompileError(f"Can't add {lhsAddr.completeType} and {rhsAddr.completeType}", self.location)
        if not lhsAddr.isPointer and not rhsAddr.isPointer:
            # Normal arithmetics
            pt, resultType = promotedType(lhsAddr.type, lhsAddr.completeType, rhsAddr.type, rhsAddr.completeType)
            lhsAddr = promoteIfNeededTo(lhsAddr, pt, resultType, context, "addition", self.location)
            rhsAddr = promoteIfNeededTo(rhsAddr, pt, resultType, context, "addition", self.location)
        else:
            # Pointer arithmetics
            if rhsAddr.isPointer:
                resultType = rhsAddr.completeType
                lhsAddr = computeByteOffset(lhsAddr, resultType)
            else:
                resultType = lhsAddr.completeType
                rhsAddr = computeByteOffset(rhsAddr, resultType)

        ir = IRAdd(context.createTemporary(resultType), lhsAddr, rhsAddr)
        context.blockFactory.addIR(ir)
        return ir.resultAddr


# TODO duplication with Add
@dataclass(frozen=True)
class Subtraction(ASTNode):
    lhs : Any
    rhs : Any

    def visit(self, context):
        def computeByteOffset(address, resultType):
            instanceType = resultType.toType
            if instanceType == "void":
                sizeOf = 1
            else:
                sizeOf = context.typeEnv.sizeOfType(instanceType)
            if isinstance(address, Constant):
                return Constant(resultType, address.value * sizeOf)
            else:
                if sizeOf == 1:
                    return address
                irMul = IRMul(context.createTemporary(resultType), address, Constant("int", sizeOf))
                context.blockFactory.addIR(irMul)
                return irMul.resultAddr

        lhsAddr = self.lhs.visit(context)
        rhsAddr = self.rhs.visit(context)
        if not lhsAddr.isPointer and not rhsAddr.isPointer:
            # Normal arithmetics
            pt, resultType = promotedType(lhsAddr.type, lhsAddr.completeType, rhsAddr.type, rhsAddr.completeType)
            lhsAddr = promoteIfNeededTo(lhsAddr, pt, resultType, context, "subtraction", self.location)
            rhsAddr = promoteIfNeededTo(rhsAddr, pt, resultType, context, "subtraction", self.location)
        else:
            # Pointer arithmetics
            if rhsAddr.isPointer:
                resultType = rhsAddr.completeType
                lhsAddr = computeByteOffset(lhsAddr, resultType)
            else:
                resultType = lhsAddr.completeType
                rhsAddr = computeByteOffset(rhsAddr, resultType)

        ir = IRSub(context.createTemporary(resultType), lhsAddr, rhsAddr)
        context.blockFactory.addIR(ir)
        return ir.resultAddr


@dataclass(frozen=True)
class BitwiseOr(ASTNode):
    lhs : Any
    rhs : Any

    def visit(self, context):
        lhsAddr = self.lhs.visit(context)
        rhsAddr = self.rhs.visit(context)
        ct = lhsAddr.completeType
        ir = IRBitwiseOr(context.createTemporary(ct), lhsAddr, rhsAddr)
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
        ir = IRBitwiseAnd(context.createTemporary(ct), lhsAddr, rhsAddr)
        context.blockFactory.addIR(ir)
        return ir.resultAddr


@dataclass(frozen=True)
class Mul(ASTNode):
    lhs : Any
    rhs : Any

    def visit(self, context):
        lhsAddr = self.lhs.visit(context)
        rhsAddr = self.rhs.visit(context)
        ir = IRMul(context.createTemporary(lhsAddr.completeType), lhsAddr, rhsAddr)
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
        s = StructType(self.name, fields)
        context.typeEnv.addStruct(s)
        for f in self.fields:
            verifyType(f.completeType, f.location, context.typeEnv)
            fields[f.name] = StructField(completeType=f.completeType, name=f.name, offset=offset)
            offset += context.typeEnv.sizeOfType(f.type)
        s.fields = fields
        return s

@dataclass(frozen=True)
class StructFieldReference(ASTNode):
    structVar : Any
    field : str
    name : str = field(init=False)

    def __post_init__(self):
        if isinstance(self.structVar, Dereference):
            object.__setattr__(self, "name", f"{self.structVar.expr.name}->{self.field}")
        else:
            object.__setattr__(self, "name", f"{self.structVar.name}.{self.field}")

    def visit(self, context):
        structAddr = self.structVar.visit(context);
        struct = context.typeEnv.lookupStructName(structAddr.completeType.name)
        try:
            offset = struct.fields[self.field].offset
        except KeyError:
            raise CompileError(f"Unknown field {self.field} in struct {struct.name}", self.location)
        if not context.symbolTable.lookUp(self.name):
            fieldType = struct.fields[self.field].completeType
            symEntry = SymEntry(fieldType, self.name)
            if isinstance(structAddr.impl, PointerAddress):
                fieldPointer = context.createTemporary(PointerType(fieldType))
                # TODO don't add if offset is zero
                irAdd = IRAdd(fieldPointer, structAddr.impl.pointer, Constant("int", offset))
                context.blockFactory.addIR(irAdd)
                symEntry.impl = PointerAddress(fieldPointer)
            else:
                symEntry.impl = structAddr.impl.cloneWithOffset(offset)
            context.symbolTable.addSymbolEntry(symEntry.name, symEntry)
        return context.symbolTable.lookUp(self.name)

