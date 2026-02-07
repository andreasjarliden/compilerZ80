SIZE_FOR_TYPES = { "char": 1,
                   "int": 2 }

class SymEntry:
    def __init__(self, t, completeType, name):
        self.name = name
        self.type = t
        self.completeType = completeType
        self.impl = None
        self.live = None

    def initLive(self):
        self.live = self.name.startswith("temp")
        self.nextUse = None

    @property
    def size(self):
        return SIZE_FOR_TYPES[self.type]

    def __repr__(self):
        return f"<SymEntry type:{self.type} c.type:{self.completeType} name:{self.name} live:{self.live} {self.impl}>"


