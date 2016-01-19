import string
BOOL_AND = "&"
BOOL_OR = "|"
BOOL_NOT = "~"
LEFT_PAREN = "("
RIGHT_PAREN = ")"
BOOL_SYNTAX = {
    LEFT_PAREN: 0, 
    RIGHT_PAREN: 0, 
    BOOL_AND: 1, 
    BOOL_OR: 1, 
    BOOL_NOT: 2
}
IDENTIFIER = string.ascii_letters + "_"
WHITESPACE = " \t\r\n"

def tokenize(input_text, tokens, whitespace):
    max_len = max(len(token) for token in tokens)
    buf = ""
    buf_pos = -1
    for i, c in enumerate(input_text):
        if c in whitespace:
            continue
        elif c in tokens:
            if buf:
                yield buf_pos, buf
                buf = ""
            yield i, c
        elif c not in IDENTIFIER:
            raise ValueError("Invalid character at position %s" % i)
        else:
            if not buf:
                buf_pos = i
            buf += c
    if buf:
        yield buf_pos, buf
        
def infix_to_postfix(tokens, syntax):
    stack = []
    for pos, token in tokens:
        if token == LEFT_PAREN:
            stack.append((pos, token))
        elif token == RIGHT_PAREN:
            while True:
                try:
                    pos, token = stack.pop()
                except IndexError:
                    fmt = "Invalid right paren at pos %s"
                    raise ValueError(fmt % pos)
                if token == LEFT_PAREN:
                    break
                else:
                    yield pos, token
        elif token in syntax:
            try:
                pos, item = stack[-1]
            except IndexError:
                pass
            else:
                if item in syntax:
                    if syntax[item] > syntax[token]:
                        yield stack.pop()
            stack.append((pos, token))
        else:
            yield pos, token
    while stack:
        yield stack.pop()

def eval_bool(input, truths):
    stack = []
    tokens = tokenize(input, BOOL_SYNTAX, WHITESPACE)
    tokens = infix_to_postfix(tokens, BOOL_SYNTAX)
    for pos, token in tokens:
        if token == BOOL_NOT:
            try:
                pos_sym, sym = stack.pop()
            except IndexError:
                raise ValueError(s)
            else:
                stack.append((pos_sym, not sym))
        elif token in BOOL_SYNTAX:
            try:
                pos_a, a = stack.pop()
                pos_b, b = stack.pop()
            except IndexError:
                raise ValueError(s)
            else:
                if a in BOOL_SYNTAX or b in BOOL_SYNTAX:
                    raise ValueError(s)
                if token == BOOL_AND:
                    stack.append((pos_a, a and b))
                elif token == BOOL_OR:
                    stack.append((pos_a, a or b))
                else:
                    raise ValueError(s)
        else:
            stack.append((pos, True if token in truths else False))
    pos, token = stack.pop()
    return token
