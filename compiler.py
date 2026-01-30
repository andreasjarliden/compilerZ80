import ply.lex as lex
from pprint import pprint

asmFile = open("a.asm", "w")

reserved = {
        'return': 'RETURN',
        'char': 'CHAR'
        }

tokens = [
        'NUMBER',
        'ID',
        'LPARA',
        'RPARA',
        'LCURL',
        'RCURL',
        'SEMI',
        'ASSIGN',
        'PLUS',
        ] + list(reserved.values())

t_NUMBER = r'[0-9]+'
t_LPARA = r'\('
t_RPARA = r'\)'
t_LCURL = r'\{'
t_RCURL = r'\}'
t_SEMI = r';'
t_ASSIGN = r'='
t_PLUS = r'\+'

def t_ID(t):
    r'[a-zA-Z_][0-9a-zA-Z_]*'
    # If reserved, return that token type instead.  Otherwise, ID
    t.type = reserved.get(t.value, 'ID')
    return t

t_ignore = ' \t\n'

def t_error(t):
    print(f"Illegal character '{t.value[0]}'")
    t.lexer.skip(1)

lexer = lex.lex()
lexer.input("""foo() { 
            return 8;
            }""")
for tok in lexer:
    print(tok)

import ply.yacc as yacc

IR = []
IR_FUNCTIONS = []

# Stack of symbol tables
ENV = [ {} ]

class SymEntry:
    def __init__(self, name):
        self._name = name
        self.impl = None

    def __repr__(self):
        return f"SymEntry {self._name} {self.impl}"

def addSymbol(name):
    entry = SymEntry(name)
    ENV[-1][name] = entry
    return entry
def pushSymbolTable():
    ENV.append({})
def popSymbolTable():
    ENV.pop()
def currentSymbolTable():
    return ENV[-1]

class IRDefFun:
    def __init__(self, function, symbolTable):
        self._function = function
        self._symbolTable = symbolTable
        IR_FUNCTIONS.append(self)

    def __repr__(self):
        return f"IRDefFun symbolTable {self._symbolTable}"

    def genCode(self):
        asmFile.write(self._function._name + ":\n");
        # Let IX be frame-pointer
        asmFile.write('\t; Let IX be frame-pointer\n')
        asmFile.write('\tpush\tIX\n')
        asmFile.write('\tld\tIX, 0\n')
        asmFile.write('\tadd\tIX, SP\n')

        # Reserve space for local variables
        localSize = len(self._symbolTable)
        if localSize > 0:
            negSize=65536-localSize
            negHexSize=f'{negSize:05x}h'
            asmFile.write('\t; Reserve space for local variables\n')
            asmFile.write(f'\tld\tHL, {negHexSize}\n')
            asmFile.write(f'\tadd\tHL, SP\n')
            asmFile.write(f'\tld\tSP, HL\n')

        asmFile.write('\t; Function content\n')

class IRFunExit:
    def __init__(self, symbolTable):
        self._symbolTable = symbolTable

    def __repr__(self):
        return f"IRFunExit symbolTable {self._symbolTable}"

    def genCode(self):
        if len(self._symbolTable) > 0:
            asmFile.write('\t;Restore stack pointer (free local variables)\n')
            asmFile.write(f'\tld\tSP, IX\n')
        asmFile.write('\t;Restore previous frame pointer IX and return\n')
        asmFile.write(f'\tpop\tIX\n')
        asmFile.write(f'\tret\n\n')

class IRReturn:
    def __init__(self, exprAddr):
        self._exprAddr = exprAddr

    def __repr__(self):
        return "IRReturn " + str(self._exprAddr)

class IRFunCall:
    def __init__(self, name):
        self._addr = Temporary()
        self._name = name

    def __repr__(self):
        return "IRFunCall " + self._name

class IRAssign:
    def __init__(self, symEntry, rhsAddress):
        self._symEntry = symEntry
        self._rhsAddress = rhsAddress

    def __repr__(self):
        return f"IRAssign {self._symEntry} = {self._rhsAddress}"

    def genCode(self):
        if isinstance(self._rhsAddress, Constant):
            value = self._rhs._value
            asmFile.write(f'\tld (ix+{offset}), {value}\n')

