from dataclasses import dataclass, field
from typing import Any, Never
from ir import *
from symbolTable import *
from blocks import BlockFactory
from error import Location, CompileError
from typeEnv import TypeEnv
from type_defs import StructType, PointerType, StructField, simpleTypeForComplexType
from copy import copy
from promotion import promoteIfNeededTo, promoteLhsAndRhs

class StringTable:
    def __init__(self):
        # String -> name
        self._table = {}
        self._count = 0

    def addString(self, s : str) -> None:
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
    functionName : str | None = None
    continueLabel : str | None = None
    dataSegment : dict[SymbolOperand, Any] = field(default_factory=dict)
    stringTable : StringTable = field(default_factory=StringTable)
    stackOffset : int = field(default = 0, init=False)
    functionLabels : int = field(default = 0, init=False)

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

    def addLocal(self, symbol : SymbolOperand):
        # stack pointer points to last byte written, so first variable starts at one byte below SP
        size = self.typeEnv.sizeOfType(symbol.type)
        self.stackOffset -= size;
        symbol.impl = StackAddress(self.stackOffset)

    def pushFrame(self):
        self.typeEnv.pushFrame()
        self.symbolTable.pushFrame()
        
    def popFrame(self):
        self.symbolTable.popFrame()
        self.typeEnv.popFrame()


def createLabel(context : ASTContext ):
    context.functionLabels += 1
    return f"{context.functionName}_l{context.functionLabels}"



@dataclass(frozen=True)
class ASTNode:
    location : Location = field(default_factory=Location, compare=False, kw_only=True)


@dataclass
class MutableASTNode:
    location : Location = field(default_factory=Location, compare=False, kw_only=True)


@dataclass(frozen=True)
class Constant:
    completeType : Any
    value : Any

    def visit(self, context):
        return ConstantOperand(self.completeType, self.value)


@dataclass(frozen=True)
class StringConstant:
    value : str

    def visit(self, context):
        name = context.stringTable.addString(self.value)
        symbol = context.symbolTable.lookUp(name)
        if not symbol:
            symbol = SymbolOperand(PointerType("char"), name)
            symbol.impl = GlobalLabel(name)
            context.symbolTable.addSymbolEntry(name, symbol)
            if not symbol in context.dataSegment:
                context.dataSegment[symbol.name] = (symbol.type, self.value)
        return symbol

#TODO remove
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
class VarArg(ASTNode):
    pass


@dataclass(frozen=True)
class Function(ASTNode):
    pass


@dataclass(frozen=True)
class FunctionDeclaration(Function):
    type : str
    name : str
    arguments : tuple[Argument, ...] = field(default_factory=tuple)
    isVarArg : bool = field(init=False)

    def __post_init__(self):
        if len(self.arguments) > 0 and isinstance(self.arguments[-1], VarArg):
            object.__setattr__(self, "arguments", self.arguments[0:-1])
            object.__setattr__(self, "isVarArg", True)
        else:
            object.__setattr__(self, "isVarArg", False)

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

        if len(arguments) > 0 and isinstance(arguments[-1], VarArg):
            object.__setattr__(self, "arguments", arguments[0:-1])
            self.isVarArg = True
        else:
            self.isVarArg = False

    def __repr__(self):
        return "FunctionDefinition " + self.name + " with statements " + str(self.statements)

    def visit(self, context):
        verifyType(self.type, self.location, context.typeEnv)
        oldSymbol = context.symbolTable.lookUp(self.name)
        if oldSymbol and not isinstance(oldSymbol, FunctionDeclaration):
            raise CompileError(f"Redefinition of {self.name}", self.location)
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
            symbol = SymbolOperand(a.completeType, a.name)
            if a.type == "int":
                symbol.impl = StackAddress(offset)
            elif a.type == "char":
                # 8 bit values are sent in the high byte
                symbol.impl = StackAddress(offset+1)
            else:
                error()
            context.symbolTable.addSymbolEntry(a.name, symbol)
            offset+=2
        symbolTable = context.symbolTable.currentSymbolTable()
        context.blockFactory.addIR(IRDefFun(self))
        for s in self.statements:
            s.visit(context)
        # TODO mutable state
        self.frameSize = -context.stackOffset;
        context.blockFactory.addIR(IRFunExit(self))
        context.exitBlock()
        context.popFrame()
        context.functionName = None
        return symbolTable # for testing


