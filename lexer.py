import ply.lex as lex

reserved = {
        'return': 'RETURN',
        'char': 'CHAR',
        'int': 'INT',
        'if': 'IF'
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
        'EQUAL',
        'PLUS',
        'COMMA',
        ] + list(reserved.values())

t_NUMBER = r'[0-9]+'
t_LPARA = r'\('
t_RPARA = r'\)'
t_LCURL = r'\{'
t_RCURL = r'\}'
t_SEMI = r';'
t_ASSIGN = r'='
t_EQUAL = r'=='
t_PLUS = r'\+'
t_COMMA = r','

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