class IRAdd:
    def __init__(self, addrLhs, addrRhs):
        self._addr = Temporary()
        self._lhsAddr= addrLhs
        self._rhsAddr = addrRhs

    def __repr__(self):
        return f"IRAdd {self._addr} = {self._lhsAddr} + {self._rhsAddr}"

# 3 types of addresses. Rename to e.g ConstantAddress?

class Constant:
    def __init__(self, value):
        self._value = value

    def __repr__(self):
        return 'Constant ' + str(self._value)

    # Because it doubles an AST Node
    def createIR(self, symbolTable):
        return self

class Symbol:
    def __init__(self, name):
        self._name = name

    def __repr__(self):
        return "Symbol " + self._name


class Temporary:
    NUM_TEMPS = 0
    def __init__(self):
        self._name = f"temp{Temporary.NUM_TEMPS}"
        addSymbol(self._name)
        Temporary.NUM_TEMPS+=1

    def __repr__(self):
        return 'Temporary ' + str(self._name)

class Function:
    def __init__(self, name, statements):
        self._name = name
        self._statements = statements
        self._localSize = 0;
        self.symbolTable = {}
        # for s in statements:
        #     if isinstance(s, VariableDefinition):
                # s.setOffset(self._localSize)
                # self._localSize += 1
                # print("Adding ", s._name, " to symbol table")
                # self.symbolTable[s._name] = s

    def __repr__(self):
        return "Function " + self._name + " locals size " + str(self._localSize) + " with statements " + str(self._statements)

    def createIR(self):
        pushSymbolTable()
        IR.append(IRDefFun(self, currentSymbolTable()))
        for s in self._statements:
            s.createIR(self.symbolTable)
        IR.append(IRFunExit(self.symbolTable))
        popSymbolTable()

class VariableDefinition:
    def __init__(self, name):
        self._name = name
        self._offset = None

    def __repr__(self):
        return "variable definition " + self._name + " at offset " + str(self._offset)

    def setOffset(self, offset):
        self._offset = offset;

    def createIR(self, symbolTable):
        addSymbol(self._name)
        # symbolTable[self._name] = -1
        pass

class VariableAssignment:
    def __init__(self, name, rhs):
        self._name = name
        self._rhs = rhs;

    def __repr__(self):
        return "variable assignment " + self._name + " = " + str(self._rhs)

    def createIR(self, symbolTable):
        symEntry = currentSymbolTable()[self._name]
        rhsAddr = self._rhs.createIR(symbolTable)
        IR.append(IRAssign(symEntry, rhsAddr))

    def generate(self, symbolTable):
        offset = symbolTable[self._name]._offset
        if isinstance(self._rhs, VariableDereference):
            self._rhs.generate(symbolTable)
            asmFile.write(f'\tld (ix+{offset}), a\n')
        elif isinstance(self._rhs, int):
            value = self._rhs
            asmFile.write(f'\tld (ix+{offset}), {value}\n')
        else:
            self._rhs.generate(symbolTable)
            asmFile.write(f'\tld (ix+{offset}), a\n')

class VariableDereference:
    def __init__(self, name):
        self._name = name

    def __repr__(self):
        return "variable dereference " + self._name

    def createIR(self, symbolTable):
        return currentSymbolTable()[self._name]

    def indexedAddress(self, symbolTable):
        offset = symbolTable[self._name]._offset
        return f'(ix+{offset})'

    def generate(self, symbolTable):
        offset = symbolTable[self._name]._offset
        asmFile.write(f'\tld a, (ix+{offset})\n')

class FunctionCall:
    def __init__(self, name):
        self._name = name

    def __repr__(self):
        return "call " + self._name

    def createIR(self, symbolTable=None):
        irfuncall = IRFunCall(self._name)
        IR.append(irfuncall)
        return irfuncall._addr

    def generate(self, symbolTable):
        asmFile.write("\tcall " + self._name + "\n")

class Return:
    def __init__(self, expr):
        self._expr = expr

    def __repr__(self):
        return "Return " + str(self._expr)

    def createIR(self, symbolTable):
        exprAddress = self._expr.createIR(symbolTable)
        IR.append(IRReturn(exprAddress))

    def generate(self, symbolTable):
        if isinstance(self._value, VariableDereference):
            self._value.generate(symbolTable);
        else:
            asmFile.write("\tld a, " + self._value + "\n")
        # TODO support return at other places then at the end
        # asmFile.write("\tret" + "\n");

