# Variant spec for ez_wifi_config.c:ez_strsep.
#
# Right size (156 bytes), 26 differing words, and the cause is one out-of-SSA
# coalescing choice.  The loop is
#
#	q = p;
#	c = *p++;
#
# so in GIMPLE `q` is literally the loop PHI's own value and exactly one of
# {PHI, p+1} and {PHI, q} can be coalesced.  The shipped build coalesces the
# post-increment pseudo with the PHI - `mov r4, r5 / ldrb r3, [r5], #1` and
# nothing on the back edge - and ours coalesces `q` instead, which costs a
# `mov r7, r4` on the back edge.
#
# Sweep the loop shape, the declaration order, the types (a typedef of a type
# is a distinct tree node, see process_config_vars_types.py) and the two forms
# of the escape test.
UNIT = 'ez_wifi_config'
FUNC = 'ez_strsep'

AXES = {
    'ctype': ['char', 'int', 'u8', 's8', 'unsigned char', 'signed char'],
    'decl': ['e0', 'e1', 'e2', 'e3', 'e4'],
    'step': ['w0', 'w1', 'w2', 'w3', 'w4', 'w5', 'w6'],
    'esc': ['x0', 'x1', 'x2', 'x3'],
    'loop': ['L0', 'L1', 'L2'],
}

DECLS = {
    'e0': "\tchar *s = *stringp;\n\tchar *p, *q;\n\t%(c)s c;\n",
    'e1': "\tchar *s = *stringp;\n\tchar *p;\n\tchar *q;\n\t%(c)s c;\n",
    'e2': "\tchar *s = *stringp;\n\t%(c)s c;\n\tchar *p, *q;\n",
    'e3': "\tchar *p, *q;\n\t%(c)s c;\n\tchar *s = *stringp;\n",
    'e4': "\tchar *s = *stringp;\n\tchar *q, *p;\n\t%(c)s c;\n",
}

# how one step of the walk is written
STEP = {
    'w0': "\t\tq = p;\n\t\tc = *p++;\n",
    'w1': "\t\tq = p++;\n\t\tc = *q;\n",
    'w2': "\t\tc = *p;\n\t\tq = p;\n\t\tp++;\n",
    'w3': "\t\tq = p;\n\t\tc = *q;\n\t\tp = q + 1;\n",
    'w4': "\t\tc = *p++;\n\t\tq = p - 1;\n",
    'w5': "\t\tq = p;\n\t\tc = *p;\n\t\tp++;\n",
    'w6': "\t\tc = *p;\n\t\tp++;\n\t\tq = p - 1;\n",
}

# the escape test
ESC = {
    'x0': ("\t\tif (c == esc) {\n"
           "\t\t\tif (*p == esc || *p == delim) {\n"
           "\t\t\t\tmemmove(q, p, strlen(q));\n"
           "\t\t\t\tcontinue;\n"
           "\t\t\t}\n"
           "\t\t}\n"),
    'x1': ("\t\tif (c == esc) {\n"
           "\t\t\tif (*p == esc) {\n"
           "\t\t\t\tmemmove(q, p, strlen(q));\n"
           "\t\t\t\tcontinue;\n"
           "\t\t\t}\n"
           "\t\t\tif (*p == delim) {\n"
           "\t\t\t\tmemmove(q, p, strlen(q));\n"
           "\t\t\t\tcontinue;\n"
           "\t\t\t}\n"
           "\t\t}\n"),
    'x2': ("\t\tif (c == esc && (*p == esc || *p == delim)) {\n"
           "\t\t\tmemmove(q, p, strlen(q));\n"
           "\t\t\tcontinue;\n"
           "\t\t}\n"),
    'x3': ("\t\tif (c == esc) {\n"
           "\t\t\tif (*p == delim || *p == esc) {\n"
           "\t\t\t\tmemmove(q, p, strlen(q));\n"
           "\t\t\t\tcontinue;\n"
           "\t\t\t}\n"
           "\t\t}\n"),
}

TAIL = ("\t\tif (c == delim) {\n"
        "\t\t\t*q = '\\0';\n"
        "\t\t\t*stringp = q + 1;\n"
        "\t\t\treturn s;\n"
        "\t\t}\n")

NUL = ("\t\tif (c == '\\0') {\n"
       "\t\t\t*stringp = NULL;\n"
       "\t\t\treturn s;\n"
       "\t\t}\n")


def render(c):
    decl = DECLS[c['decl']] % {'c': c['ctype']}
    body = STEP[c['step']] + NUL + ESC[c['esc']] + TAIL
    if c['loop'] == 'L0':
        loop = '\tfor (;;) {\n' + body + '\t}\n'
    elif c['loop'] == 'L1':
        loop = '\twhile (1) {\n' + body + '\t}\n'
    else:
        loop = '\tdo {\n' + body + '\t} while (1);\n'
    return ('char *ez_strsep(char **stringp, char delim, char esc)\n{\n'
            + decl +
            '\n'
            '\tif (s == NULL)\n\t\treturn s;\n\n'
            "\tif (*s == '\\0')\n\t\treturn NULL;\n\n"
            '\tp = s;\n' + loop + '}\n')
