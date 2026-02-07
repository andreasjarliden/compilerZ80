# 3 types of addresses. Rename to e.g ConstantAddress?

class Constant:
    def __init__(self, t, value):
        self.type = t
        self.value = value

    def __repr__(self):
        return f"Constant {self.type} {self.value}"

    # Because it doubles an AST Node
    def visit(self):
        return self


class Symbol:
    def __init__(self, t, name):
        self.type = t
        self.name = name

    def __repr__(self):
        return f"Symbol {self.type} {self.name}"


class Temporary:
    NUM_TEMPS = 0
    def __init__(self, t):
        self.type = t
        self.name = f"temp{Temporary.NUM_TEMPS}"
        Temporary.NUM_TEMPS+=1

    def __repr__(self):
        return f"Temporary {self.type} {self.name}"


class Flags:
    def __init__(self):
        pass

    def __repr__(self):
        return "Flags"