class Add:
    def __init__(self, lhs, rhs):
        self._lhs = lhs
        self._rhs = rhs

    def __repr__(self):
        return "<Add " + str(self._lhs) + " " + str(self._rhs) + ">"

    def createIR(self, symbolTable):
        lhsAddr = self._lhs.createIR(symbolTable)
        rhsAddr = self._rhs.createIR(symbolTable)
        irAdd = IRAdd(lhsAddr, rhsAddr)
        IR.append(irAdd)
        return irAdd._addr

    def generate(self, symbolTable):
        # lhs in A
        if isinstance(self._lhs, VariableDereference):
            self._lhs.generate(symbolTable);
        else:
            asmFile.write("\tld a, " + self._lhs + "\n")
        # rhs
        if isinstance(self._rhs, VariableDereference):
            asmFile.write("\tadd a, " + self._rhs.indexedAddress() + "\n")
        elif isinstance(self._rhs, int):
            asmFile.write("\tadd a, " + str(self._rhs) + "\n")
        else:
            error()

def p_statement_list(p):
    '''
    statement_list : statement_list statement
                   | statement
    '''
    if len(p) == 3:
        p[0] = p[1] + (p[2] if isinstance(p[2], list) else [p[2]])
    else:
        p[0] = [p[1]]

def p_statement(p):
    ''' 
    statement : expression SEMI
              | function_definition
    '''
    p[0] = p[1]

def p_expression(p):
    '''
    expression : return_expression
               | function_expression
               | var_def_expression
               | var_assign_expression
    '''
    p[0] = p[1]

def p_value_expression_constant(p):
    '''
    value_expression : NUMBER
    '''
    p[0] = Constant(int(p[1]))

def p_value_expression_variable(p):
    '''
    value_expression : ID
    '''
    p[0] = VariableDereference(p[1])

def p_value_expression_add(p):
    '''
    value_expression : value_expression PLUS  value_expression
    '''
    p[0] = Add(p[1], p[3])

def p_variable_definition_expression(p):
    'var_def_expression : CHAR ID'
    print("Variable definition " + p[2])
    p[0] = VariableDefinition(p[2])

def p_variable_assignment_expression(p):
    'var_assign_expression : ID ASSIGN value_expression'
    print("Variable assignment ", p[1], p[3])
    p[0] = VariableAssignment(p[1], p[3])

def p_return_expression(p):
    'return_expression : RETURN value_expression'
    p[0] = Return(p[2])

def p_function_expression(p):
    'function_expression : ID LPARA RPARA'
    print("Calling function "+p[1])
    p[0] = FunctionCall(p[1])

def p_function_definition(p):
    'function_definition : ID LPARA RPARA LCURL statement_list RCURL'
    print("def function " + p[1])
    node = Function(p[1], p[5])
    p[0] = node

def p_error(p):
    if p:
        print("Parse error: " + p.value);
    else:
        print("Unexpected end of file");

parser = yacc.yacc()

ast = parser.parse("foo() { char a;char b; b=42; a=b+b+1; return a;} foo();PRINT_HEX();")
print("AST")
pprint(ast)
print()

def astToThreeCode(ast):
    for n in ast:
        n.createIR()

class StackVariable:
    def __init__(self, offset):
        self._offset = offset

    def __repr__(self):
        return f"Stack Variable offset {self._offset}"

def mapSymbols():
    for f in IR_FUNCTIONS:
        symbolTable = f._symbolTable
        offset = 0
        for symbol in symbolTable:
            symbolTable[symbol].impl = StackVariable(offset)
            offset+=1

def genCode():
    for i in IR:
        i.genCode()

astToThreeCode(ast)

print("IR")
pprint(IR)

print("IR_FUNCTIONS")
pprint(IR_FUNCTIONS)

mapSymbols()

print("\nIR mapped symbols")
pprint(IR)

# genCode()

# asmFile.write("\t.org 08000h\n")
# asmFile.write('\t#include "constants.asm"\n')

# for s in r:
#     s.generate(None)

