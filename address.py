# 3 types of addresses. Rename to e.g ConstantAddress?

class Constant:
    def __init__(self, value):
        self.value = value

    def __repr__(self):
        return 'Constant ' + str(self.value)

    # Because it doubles an AST Node
    def createIR(self):
        return self


class Symbol:
    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return "Symbol " + self.name


class Temporary:
    NUM_TEMPS = 0
    def __init__(self):
        self.name = f"temp{Temporary.NUM_TEMPS}"
        Temporary.NUM_TEMPS+=1

    def __repr__(self):
        return 'Temporary ' + str(self.name)


class Flags:
    def __init__(self):
        pass

    def __repr__(self):
        return "Flags"
