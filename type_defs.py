# Note: name types.py is taken by the stdlib

from dataclasses import dataclass, field
from typing import Any

def simpleTypeForComplexType(ct):
    if isinstance(ct, StructType) or not isinstance(ct, PointerType):
        return ct
    return "int"

@dataclass(frozen=True)
class PointerType:
    toType : Any

    def __repr__(self):
        return f"{self.toType}*"

# TODO there is commonality between SymbolOperand and StructField
@dataclass(frozen=True)
class StructField:
    completeType : Any
    name : str
    offset :  int

    @property
    def type(self):
        return simpleTypeForComplexType(self.completeType)

@dataclass
class StructType:
    name : str
    fields : dict[str, StructField]

    def __repr__(self):
        return f"struct {self.name} with fields {self.fields}"


@dataclass(frozen=True)
class Argument:
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
class FunctionType:
    type : Any
    name : str # Not sure really needed
    arguments : tuple[Argument, ...]
    isVarArg : bool
    isDefined : bool = field(default=False)

