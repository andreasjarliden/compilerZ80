from lexer import tokens
import ply.yacc as yacc
from address import Constant
from astnodes import *
import sys

# Start symbol at the top
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
              | while_expression
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

def p_ptrlvalue(p):
    'ptrlvalue : STAR ID'
    p[0] = Variable(p[2])

def p_value_expression(p):
    'value_expression : comparisson'
    p[0] = p[1]

def p_comparisson_single(p):
    'comparisson : additive'
    p[0] = p[1]

def p_comparisson_equal(p):
    '''comparisson : comparisson EQUAL additive
                   | comparisson NOT_EQUAL additive
                   | comparisson LESS additive
                   | comparisson LESS_OR_EQUAL additive
                   | comparisson GREATER additive
                   | comparisson GREATER_OR_EQUAL additive'''
    p[0] = Relation(p[2], p[1], p[3])

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
    primary : constant
    '''
    # TODO all as char for now
    if isinstance(p[1], String):
        p[0] = StringConstant(p[1])
    else:
        p[0] = Constant("char", p[1])

def p_primary_variable(p):
    '''
    primary : ID
    '''
    p[0] = Variable(p[1])

def p_primary_fun_call(p):
    '''
    primary : function_expression
    '''
    f = p[1]
    f.storeResult = True
    p[0] = p[1]

def p_variable_definition_expression(p):
    'var_def_expression : type ID'
    p[0] = VariableDefinition(p[1], p[2])

def p_variable_definition_expression_value(p):
    'var_def_expression : type ID ASSIGN value_expression'
    # 'var_def_expression : type ID ASSIGN constant'
    p[0] = VariableDefinition(p[1], p[2], p[4])

def p_type(p):
    '''type : base_type pointers
    '''
    p[0] = p[1] + "*"*p[2]

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
    p[0] = VariableAssignment(p[1], p[3])

def p_ptr_assignment_expression(p):
    'ptr_assign_expression : ptrlvalue ASSIGN value_expression'
    p[0] = DerefPointerAssignment(p[1], p[3])

def p_return_expression(p):
    'return_expression : RETURN value_expression'
    p[0] = Return(p[2])

def p_function_expression_no_args(p):
    'function_expression : ID LPARA RPARA'
    p[0] = FunctionCall(p[1])

def p_function_expression_args(p):
    'function_expression : ID LPARA expr_list RPARA'
    print(p[1])
    print(p[3])
    print(FunctionCall)
    p[0] = FunctionCall(p[1], p[3])

def p_function_definition_no_args(p):
    'function_definition : type ID LPARA RPARA LCURL statement_list RCURL'
    node = Function(p[1], p[2], p[6])
    p[0] = node

def p_function_definition_args(p):
    'function_definition : type ID LPARA arg_list RPARA LCURL statement_list RCURL'
    node = Function(p[1], p[2], p[7], p[4])
    p[0] = node

def p_if_expression(p):
    '''
    if_expression : IF LPARA value_expression RPARA block
    '''
    p[0] = If(p[3], p[5])

def p_while_expression(p):
    '''
    while_expression : WHILE LPARA value_expression RPARA block
    '''
    p[0] = While(p[3], p[5])

def p_block(p):
    'block : LCURL statement_list RCURL'
    p[0] = p[2]

def p_block_single(p):
    'block : statement'
    p[0] = [p[1]]

def p_block_empty(p):
    'block : LCURL RCURL'
    p[0] = []

def p_expr_list_single(p):
    'expr_list : value_expression'
    p[0] = [p[1]]

def p_expr_list_multiple(p):
    'expr_list : expr_list COMMA value_expression'
    p[0] = p[1] + [p[3]]

def p_arg_list_single(p):
    'arg_list : arg'
    p[0] = [p[1]]

def p_arg_list_multiple(p):
    'arg_list : arg_list COMMA arg'
    p[0] = p[1] + [p[3]]

def p_arg(p):
    'arg : type ID'
    p[0] = Argument(p[1], p[2])

def p_error(p):
    if p:
        print(f"Parse error: {p.value} {p}")
    else:
        print("Unexpected end of file");
    sys.exit(1);

def p_constant_number(p):
    '''
    constant : NUMBER
    '''
    p[0] = int(p[1])

def p_constant_string(p):
    '''
    constant : STRING
    '''
    p[0] = String(p[1][1:-1])

parser = yacc.yacc()
