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

class EvalError(ValueError):
    def __init__(self, position, token):
        self.position = position
        self.token = token
        s = "Invalid token %s at position %s"
        super(EvalError, self).__init__(s % (self.token, self.position))

def tokenize(input_text, tokens, whitespace):
    max_len = max(len(token) for token in tokens)
    buf = ""
    buf_pos = -1
    for i, c in enumerate(input_text):
        if c in whitespace:
            if buf:
                yield buf_pos, buf
                buf = ""
        elif c in tokens:
            if buf:
                yield buf_pos, buf
                buf = ""
            yield i, c
        elif c not in IDENTIFIER:
            raise EvalError(i, c)
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
                    raise EvalError(pos, token)
                if token == LEFT_PAREN:
                    break
                else:
                    yield pos, token
        elif token in syntax:
            try:
                next_pos, next_token = stack[-1]
            except IndexError:
                pass
            else:
                if next_token in syntax:
                    if syntax[next_token] == syntax[token]:
                        raise EvalError(pos, token)
                    elif syntax[next_token] > syntax[token]:
                        yield stack.pop()
            stack.append((pos, token))
        else:
            yield pos, token
    while stack:
        yield stack.pop()

def boolify(token, truths):
    if token in truths:
        return True
    elif token is True:
        return True
    else:
        return False

def eval_bool(input, truths):
    stack = []
    print "foo"
    tokens = tokenize(input, BOOL_SYNTAX, WHITESPACE)
    tokens = infix_to_postfix(tokens, BOOL_SYNTAX)
    tokens = list(tokens)
    print tokens
    for pos, token in tokens:
        if token == BOOL_NOT:
            try:
                pos_sym, sym = stack.pop()
            except IndexError:
                raise EvalError(pos, token)
            else:
                stack.append((pos_sym, not boolify(sym, truths)))
        elif token in BOOL_SYNTAX:
            try:
                pos_a, a = stack.pop()
                pos_b, b = stack.pop()
            except IndexError:
                raise EvalError(pos, token)
            else:
                if a in BOOL_SYNTAX or b in BOOL_SYNTAX:
                    raise EvalError(s)
                a = boolify(a, truths)
                b = boolify(b, truths)
                if token == BOOL_AND:
                    stack.append((pos_a, a and b))
                elif token == BOOL_OR:
                    stack.append((pos_a, a or b))
                else:
                    raise EvalError(pos, token)
        else:
            stack.append((pos, token))
    pos, token = stack.pop()
    if stack:
        raise EvalError(pos, token)
    return boolify(token, truths)
