class Temporary:
    NUM_TEMPS = 0
    def __init__(self, t):
        self.type = t
        self.name = f"temp{Temporary.NUM_TEMPS}"
        Temporary.NUM_TEMPS+=1

    def __repr__(self):
        return f"Temporary {self.type} {self.name}"
