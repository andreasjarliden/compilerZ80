from lexer import tokens
import ply.yacc as yacc
from ir import *
from address import Constant
import sys
from pprint import *
from symEntry import *
from copy import copy

# Stack of symbol tables
ENV = [ {} ]
FUNCTION = None
FUNCTION_LABELS = 0

BASIC_BLOCKS = {}
BLOCK_PREFIX = None
BLOCK_NUMBER = 1

class BasicBlock:
    def __init__(self, symbolTable, name):
        self.statements = []
        self.symbolTable = symbolTable
        self.name = name

    def __repr__(self):
        return f"Symbol table: {self.symbolTable}\nStatements:\n{pformat(self.statements)}\n\n"

def addIR(ir):
    global CURRENT_BLOCK
    CURRENT_BLOCK.statements.append(ir)
def enterBlock(name, symbolTable):
    global BLOCK_NUMBER
    global BLOCK_PREFIX
    global CURRENT_BLOCK_NAME
    CURRENT_BLOCK_NAME = name
    BLOCK_PREFIX = name
    BLOCK_NUMER = 0
    enterSubBlock(symbolTable)
def enterSubBlock(symbolTable):
    global CURRENT_BLOCK
    global CURRENT_BLOCK_NAME
    global BLOCK_PREFIX
    global BLOCK_NUMBER
    CURRENT_BLOCK_NAME = f"{BLOCK_PREFIX}_{BLOCK_NUMBER:04}"
    CURRENT_BLOCK = BasicBlock(symbolTable, CURRENT_BLOCK_NAME)
    BLOCK_NUMBER+=1
def exitBlock():
    global CURRENT_BLOCK
    global CURRENT_BLOCK_NAME
    BASIC_BLOCKS[CURRENT_BLOCK_NAME] = CURRENT_BLOCK

# TODO this belongs to the AST and should probably be moved to parser
# Any use should probably also be moved
# TODO create real SymbolTable class
def addSymbol(t, completeType, name):
    entry = SymEntry(t, completeType, name)
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
def addTemporary(t, completeType):
    temp = Temporary(t)
    return addSymbol(t, completeType, temp.name)
def createLabel():
    global FUNCTION
    global FUNCTION_LABELS
    FUNCTION_LABELS += 1
    return f"{FUNCTION}_l{FUNCTION_LABELS}"

class Argument:
    def __init__(self, t, name):
        # TODO duplicate with Variable
        if t == "char" or t == "int":
            self.type = t
        elif t[0] == "*":
            # Pointers are handled as int
            self.type = "int"
        self.completeType = t
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

    def visit(self):
        enterFunction(self.name)
        enterBlock(self.name, currentSymbolTable())
        # return address is at ix+2, ix+3. Rightmost argument (16-bit) is at ix+5, ix+4
        # If pushing AF, then A is at ix+5
        offset = 4
        for a in reversed(self.arguments):
            symEntry = SymEntry(a.type, a.completeType, a.name)
            if a.type == "int":
                symEntry.impl = StackVariable(offset)
            elif a.type == "char":
                # 8 bit values are sent in the high byte
                symEntry.impl = StackVariable(offset+1)
            else:
                error()
            addSymbolEntry(a.name, symEntry)
            offset+=2
        addIR(IRDefFun(self, currentSymbolTable()))
        for s in self.statements:
            s.visit()
        addIR(IRFunExit(self, currentSymbolTable()))
        exitFunction()
        exitBlock()

class If:
    def __init__(self, expr, statements):
        self.expr = expr
        self.statements = statements

    def __repr__(self):
        return f"IF {self.expr} with statements {self.statements}"

    def visit(self):
        print(f"If.visit: expr {self.expr}")
        exprAddr = self.expr.visit()
        print(f"exprAddr {exprAddr}")
        skipLabel = createLabel()
        addIR(IRIf(exprAddr, skipLabel))
        exitBlock()
        enterSubBlock(currentSymbolTable())
        for s in self.statements:
            s.visit()
        exitBlock()
        enterSubBlock(currentSymbolTable())
        addIR(IRLabel(skipLabel))