@dataclass(frozen=True)
class If(ASTNode):
    expr : Any
    statements : list
    elseStatements : list | None = None

    def visit(self, context):
        elseLabel = createLabel(context)
        if isinstance(self.expr, Relation):
            (lhsAddr, rhsAddr) = self.expr.visit(context)
            ir = IRIfRelation(self.expr.operation, lhsAddr, rhsAddr, elseLabel)
        else:
            exprAddr = self.expr.visit(context)
            ir = IRIfVariable(exprAddr, elseLabel)
        context.blockFactory.addIR(ir)
        # Note: IRIf handles the spilling
        context.newSubBlock()
        context.pushFrame()
        for s in self.statements:
            s.visit(context)
        context.blockFactory.addIR(IRSpillAll())

        if self.elseStatements:
            afterLabel = createLabel(context)
            context.blockFactory.addIR(IRJump(afterLabel))
            context.newSubBlock()
            context.blockFactory.addIR(IRLabel(elseLabel))
            context.pushFrame()
            for s in self.elseStatements:
                s.visit(context)
            context.blockFactory.addIR(IRSpillAll())
        else:
            afterLabel = elseLabel

        context.newSubBlock()
        context.blockFactory.addIR(IRLabel(afterLabel))
        context.popFrame()


@dataclass(frozen=True)
class While(ASTNode):
    expr : Any
    statements : list

    def visit(self, context):
        context.blockFactory.addIR(IRSpillAll())
        context.newSubBlock()
        loopLabel = createLabel(context)
        oldContinueLabel = context.continueLabel
        context.continueLabel = loopLabel
        context.blockFactory.addIR(IRLabel(loopLabel))
        exitLabel = createLabel(context)
        if isinstance(self.expr, Variable) or isinstance(self.expr, Constant):
            exprAddr = self.expr.visit(context)
            ir = IRIfVariable(exprAddr, exitLabel)
        elif isinstance(self.expr, Relation):
            (lhsAddr, rhsAddr) = self.expr.visit(context)
            assert(lhsAddr.type == rhsAddr.type)
            ir = IRIfRelation(self.expr.operation, lhsAddr, rhsAddr, exitLabel)
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
        context.blockFactory.addIR(IRLabel(exitLabel))
        context.popFrame()
        context.continueLabel = oldContinueLabel

VALID_TYPES = { 'void', 'char', 'int' }
def verifyType(t, location, typeEnv):
    if isinstance(t, Struct):
        structType = typeEnv.lookupStructName(t.name)
        if not structType:
            raise CompileError(f"Unknown struct {t.name}", location)
        return structType
    elif isinstance(t, PointerType): 
        return PointerType(verifyType(t.toType, location, typeEnv));
    if not t in VALID_TYPES:
        raise CompileError(f"Unknown type {t}", location)
    return t


@dataclass(frozen=True)
class StructInitialization(ASTNode):
    fields : list

    def visit(self, context):
        ...

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
            tComplete = verifyType(tComplete, self.location, context.typeEnv)
        symbol = SymbolOperand(tComplete, self.name)
        context.symbolTable.addSymbolEntry(self.name, symbol)
        if not context.functionName:
            symbol.impl = GlobalAddress(self.name)
            if self.value:
                address = self.value.visit(context)
                if isinstance(address, SymbolOperand):
                    value = address.name
                elif isinstance(address, ConstantOperand):
                    value = address.value
                else:
                    error()
                # if self.completeType == "char*":
                #     value = self.value.value
                # else:
                #     value = self.value.value
            else:
                value = 0
            # value = self.value.visit(context) if self.value else ConstantOperand(self.completeType, 0)
            context.dataSegment[symbol.name] = (symbol.type, value)
        else:
            context.addLocal(symbol)
            if self.value:
                if isinstance(self.value, StructInitialization):
                    structInitializer = self.value
                    structType = symbol.completeType
                    initializeStruct(self.name, structType, structInitializer, context)
                else:
                    rhsAddr = promoteIfNeededTo(self.value.visit(context), self.type, tComplete, context, "assignment", self.location)
                    context.blockFactory.addIR(IRAssign(symbol, rhsAddr))


def initializeStruct(name : str,
                     structType : StructType,
                     structInitializer : StructInitialization,
                     context : ASTContext) -> None:
    structFields = tuple(structType.fields.keys())
    lastIndex = 0;
    for f in structInitializer.fields:
        if isinstance(f, tuple):
            fieldName, fieldValue = f
            lastIndex = structFields.index(fieldName)
        else:
            fieldName = structFields[lastIndex]
            fieldValue = f
        structFieldReference = StructFieldReference(Variable(name), fieldName)
        if isinstance(fieldValue, StructInitialization):
            fieldRefAddr = structFieldReference.visit(context)
            fieldStructType = fieldRefAddr.completeType
            initializeStruct(structFieldReference.name, fieldStructType, fieldValue, context)
        else:
            assignment = VariableAssignment(structFieldReference, fieldValue)
            assignment.visit(context)
            lastIndex += 1


