# Note: name types.py is taken by the stdlib

from dataclasses import dataclass, field
from typing import Any

def simpleTypeForComplexType(ct):
    if isinstance(ct, StructType) or not ct.endswith("*"):
        return ct
    return "int"

@dataclass(frozen=True)
class StructType:
    name : str
    fields : dict = field(default_factory=dict)

@dataclass(frozen=True)
class StructField:
    type : Any
    name : str
    offset :  int