class VariableDefinition:
    def __init__(self, t, name):
        if t == "char" or t == "int":
            self.type = t
        elif t[0] == "*":
            # Pointers are handled as int
            self.type = "int"
        self.completeType = t
        self.name = name
        self.offset = None

    def __repr__(self):
        return f"variable definition {self.type} {self.name} at offset {self.offset}"

    def visit(self):
        addSymbol(self.type, self.completeType, self.name)
        pass

class VariableAssignment:
    def __init__(self, lvalue, rhs):
        self.lvalue = lvalue
        self.rhs = rhs;

    def __repr__(self):
        return f"variable assignment {self.lvalue} = {self.rhs}"

    def visit(self):
        lvalue = self.lvalue.visit()
        print(f"Variable assignment lvalue {lvalue}")
        rhsAddr = self.rhs.visit()
        addIR(IRAssign(lvalue, rhsAddr))

class DerefPointerAssignment:
    def __init__(self, lvalue, rhs):
        self.lvalue = lvalue
        self.rhs = rhs;

    def __repr__(self):
        return f"Deref pointer assignment *{self.lvalue} = {self.rhs}"

    def visit(self):
        lvalue = self.lvalue.visit()
        rhsAddr = self.rhs.visit()
        addIR(IRAssignToPointer(lvalue, rhsAddr, currentSymbolTable()))

class Variable:
    def __init__(self, name):
        self.type = None
        self.completeType = None
        self.name = name

    def __repr__(self):
        return f"<Variable type {self.type} complete type {self.completeType} name {self.name}>"

    def visit(self):
        symEntry = currentSymbolTable()[self.name]
        self.type = symEntry.type
        self.completeType = symEntry.completeType
        return currentSymbolTable()[self.name]

class AddressOf:
    def __init__(self, expr):
        self.expr = expr

    def __repr__(self):
        return f"AddressOf {self.expr}"

    def visit(self):
        exprAddr = self.expr.visit()
        irAddressOf = IRAddressOf(exprAddr, addTemporary("int", "*" + exprAddr.completeType))
        addIR(irAddressOf)
        return irAddressOf.resultAddr

class Dereference:
    def __init__(self, expr):
        self.expr = expr

    def __repr__(self):
        return f"Dereference {self.expr}"

    def visit(self):
        resAddr = copy(self.expr.visit())
        print(f"Dereference: created code for pointer receiving {self.expr} address {resAddr}")
        resAddr.impl = DereferencedPointer()
        addIR(IRDereference(resAddr, currentSymbolTable()))
        return resAddr
        # return DereferencedPointer(t, resAddr)
        # symEntry = addTemporary(t, t)
        # symEntry.impl = DereferencedPointer()
        # return symEntry

class FunctionCall:
    def __init__(self, name, arguments=[]):
        self.name = name
        self.arguments = arguments
        self.storeResult = False
        self.type = currentSymbolTable()[name].type
        print(f"Function call for {name} which is returning {self.type}")

    def __repr__(self):
        return f"call {self.name} with args {self.arguments}"

    def visit(self):
        for a in reversed(self.arguments):
            exprAddress = a.visit()
            addIR(IRArgument(exprAddress))
        if self.storeResult:
            irfuncall = IRFunCall(self.type, self.name, len(self.arguments), addr=addTemporary(self.type, self.type))
            addIR(irfuncall)
            return irfuncall.resultAddr
        else:
            irfuncall = IRFunCall(self.type, self.name, len(self.arguments))
            addIR(irfuncall)

class Return:
    def __init__(self, expr):
        self.expr = expr

    def __repr__(self):
        return "Return " + str(self.expr)

    def visit(self):
        # Function is in the symbol table above the current one
        t = ENV[-2][FUNCTION].type
        exprAddress = self.expr.visit()
        addIR(IRReturn(t, exprAddress))