@dataclass(frozen=True)
class Cast(ASTNode):
    completeType : Any
    value : Any = None 

    def visit(self, context):
        valueAddr = self.value.visit(context)
        completeType = verifyType(self.completeType, self.location, context.typeEnv)
        if isinstance(valueAddr, ConstantOperand):
            temp = copy(valueAddr)
            temp.completeType = completeType
            return temp
        else:
            t = CastSymbolOperand(valueAddr, completeType)
            return t


@dataclass(frozen=True)
class SizeOf(ASTNode):
    expr : Any

    def visit(self, context):
        if isinstance(self.expr, Struct):
            size = context.typeEnv.sizeOfType(self.expr.visit(context))
        elif isinstance(self.expr, ASTNode):
            oldDisabledState = context.blockFactory.disable
            context.blockFactory.disable = True
            exprAddr = self.expr.visit(context)
            context.blockFactory.disable = oldDisabledState
            size = context.typeEnv.sizeOfType(exprAddr.completeType)
        elif isinstance(self.expr, StringConstant):
            size = len(self.expr.value.string) + 1
        else:
            size = context.typeEnv.sizeOfType(self.expr)
        return ConstantOperand("int", size)


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
        return lvalue

@dataclass(frozen=True)
class AddressOf(ASTNode):
    expr : Any

    def visit(self, context):
        exprAddr = self.expr.visit(context)
        if isinstance(exprAddr.impl, PointerAddress) and isinstance(exprAddr.impl.pointer, ConstantOperand):
            return exprAddr.impl.pointer
        irAddressOf = IRAddressOf(exprAddr, context.createTemporary(PointerType(exprAddr.completeType)))
        context.blockFactory.addIR(irAddressOf)
        return irAddressOf.resultAddr


# Creates and returns a symbol with a PointerAddress to expr.
# It doesn't read anything itself, but creates an IRDereference instruction
# which updates the live tracking for the pointer and stores any symbols with
# matching types).
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
        numVarArgs = 0
        if fun.isVarArg:
            numVarArgs = len(self.arguments) - len(fun.arguments)
            if numVarArgs < 0:
                raise CompileError(f"Attempting to call function {self.name} with {len(self.arguments)} arguments but expected {len(fun.arguments)}", self.location)
        else:
            if len(fun.arguments) != len(self.arguments):
                raise CompileError(f"Attempting to call function {self.name} with {len(self.arguments)} arguments but expected {len(fun.arguments)}", self.location)
        numRegularArgs = len(fun.arguments)
        for a in reversed(self.arguments[numRegularArgs:len(self.arguments)]):
            exprAddress = a.visit(context)
            context.blockFactory.addIR(IRArgument(exprAddress))
        for fa, a in zip(reversed(fun.arguments), reversed(self.arguments[0:numRegularArgs])):
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
            if isinstance(address, ConstantOperand):
                return ConstantOperand(resultType, address.value * sizeOf)
            else:
                if sizeOf == 1:
                    return address
                irMul = IRMul(context.createTemporary(resultType), address, ConstantOperand("int", sizeOf))
                context.blockFactory.addIR(irMul)
                return irMul.resultAddr

        lhsAddr = self.lhs.visit(context)
        rhsAddr = self.rhs.visit(context)
        if lhsAddr.isPointer and rhsAddr.isPointer:
            raise CompileError(f"Can't add {lhsAddr.completeType} and {rhsAddr.completeType}", self.location)
        if not lhsAddr.isPointer and not rhsAddr.isPointer:
            # Normal arithmetics
            lhsAddr, rhsAddr, resultType = promoteLhsAndRhs(lhsAddr, rhsAddr, context, "addition", self.location)
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
            if isinstance(address, ConstantOperand):
                return ConstantOperand(resultType, address.value * sizeOf)
            else:
                if sizeOf == 1:
                    return address
                irMul = IRMul(context.createTemporary(resultType), address, ConstantOperand("int", sizeOf))
                context.blockFactory.addIR(irMul)
                return irMul.resultAddr

        lhsAddr = self.lhs.visit(context)
        rhsAddr = self.rhs.visit(context)
        if not lhsAddr.isPointer and not rhsAddr.isPointer:
            # Normal arithmetics
            lhsAddr, rhsAddr, resultType = promoteLhsAndRhs(lhsAddr, rhsAddr, context, "addition", self.location)
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
        lhsAddr = self.lhs.visit(context)
        rhsAddr = self.rhs.visit(context)
        if ((isinstance(lhsAddr.completeType, PointerType) and not isinstance(rhsAddr.completeType, PointerType)) or 
            (not isinstance(lhsAddr.completeType, PointerType) and isinstance(rhsAddr.completeType, PointerType))):
            raise CompileError(f"Comparisson between pointer and non-pointer: {lhsAddr.completeType} and {rhsAddr.completeType}", self.location)
        if isinstance(lhsAddr.completeType, PointerType) and isinstance(rhsAddr.completeType, PointerType):
            if lhsAddr.completeType != rhsAddr.completeType:
                raise CompileError(f"Comparisson between different pointer types: {lhsAddr.completeType} and {rhsAddr.completeType}", self.location)
        lhsAddr, rhsAddr, resultType = promoteLhsAndRhs(lhsAddr, rhsAddr, context, self.operation, self.location)
        return (lhsAddr, rhsAddr)

