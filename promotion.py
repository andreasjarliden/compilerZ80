from address import Constant, PointerType
from ir import IRPromote
from error import CompileError

def promoteLhsAndRhs(lhsAddr, rhsAddr, context, operation, location):
    # Normal arithmetics
    pt, resultType = promotedType(lhsAddr.type, lhsAddr.completeType, rhsAddr.type, rhsAddr.completeType)
    lhsAddr = promoteIfNeededTo(lhsAddr, pt, resultType, context, operation, location)
    rhsAddr = promoteIfNeededTo(rhsAddr, pt, resultType, context, operation, location)
    return (lhsAddr, rhsAddr, resultType)

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
