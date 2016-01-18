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
    for i, c in enumerate(input_text):
        if c in whitespace:
            continue
        elif c in tokens:
            if buf:
                yield buf
                buf = ""
            yield c
        elif c not in IDENTIFIER:
            raise ValueError("Invalid character at position %s" % i)
        else:
            buf += c
    if buf:
        yield buf
        
def infix_to_postfix(tokens, syntax):
    stack = []
    for token in tokens:
        if token == LEFT_PAREN:
            stack.append(token)
        elif token == RIGHT_PAREN:
            while True:
                token = stack.pop()
                if token == LEFT_PAREN:
                    break
                else:
                    yield token
        elif token in syntax:
            try:
                item = stack[-1]
            except IndexError:
                pass
            else:
                if item in syntax:
                    if syntax[item] > syntax[token]:
                        yield stack.pop()
            stack.append(token)
        else:
            yield token
    while stack:
        yield stack.pop()

def eval_bool(input, truths):
    stack = []
    tokens = tokenize(input, BOOL_SYNTAX, WHITESPACE)
    tokens = list(infix_to_postfix(tokens, BOOL_SYNTAX))
    for token in tokens:
        if token == BOOL_NOT:
            stack.append(not stack.pop())
        elif token in BOOL_SYNTAX:
            if token == BOOL_AND:
                stack.append(stack.pop() and stack.pop())
            elif token == BOOL_OR:
                stack.append(stack.pop() or stack.pop())
            else:
                raise ValueError(token)
        else:
            stack.append(True if token in truths else False)
    return stack.pop()import string
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
    for i, c in enumerate(input_text):
        if c in whitespace:
            continue
        elif c in tokens:
            if buf:
                yield buf
                buf = ""
            yield c
        elif c not in IDENTIFIER:
            raise ValueError("Invalid character at position %s" % i)
        else:
            buf += c
    if buf:
        yield buf
        
def infix_to_postfix(tokens, syntax):
    stack = []
    for token in tokens:
        if token == LEFT_PAREN:
            stack.append(token)
        elif token == RIGHT_PAREN:
            while True:
                token = stack.pop()
                if token == LEFT_PAREN:
                    break
                else:
                    yield token
        elif token in syntax:
            try:
                item = stack[-1]
            except IndexError:
                pass
            else:
                if item in syntax:
                    if syntax[item] > syntax[token]:
                        yield stack.pop()
            stack.append(token)
        else:
            yield token
    while stack:
        yield stack.pop()

def eval_bool(input, truths):
    stack = []
    tokens = tokenize(input, BOOL_SYNTAX, WHITESPACE)
    tokens = list(infix_to_postfix(tokens, BOOL_SYNTAX))
    for token in tokens:
        if token == BOOL_NOT:
            stack.append(not stack.pop())
        elif token in BOOL_SYNTAX:
            if token == BOOL_AND:
                stack.append(stack.pop() and stack.pop())
            elif token == BOOL_OR:
                stack.append(stack.pop() or stack.pop())
            else:
                raise ValueError(token)
        else:
            stack.append(True if token in truths else False)
    return stack.pop()