@dataclass(frozen=True)
class TypeDef(ASTNode):
    name : str
    completeType : str

    def visit(self, context):
        symbol = SymbolOperand(self.completeType, self.name)
        context.symbolTable.addSymbolEntry(self.name, symbol)
        symbol.impl = TypeAddress(completeType=self.completeType)


@dataclass(frozen=True)
class Struct(ASTNode):
    name : str

    def visit(self, context) -> StructType:
        return verifyType(self, self.location, context.typeEnv)


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
            fieldType = verifyType(f.completeType, f.location, context.typeEnv)
            fields[f.name] = StructField(completeType=fieldType, name=f.name, offset=offset)
            offset += context.typeEnv.sizeOfType(fieldType)
        s.fields = fields
        return s

@dataclass(frozen=True)
class StructFieldReference(ASTNode):
    structVar : Any
    fieldName : str
    name : str = field(init=False)

    def __post_init__(self):
        if isinstance(self.structVar, Dereference):
            if hasattr(self.structVar.expr, "name"):
                object.__setattr__(self, "name", f"{self.structVar.expr.name}->{self.fieldName}")
            else:
                object.__setattr__(self, "name", Temporary(None).name)
        else:
            object.__setattr__(self, "name", f"{self.structVar.name}.{self.fieldName}")

    def visit(self, context):
        structAddr = self.structVar.visit(context);
        structType = structAddr.completeType
        try:
            offset = structType.fields[self.fieldName].offset
        except KeyError:
            raise CompileError(f"Unknown field {self.fieldName} in struct {structType.name}", self.location)
        if not context.symbolTable.lookUp(self.name):
            fieldType = structType.fields[self.fieldName].completeType
            symbol = SymbolOperand(fieldType, self.name)
            if isinstance(structAddr.impl, PointerAddress):
                # TODO don't add if offset is zero
                if isinstance(structAddr.impl.pointer, ConstantOperand):
                    fieldPointer = ConstantOperand(PointerType(fieldType), structAddr.impl.pointer.value + offset)
                else:
                    fieldPointer = context.createTemporary(PointerType(fieldType))
                    irAdd = IRAdd(fieldPointer, structAddr.impl.pointer, ConstantOperand("int", offset))
                    context.blockFactory.addIR(irAdd)
                symbol.impl = PointerAddress(fieldPointer)
            else:
                symbol.impl = structAddr.impl.cloneWithOffset(offset)
            context.symbolTable.addSymbolEntry(symbol.name, symbol)
        else:
            if isinstance(structAddr.impl, PointerAddress):
                # Since we are using the pointer, use IRDereference to ensure
                # the pointer becomes live
                fieldSymbol = context.symbolTable.lookUp(self.name)
                fieldPointer = fieldSymbol.impl.pointer
                irDeref = IRDereference(fieldPointer, None)
                context.blockFactory.addIR(irDeref)
        return context.symbolTable.lookUp(self.name)

class Continue(ASTNode):
    def visit(self, context):
        if not context.continueLabel:
            raise CompileError(f"Continue outside loop", self.location)
        context.blockFactory.addIR(IRSpillAll())
        context.blockFactory.addIR(IRJump(context.continueLabel))




