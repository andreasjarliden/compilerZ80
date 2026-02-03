from lexer import tokens
import ply.yacc as yacc
from ir import *
from address import Constant
import sys

# Stack of symbol tables
ENV = [ {} ]
FUNCTION = None
FUNCTION_LABELS = 0

SIZE_FOR_TYPES = { "char": 1,
                   "int": 2 }

class SymEntry:
    def __init__(self, t, name):
        self.name = name
        self.type = t
        self.impl = None

    @property
    def size(self):
        return SIZE_FOR_TYPES[self.type]

    def __repr__(self):
        return f"<SymEntry {self.type} {self.name} {self.impl}>"

# TODO this belongs to the AST and should probably be moved to parser
# Any use should probably also be moved
def addSymbol(t, name):
    entry = SymEntry(t, name)
    ENV[-1][name] = entry
    return entry
def addSymbolEntry(name, entry):
    ENV[-1][name] = entry
def enterFunction(name):
    global FUNCTION
    global FUNCTION_LABELS
    ENV.append({})
    FUNCTION = name
    FUNCTION_LABELS = 0
def exitFunction():
    global FUNCTION
    ENV.pop()
    FUNCTION = None
def currentSymbolTable():
    return ENV[-1]
def addTemporary(t):
    temp = Temporary(t)
    return addSymbol(t, temp.name)
def createLabel():
    global FUNCTION
    global FUNCTION_LABELS
    FUNCTION_LABELS += 1
    return f"{FUNCTION}_l{FUNCTION_LABELS}"

class Argument:
    def __init__(self, t, name):
        self.type = t
        self.name = name

    def __repr__(self):
        return f"Argument {self.type} {self.name}"

class Function:
    def __init__(self, t, name, statements, arguments=[]):
        self.type = t
        self.name = name
        self.statements = statements
        self.arguments = arguments
        addSymbolEntry(name, self)

    def __repr__(self):
        return "Function " + self.name + " with statements " + str(self.statements)

    def createIR(self):
        enterFunction(self.name)
        # return address is at ix+2, ix+3. Rightmost argument (16-bit) is at ix+5, ix+4
        # If pushing AF, then A is at ix+5
        offset = 4
        for a in reversed(self.arguments):
            symEntry = SymEntry(a.type, a.name)
            if a.type == "int":
                symEntry.impl = StackVariable(offset)
            elif a.type == "char":
                # 8 bit values are sent in the high byte
                symEntry.impl = StackVariable(offset+1)
            else:
                error()
            addSymbolEntry(a.name, symEntry)
            offset+=2
        IR.append(IRDefFun(self, currentSymbolTable()))
        for s in self.statements:
            s.createIR()
        IR.append(IRFunExit(self, currentSymbolTable()))
        exitFunction()

class If:
    def __init__(self, expr, statements):
        self.expr = expr
        self.statements = statements

    def __repr__(self):
        return f"IF {self.expr} with statements {self.statements}"

    def createIR(self):
        print(f"If.createIR: expr {self.expr}")
        exprAddr = self.expr.createIR()
        print(f"exprAddr {exprAddr}")
        skipLabel = createLabel()
        IR.append(IRIf(exprAddr, skipLabel))
        for s in self.statements:
            s.createIR()
        IR.append(IRLabel(skipLabel))

class VariableDefinition:
    def __init__(self, t, name):
        self.type = t
        self.name = name
        self.offset = None

    def __repr__(self):
        return f"variable definition {self.type} {self.name} at offset {self.offset}"

    def createIR(self):
        addSymbol(self.type, self.name)
        pass

class VariableAssignment:
    def __init__(self, name, rhs):
        self.name = name
        self.rhs = rhs;

    def __repr__(self):
        return "variable assignment " + self.name + " = " + str(self.rhs)

    def createIR(self):
        symEntry = currentSymbolTable()[self.name]
        rhsAddr = self.rhs.createIR()
        IR.append(IRAssign(symEntry, rhsAddr))

class VariableDereference:
    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return "variable dereference " + self.name

    def createIR(self):
        return currentSymbolTable()[self.name]

class FunctionCall:
    def __init__(self, name, arguments=[]):
        self.name = name
        self.arguments = arguments
        self.storeResult = False
        self.type = currentSymbolTable()[name].type
        print(f"Function call for {name} which is returning {self.type}")

    def __repr__(self):
        return f"call {self.name} with args {self.arguments}"

    def createIR(self):
        for a in reversed(self.arguments):
            exprAddress = a.createIR()
            IR.append(IRArgument(exprAddress))
        if self.storeResult:
            irfuncall = IRFunCall(self.type, self.name, len(self.arguments), addr=addTemporary(self.type))
            IR.append(irfuncall)
            return irfuncall.addr
        else:
            irfuncall = IRFunCall(self.type, self.name, len(self.arguments))
            IR.append(irfuncall)

