from dataclasses import dataclass, field

@dataclass(frozen=True)
class Location:
    file : str | None = None
    line : int = 1

@dataclass(frozen=True)
class CompileError(Exception):
    message : str
    location : Location
