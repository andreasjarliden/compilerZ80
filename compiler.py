from lexer import tokens
from pprint import pprint
import ply.yacc as yacc

asmFile = open("a.asm", "w")

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

    def genCode(self):
        # TODO should also add jump to return
        if isinstance(self._exprAddr.impl, StackVariable):
            asmFile.write(f'\tld\ta, {self._exprAddr.impl.codeArg()}\n')
        elif isinstance(self._exprAddr, Constant):
            asmFile.write(f'\tld\ta, {self._exprAddr.value}\n')
        else:
            error()
        

class IRFunCall:
    def __init__(self, name):
        self._addr = Temporary()
        self._name = name

    def __repr__(self):
        return "IRFunCall " + self._name

    def genCode(self):
        asmFile.write(f'\tcall\t{self._name}\n')
        # TODO store result

class IRAssign:
    def __init__(self, symEntry, rhsAddress):
        self._symEntry = symEntry
        self._rhsAddress = rhsAddress

    def __repr__(self):
        return f"IRAssign {self._symEntry} = {self._rhsAddress}"

    def genCode(self):
        if isinstance(self._symEntry.impl, StackVariable):
            lhs = self._symEntry.impl.codeArg()
        else:
            error()
        if isinstance(self._rhsAddress, Constant):
            value = self._rhsAddress._value
            asmFile.write(f'\tld\t{lhs}, {value}\n')
        elif isinstance(self._rhsAddress.impl, StackVariable):
            asmFile.write(f'\tld\ta, {self._rhsAddress.impl.codeArg()}\n')
            asmFile.write(f'\tld\t{lhs}, a\n')
        else:
            error()

class IRAdd:
    def __init__(self, addrLhs, addrRhs):
        t = Temporary()
        self._addr = currentSymbolTable()[t._name]
        self._lhsAddr = addrLhs
        self._rhsAddr = addrRhs

    def __repr__(self):
        return f"IRAdd {self._addr} = {self._lhsAddr} + {self._rhsAddr}"

    def genCode(self):
        if isinstance(self._lhsAddr.impl, StackVariable):
            lhs = self._lhsAddr.impl.codeArg()
            asmFile.write(f'\tld\ta, {lhs}\n')
        else:
            error()
        if isinstance(self._rhsAddr, Constant):
            asmFile.write(f'\tadd\ta, {self._rhsAddr._value}\n')
        elif isinstance(self._rhsAddr.impl, StackVariable):
            asmFile.write(f'\tadd\ta, {self._rhsAddr.impl.codeArg()}\n')
        else:
            error()
        asmFile.write(f'\tld\t{self._addr.impl.codeArg()}, a\n')

# 3 types of addresses. Rename to e.g ConstantAddress?

class Constant:
    def __init__(self, value):
        self._value = value

    def __repr__(self):
        return 'Constant ' + str(self._value)

    # Because it doubles an AST Node
    def createIR(self):
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
        self.symbolTable = {}

    def __repr__(self):
        return "Function " + self._name + " with statements " + str(self._statements)

    def createIR(self):
        pushSymbolTable()
        IR.append(IRDefFun(self, currentSymbolTable()))
        for s in self._statements:
            s.createIR()
        IR.append(IRFunExit(currentSymbolTable()))
        popSymbolTable()


class VariableDefinition:
    def __init__(self, name):
        self._name = name
        self._offset = None

    def __repr__(self):
        return "variable definition " + self._name + " at offset " + str(self._offset)

    def createIR(self):
        addSymbol(self._name)
        pass

class VariableAssignment:
    def __init__(self, name, rhs):
        self._name = name
        self._rhs = rhs;

    def __repr__(self):
        return "variable assignment " + self._name + " = " + str(self._rhs)

    def createIR(self):
        symEntry = currentSymbolTable()[self._name]
        rhsAddr = self._rhs.createIR()
        IR.append(IRAssign(symEntry, rhsAddr))


class VariableDereference:
    def __init__(self, name):
        self._name = name

    def __repr__(self):
        return "variable dereference " + self._name

    def createIR(self):
        return currentSymbolTable()[self._name]

    def indexedAddress(self, symbolTable):
        offset = symbolTable[self._name]._offset
        return f'(ix+{offset})'


class FunctionCall:
    def __init__(self, name):
        self._name = name

    def __repr__(self):
        return "call " + self._name

    def createIR(self):
        irfuncall = IRFunCall(self._name)
        IR.append(irfuncall)
        return irfuncall._addr


class Return:
    def __init__(self, expr):
        self._expr = expr

    def __repr__(self):
        return "Return " + str(self._expr)

    def createIR(self):
        exprAddress = self._expr.createIR()
        IR.append(IRReturn(exprAddress))


class Add:
    def __init__(self, lhs, rhs):
        self._lhs = lhs
        self._rhs = rhs

    def __repr__(self):
        return "<Add " + str(self._lhs) + " " + str(self._rhs) + ">"

    def createIR(self):
        lhsAddr = self._lhs.createIR()
        rhsAddr = self._rhs.createIR()
        irAdd = IRAdd(lhsAddr, rhsAddr)
        IR.append(irAdd)
        return irAdd._addr

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

ast = parser.parse("main() { foo();PRINT_HEX(); } foo() { char a;char b; b=42; a=b+b+1; return a+1; }") 
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

    def codeArg(self):
        # Use ix - 1, as "ix-1" is interpreted as identifier "ix-1"
        if self._offset >= 0:
            return f"(ix + {self._offset})"
        else:
            return f"(ix - {-self._offset})"

def mapSymbols():
    for f in IR_FUNCTIONS:
        symbolTable = f._symbolTable
        # stack pointer points to last byte written, so first variable starts at one byte below SP
        offset = -1
        for symbol in symbolTable:
            symbolTable[symbol].impl = StackVariable(offset)
            offset-=1

def genCode():
    asmFile.write("\t.org 08000h\n")
    asmFile.write('\t#include "constants.asm"\n')
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

genCode()


# for s in r:
#     s.generate(None)

