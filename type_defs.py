# Note: name types.py is taken by the stdlib

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class StructType:
    name : str
    fields : dict = field(default_factory=dict)

@dataclass(frozen=True)
class StructField:
    type : Any
    name : str
    offset :  int

