from lexer import tokens
import ply.yacc as yacc
from ir import *
from address import Constant

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
