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

# TODO there is commonality between SymEntry and StructField
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