class Add:
    def __init__(self, lhs, rhs):
        self.lhs = lhs
        self.rhs = rhs

    def __repr__(self):
        return "<Add " + str(self.lhs) + " " + str(self.rhs) + ">"

    def visit(self):
        lhsAddr = self.lhs.visit()
        rhsAddr = self.rhs.visit()
        t = lhsAddr.type # TODO promote
        ct = lhsAddr.completeType
        irAdd = IRAdd(addTemporary(t, ct), lhsAddr, rhsAddr)
        addIR(irAdd)
        return irAdd.resultAddr

class Equal:
    def __init__(self, lhs, rhs):
        self.lhs = lhs
        self.rhs = rhs

    def __repr__(self):
        return "<Equal " + str(self.lhs) + " " + str(self.rhs) + ">"

    def visit(self):
        lhsAddr = self.lhs.visit()
        rhsAddr = self.rhs.visit()
        irEqual = IREqual(lhsAddr, rhsAddr)
        addIR(irEqual)
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
               | ptr_assign_expression
    '''
    p[0] = p[1]

def p_lvalue(p):
    'lvalue : ID'
    p[0] = Variable(p[1])

# def p_lvalue_deref(p):
#     'lvalue : STAR lvalue'
#     p[0] = Dereference(p[2])

def p_ptrlvalue(p):
    'ptrlvalue : STAR ID'
    p[0] = Variable(p[2])

def p_value_expression(p):
    'value_expression : equality'
    p[0] = p[1]

def p_equality_single(p):
    'equality : additive'
    p[0] = p[1]

def p_equality_equal(p):
    'equality : equality EQUAL additive'
    p[0] = Equal(p[1], p[3])

def p_additive_single(p):
    'additive : multiplicative'
    p[0] = p[1]

def p_additive_plus(p):
    'additive : additive PLUS multiplicative'
    p[0] = Add(p[1], p[3])

def p_multiplicative_single(p):
    'multiplicative : unary'
    p[0] = p[1]

def p_unary_deref(p):
    'unary : STAR unary'
    p[0] = Dereference(p[2])

def p_unary_addressOf(p):
    '''
    unary : AMPERSAND unary
    '''
    p[0] = AddressOf(p[2])

def p_unary_primary(p):
    'unary : primary'
    p[0] = p[1]

def p_primary_constant(p):
    '''
    primary : NUMBER
    '''
    # TODO all as char for now
    p[0] = Constant("char", int(p[1]))

def p_primary_variable(p):
    '''
    primary : ID
    '''
    print(f"Variable {p[1]}")
    p[0] = Variable(p[1])

def p_primary_fun_call(p):
    '''
    primary : function_expression
    '''
    print("Calling function " + str(p[1]))
    f = p[1]
    f.storeResult = True
    p[0] = p[1]

def p_variable_definition_expression(p):
    'var_def_expression : type ID'
    print(f"Variable definition {p[1]} {p[2]}")
    p[0] = VariableDefinition(p[1], p[2])

def p_type(p):
    '''type : base_type pointers
    '''
    print(f"Type found base_type {p[1]} pointers {p[2]}")
    p[0] = "*"*p[2] + p[1]

def p_base_type(p):
    '''base_type : CHAR
                 | INT
    '''
    p[0] = p[1]

def p_pointers_empty(p):
    '''
    pointers :
    '''
    p[0] = 0 # number of *

def p_pointers_more(p):
    '''pointers : pointers STAR
    '''
    p[0] = p[1] + 1

def p_variable_assignment_expression(p):
    'var_assign_expression : lvalue ASSIGN value_expression'
    print("Variable assignment ", p[1], p[3])
    p[0] = VariableAssignment(p[1], p[3])

def p_ptr_assignment_expression(p):
    'ptr_assign_expression : ptrlvalue ASSIGN value_expression'
    print("Dereferenced Pointer Assignment ", p[1], p[3])
    p[0] = DerefPointerAssignment(p[1], p[3])

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
