from lexer import tokens, lexer
import ply.yacc as yacc
from address import Constant
from astnodes import *
from error import Location, CompileError
from type_defs import PointerType
import sys

def loc(p, i=1):
    return Location(
        file=p.lexer.file,
        line=p.lineno(i),
    )

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
              | value_expression SEMI
              | function_declaration
              | function_definition
              | if_expression
              | while_expression
              | typedef_statement SEMI
              | continue SEMI
    '''
    p[0] = p[1]

def p_expression(p):
    '''
    expression : return_expression
               | function_expression
               | struct_definition_expression
               | var_def_expression
    '''
    p[0] = p[1]

def p_value_expression(p):
    'value_expression : assignment'
    p[0] = p[1]

def p_assignment_single(p):
    'assignment : comparisson'
    p[0] = p[1]

def p_assignment_regular(p):
    'assignment : assignment ASSIGN comparisson'
    p[0] = VariableAssignment(p[1], p[3], location=loc(p, 2))

def p_comparisson_single(p):
    'comparisson : bitwise'
    p[0] = p[1]

def p_comparisson_op(p):
    '''comparisson : comparisson EQUAL bitwise
                   | comparisson NOT_EQUAL bitwise
                   | comparisson LESS bitwise
                   | comparisson LESS_OR_EQUAL bitwise
                   | comparisson GREATER bitwise
                   | comparisson GREATER_OR_EQUAL bitwise'''
    p[0] = Relation(p[2], p[1], p[3], location=loc(p, 2))

def p_bitwise_single(p):
    'bitwise : additive'
    p[0] = p[1]

def p_bitwise_or(p):
    '''bitwise : bitwise OR additive'''
    p[0] = BitwiseOr(p[1], p[3])        

def p_bitwise_and(p):
    '''bitwise : bitwise AMPERSAND additive'''
    p[0] = BitwiseAnd(p[1], p[3])        

def p_additive_single(p):
    'additive : multiplicative'
    p[0] = p[1]

def p_additive_plus(p):
    'additive : additive PLUS multiplicative'
    p[0] = Add(p[1], p[3], location=loc(p, 2))

def p_additive_minus(p):
    'additive : additive MINUS multiplicative'
    p[0] = Subtraction(p[1], p[3])

def p_multiplicative_single(p):
    'multiplicative : unary'
    p[0] = p[1]

def p_multiplicative_mul(p):
    'multiplicative : multiplicative STAR unary'
    p[0] = Mul(p[1], p[3])

def p_unary_sizeof_expression(p):
    'unary : SIZEOF LPARA value_expression RPARA'
    p[0] = SizeOf(p[3], location=loc(p, 1))

def p_unary_sizeof_type(p):
    'unary : SIZEOF LPARA type RPARA'
    p[0] = SizeOf(p[3], location=loc(p, 1))

def p_unary_cast(p):
    'unary : LPARA type RPARA unary'
    p[0] = Cast(p[2], p[4], location=loc(p, 2))

def p_unary_deref(p):
    'unary : STAR unary'
    p[0] = Dereference(p[2], location=loc(p))

def p_unary_addressOf(p):
    '''
    unary : AMPERSAND unary
    '''
    p[0] = AddressOf(p[2])

def p_unary_struct_field(p):
    'unary : unary PERIOD ID'
    p[0] = StructFieldReference(p[1], p[3], location=loc(p, 3))

def p_unary_struct_pointer_field(p):
    'unary : unary ARROW ID'
    p[0] = StructFieldReference(Dereference(p[1], location=loc(p, 3)), p[3], location=loc(p, 3))

def p_unary_primary(p):
    'unary : grouping'
    p[0] = p[1]

def p_grouping_paran(p):
    'grouping : LPARA value_expression RPARA' 
    p[0] = p[2]

def p_grouping_primary(p):
    'grouping : primary'
    p[0] = p[1]

def p_primary_constant(p):
    '''
    primary : constant
    '''
    p[0] = p[1]

def p_primary_variable(p):
    '''
    primary : ID
    '''
    p[0] = Variable(p[1], location=loc(p))

def p_primary_fun_call(p):
    '''
    primary : function_expression
    '''
    f = p[1]
    f.setStoreResult()
    p[0] = p[1]

def p_struct_definition_expression(p):
    'struct_definition_expression : STRUCT ID LCURL var_list RCURL'
    p[0] = StructDefinition(p[2], p[4], location=loc(p, 2))

def p_variable_definition_expression(p):
    'var_def_expression : type ID'
    p[0] = VariableDefinition(p[1], p[2], location=loc(p, 2))

def p_variable_definition_expression_value(p):
    'var_def_expression : type ID ASSIGN value_expression'
    # 'var_def_expression : type ID ASSIGN constant'
    p[0] = VariableDefinition(p[1], p[2], p[4], location=loc(p, 2))

def p_typedef(p):
    'typedef_statement : TYPEDEF type ID'
    p[0] = TypeDef(p[3], p[2], location=loc(p, 1))

def p_continue(p):
    'continue : CONTINUE'
    p[0] = Continue(location=loc(p, 1))

def p_type(p):
    '''type : base_type pointers
    '''
    t = p[1]
    for i in range(0, p[2]):
        t = PointerType(t)
    p[0] = t

def p_base_type(p):
    '''base_type : CHAR
                 | INT
                 | VOID
                 | ID
    '''
    p[0] = p[1]

def p_base_type_struct(p):
    # '''base_type | ID'''
    '''base_type : STRUCT ID
    '''
    p[0] = StructType(p[2], ())

def p_pointers_empty(p):
    '''
    pointers :
    '''
    p[0] = 0 # number of *

def p_pointers_more(p):
    '''pointers : pointers STAR
    '''
    p[0] = p[1] + 1

def p_return_expression(p):
    'return_expression : RETURN value_expression'
    p[0] = Return(p[2])

def p_function_expression_no_args(p):
    'function_expression : ID LPARA RPARA'
    p[0] = FunctionCall(p[1], location=loc(p))

def p_function_expression_args(p):
    'function_expression : ID LPARA expr_list RPARA'
    p[0] = FunctionCall(p[1], p[3], location=loc(p))

def p_function_declaration_no_args(p):
    'function_declaration : type ID LPARA RPARA SEMI'
    node = FunctionDeclaration(p[1], p[2])
    p[0] = node

def p_function_declaration_args(p):
    'function_declaration : type ID LPARA arg_list RPARA SEMI'
    node = FunctionDeclaration(p[1], p[2], p[4])
    p[0] = node

def p_function_definition_no_args(p):
    'function_definition : type ID LPARA RPARA LCURL statement_list RCURL'
    node = FunctionDefinition(p[1], p[2], p[6], location=loc(p, 2))
    p[0] = node

def p_function_definition_args(p):
    'function_definition : type ID LPARA arg_list RPARA LCURL statement_list RCURL'
    node = FunctionDefinition(p[1], p[2], p[7], p[4], location=loc(p, 2))
    p[0] = node

def p_if_expression(p):
    '''
    if_expression : IF LPARA value_expression RPARA block
    '''
    p[0] = If(p[3], p[5])

def p_if_expression_else(p):
    '''
    if_expression : IF LPARA value_expression RPARA block ELSE block
    '''
    p[0] = If(p[3], p[5], p[7])

def p_while_expression(p):
    '''
    while_expression : WHILE LPARA value_expression RPARA block
    '''
    p[0] = While(p[3], p[5], location=loc(p))

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

def p_var_list_single(p):
    'var_list : var_def_expression SEMI'
    p[0] = (p[1],)

def p_var_list_multiple(p):
    'var_list : var_list var_def_expression SEMI'
    p[0] = p[1] + (p[2],)

def p_arg_list_single(p):
    'arg_list : arg'
    p[0] = (p[1],)

def p_arg_list_multiple(p):
    'arg_list : arg_list COMMA arg'
    p[0] = p[1] + (p[3],)

def p_arg_list_vararg(p):
    'arg_list : arg_list COMMA ELLIPSIS'
    p[0] = p[1] + (VarArg(),)

def p_arg(p):
    'arg : type ID'
    p[0] = Argument(p[1], p[2])

def p_error(p):
    if p:
        file = p.lexer.file
        line = p.lineno
        raise CompileError(f"Syntax error {p}", Location(file, line))
    else:
        raise CompileError(f"Unexpected end of file", Location(lexer.file, lexer.lineno))

def p_constant_number(p):
    '''
    constant : number
    '''
    i = p[1]
    if i < 255:
        p[0] = Constant("char", i)
    elif i < 65535:
        p[0] = Constant("int", i)
    else:
        error()

def p_number_dec(p):
    '''
    number : DEC_NUMBER 
    '''
    p[0] = int(p[1])

def p_constant_hex_number(p):
    '''
    number : HEX_NUMBER
    '''
    p[0] = int(p[1], 0)

def p_constant_char(p):
    '''
    constant : CHAR_LITTERA
    '''
    s = p[1].encode("utf-8").decode("unicode_escape")
    if len(s) > 3:
        raise CompileError(f"Character littera longer than one character {s}", loc(p, 1))
    p[0] = Constant("char", ord(s[1]))

def p_constant_string(p):
    '''
    constant : STRING
    '''
    p[0] = StringConstant(String(p[1][1:-1], location=loc(p, 1)))

parser = yacc.yacc()