class Return:
    def __init__(self, expr):
        self.expr = expr

    def __repr__(self):
        return "Return " + str(self.expr)

    def createIR(self):
        # Function is in the symbol table above the current one
        t = ENV[-2][FUNCTION].type
        exprAddress = self.expr.createIR()
        IR.append(IRReturn(t, exprAddress))

class Add:
    def __init__(self, lhs, rhs):
        self.lhs = lhs
        self.rhs = rhs

    def __repr__(self):
        return "<Add " + str(self.lhs) + " " + str(self.rhs) + ">"

    def createIR(self):
        lhsAddr = self.lhs.createIR()
        rhsAddr = self.rhs.createIR()
        t = lhsAddr.type # TODO promote
        irAdd = IRAdd(addTemporary(t), lhsAddr, rhsAddr)
        IR.append(irAdd)
        return irAdd.addr

class Equal:
    def __init__(self, lhs, rhs):
        self.lhs = lhs
        self.rhs = rhs

    def __repr__(self):
        return "<Equal " + str(self.lhs) + " " + str(self.rhs) + ">"

    def createIR(self):
        lhsAddr = self.lhs.createIR()
        rhsAddr = self.rhs.createIR()
        irEqual = IREqual(lhsAddr, rhsAddr)
        IR.append(irEqual)
        return irEqual.addr

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
              | if_expression
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
    # TODO all as char for now
    p[0] = Constant("char", int(p[1]))

def p_value_expression_fun(p):
    '''
    value_expression : function_expression
    '''
    print("Calling function " + str(p[1]))
    f = p[1]
    f.storeResult = True
    p[0] = p[1]

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

def p_value_expression_equal(p):
    ' value_expression : value_expression EQUAL value_expression'
    p[0] = Equal(p[1], p[3])

def p_variable_definition_expression(p):
    'var_def_expression : type ID'
    print(f"Variable definition {p[1]} {p[2]}")
    p[0] = VariableDefinition(p[1], p[2])

def p_type(p):
    '''type : CHAR
            | INT
    '''
    p[0] = p[1]

def p_variable_assignment_expression(p):
    'var_assign_expression : ID ASSIGN value_expression'
    print("Variable assignment ", p[1], p[3])
    p[0] = VariableAssignment(p[1], p[3])

def p_return_expression(p):
    'return_expression : RETURN value_expression'
    p[0] = Return(p[2])

def p_function_expression_no_args(p):
    'function_expression : ID LPARA RPARA'
    print(f"Calling function {str(p[1])} with no args")
    p[0] = FunctionCall(p[1])

def p_function_expression_args(p):
    'function_expression : ID LPARA expr_list RPARA'
    print(f"Calling function {p[1]} with args {str(p[3])}")
    p[0] = FunctionCall(p[1], p[3])

def p_function_definition_no_args(p):
    'function_definition : type ID LPARA RPARA LCURL statement_list RCURL'
    print("def function " + p[2])
    node = Function(p[1], p[2], p[6])
    p[0] = node

def p_function_definition_args(p):
    'function_definition : type ID LPARA arg_list RPARA LCURL statement_list RCURL'
    print("def function {p[1]} {p[2]}(...) with arguments {p[4]}")
    node = Function(p[1], p[2], p[7], p[4])
    p[0] = node

def p_if_expression(p):
    '''
    if_expression : IF LPARA value_expression RPARA LCURL statement_list RCURL
    '''
    print(f"IF {p[3]} {p[6]}")
    p[0] = If(p[3], p[6])

def p_expr_list_single(p):
    'expr_list : value_expression'
    print("expr " + str(p[1]))
    p[0] = [p[1]]

def p_expr_list_multiple(p):
    'expr_list : expr_list COMMA value_expression'
    p[0] = p[1] + [p[3]]
    print("expr " + str(p[0]))

def p_arg_list_single(p):
    'arg_list : arg'
    print("argument " + str(p[1]))
    p[0] = [p[1]]

def p_arg_list_multiple(p):
    'arg_list : arg_list COMMA arg'
    print("argument " + str(p[1]) + " " + str(p[3]))
    p[0] = p[1] + [p[3]]

def p_arg(p):
    'arg : type ID'
    p[0] = Argument(p[1], p[2])

def p_error(p):
    if p:
        print("Parse error: " + p.value + str(p));
    else:
        print("Unexpected end of file");
    sys.exit(1);

parser = yacc.yacc()
