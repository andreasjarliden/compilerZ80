import ply.lex as lex
import re

re_linemarker = re.compile(r'\#\s*(\d+)\s+"([^"]+)"(?:\s+([1234 ]+))?')

reserved = {
        'return': 'RETURN',
        'void': 'VOID',
        'char': 'CHAR',
        'int': 'INT',
        'if': 'IF',
        'while': 'WHILE',
        'struct': 'STRUCT',
        'typedef': 'TYPEDEF'
        }

tokens = [
        'NUMBER',
        'HEX_NUMBER',
        'STRING',
        'ID',
        'LPARA',
        'RPARA',
        'LCURL',
        'RCURL',
        'SEMI',
        'ASSIGN',
        'EQUAL',
        'NOT_EQUAL',
        'LESS',
        'LESS_OR_EQUAL',
        'GREATER',
        'GREATER_OR_EQUAL',
        'PLUS',
        'MINUS',
        'OR',
        'COMMA',
        'STAR',
        'AMPERSAND',
        'PERIOD',
        ] + list(reserved.values())

t_NUMBER = r'[0-9]+'
t_HEX_NUMBER = r'0x[0-9a-fA-F]+'
t_STRING = r'"[^"]*"'
t_LPARA = r'\('
t_RPARA = r'\)'
t_LCURL = r'\{'
t_RCURL = r'\}'
t_SEMI = r';'
t_ASSIGN = r'='
t_EQUAL = r'=='
t_NOT_EQUAL = r'!='
t_LESS = r'<'
t_LESS_OR_EQUAL = r'<='
t_GREATER = r'>'
t_GREATER_OR_EQUAL = r'>='
t_PLUS = r'\+'
t_MINUS = r'-'
t_OR = r'\|'
t_COMMA = r','
t_STAR = r'\*'
t_AMPERSAND = r'&'
t_PERIOD = r'\.'

def t_ID(t):
    r'[a-zA-Z_][0-9a-zA-Z_]*'
    # If reserved, return that token type instead.  Otherwise, ID
    t.type = reserved.get(t.value, 'ID')
    return t

t_ignore = ' \t'

def t_NEWLINE(t):
    r'\n+'
    t.lexer.lineno += len(t.value)

def t_COMMENT(t):
    r'//[^\n]*'
    pass

def t_LINEMARKER(t):
    r'\#[^\n]*'
    match = re_linemarker.match(t.value)
    line = match.group(1)
    file = match.group(2)
    t.lexer.lineno = int(line) - 1
    t.lexer.file = file
    pass

def t_error(t):
    print(f"Illegal character '{t.value[0]}'")
    t.lexer.skip(1)

lexer = lex.lex()
lexer.file = None
