# 3 types of addresses. Rename to e.g ConstantAddress?

class Constant:
    def __init__(self, t, value):
        self.type = t
        self.value = value

    def __eq__(self, other):
        if not isinstance(other, Constant):
            return NotImplemented
        return self.type == other.type and self.value == other.value

    @property
    def completeType(self):
        return self.type

    def __repr__(self):
        return f"Constant {self.type} {self.value}"

    # Because it doubles an AST Node
    def visit(self, context):
        return self


class Temporary:
    NUM_TEMPS = 0
    def __init__(self, t):
        self.type = t
        self.name = f"temp{Temporary.NUM_TEMPS}"
        Temporary.NUM_TEMPS+=1

    def __repr__(self):
        return f"Temporary {self.type} {self.name}"
