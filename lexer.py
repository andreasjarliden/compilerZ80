import ply.lex as lex

reserved = {
        'return': 'RETURN',
        'char': 'CHAR',
        'int': 'INT',
        'if': 'IF'
        }

tokens = [
        'NUMBER',
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
        'COMMA',
        'STAR',
        'AMPERSAND',
        ] + list(reserved.values())

t_NUMBER = r'[0-9]+'
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
t_COMMA = r','
t_STAR = r'\*'
t_AMPERSAND = r'&'

def t_ID(t):
    r'[a-zA-Z_][0-9a-zA-Z_]*'
    # If reserved, return that token type instead.  Otherwise, ID
    t.type = reserved.get(t.value, 'ID')
    return t

t_ignore = ' \t\n'

def t_COMMENT(t):
    r'//[^\n]*'
    pass

def t_error(t):
    print(f"Illegal character '{t.value[0]}'")
    t.lexer.skip(1)

lexer = lex.lex()
