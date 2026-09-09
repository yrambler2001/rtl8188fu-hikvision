# Variant spec for ez_wifi_config.c:ez_strsep - stage 4, the loop carrier.
#
# Out-of-SSA is where the last instruction goes.  `q = p` is copy-propagated
# away, so the loop PHI `p_1` *is* `q`, and `p_10 = p_1 + 1` is defined while
# `p_1` is still live (memmove, strlen and the NUL store all read it after the
# increment).  They interfere, the PHI cannot be coalesced with its back-edge
# value, and the back edge gets a copy.  The shipped build has no such copy,
# so there the PHI's last use must be the increment - i.e. the "old pointer"
# has a name of its own that is live across it.
#
# These are loop shapes where the two pointers cannot collapse into one SSA
# name: the loop carries the *old* pointer, or the *new* one, or an index, or
# there is no second pointer at all and the old position is recomputed.
UNIT = 'ez_wifi_config'
FUNC = 'ez_strsep'

AXES = {
    'shape': ['c0', 'c1', 'c2', 'c3', 'c4', 'c5', 'c6', 'c7'],
    'esc': ['x0', 'x1'],
}

HEAD = ('char *ez_strsep(char **stringp, char delim, char esc)\n'
        '{\n')


def esc_block(kind, q, p, mmsrc=None):
    mm = '\t\t\t\tmemmove(%s, %s, strlen(%s));\n' % (q, mmsrc or p, q)
    if kind == 'x0':
        return ("\t\tif (c == esc) {\n"
                "\t\t\tif (*%s == esc || *%s == delim) {\n" % (p, p)
                + mm + "\t\t\t\tcontinue;\n\t\t\t}\n\t\t}\n")
    return ("\t\tif (c == esc) {\n"
            "\t\t\tif (*%s == esc) {\n" % p + mm + "\t\t\t\tcontinue;\n\t\t\t}\n"
            "\t\t\tif (*%s == delim) {\n" % p + mm + "\t\t\t\tcontinue;\n\t\t\t}\n"
            "\t\t}\n")


def render(c):
    s, k = c['shape'], c['esc']
    pre = ('\tchar *s = *stringp;\n')
    guard = ('\n\tif (s == NULL)\n\t\treturn s;\n\n'
             "\tif (*s == '\\0')\n\t\treturn NULL;\n\n")
    if s == 'c0':                       # baseline: carry p, snapshot q
        decl = '\tchar *p, *q;\n\tchar c;\n'
        body = ('\tp = s;\n\tfor (;;) {\n'
                '\t\tq = p;\n\t\tc = *p++;\n'
                "\t\tif (c == '\\0') {\n\t\t\t*stringp = NULL;\n\t\t\treturn s;\n\t\t}\n"
                + esc_block(k, 'q', 'p') +
                "\t\tif (c == delim) {\n\t\t\t*q = '\\0';\n"
                '\t\t\t*stringp = q + 1;\n\t\t\treturn s;\n\t\t}\n\t}\n')
    elif s == 'c1':                     # carry q, derive p
        decl = '\tchar *p, *q;\n\tchar c;\n'
        body = ('\tq = s;\n\tfor (;;) {\n'
                '\t\tp = q + 1;\n\t\tc = *q;\n'
                "\t\tif (c == '\\0') {\n\t\t\t*stringp = NULL;\n\t\t\treturn s;\n\t\t}\n"
                + esc_block(k, 'q', 'p') +
                "\t\tif (c == delim) {\n\t\t\t*q = '\\0';\n"
                '\t\t\t*stringp = p;\n\t\t\treturn s;\n\t\t}\n'
                '\t\tq = p;\n\t}\n')
    elif s == 'c2':                     # no q: recompute p - 1
        decl = '\tchar *p;\n\tchar c;\n'
        body = ('\tp = s;\n\tfor (;;) {\n'
                '\t\tc = *p++;\n'
                "\t\tif (c == '\\0') {\n\t\t\t*stringp = NULL;\n\t\t\treturn s;\n\t\t}\n"
                + esc_block(k, 'p - 1', 'p') +
                "\t\tif (c == delim) {\n\t\t\t*(p - 1) = '\\0';\n"
                '\t\t\t*stringp = p;\n\t\t\treturn s;\n\t\t}\n\t}\n')
    elif s == 'c3':                     # index carrier
        decl = '\tchar *p, *q;\n\tchar c;\n\tint k;\n'
        body = ('\tk = 0;\n\tfor (;;) {\n'
                '\t\tq = s + k;\n\t\tp = s + k + 1;\n\t\tc = s[k++];\n'
                "\t\tif (c == '\\0') {\n\t\t\t*stringp = NULL;\n\t\t\treturn s;\n\t\t}\n"
                + esc_block(k, 'q', 'p') +
                "\t\tif (c == delim) {\n\t\t\t*q = '\\0';\n"
                '\t\t\t*stringp = p;\n\t\t\treturn s;\n\t\t}\n\t}\n')
    elif s == 'c4':                     # snapshot q, advance p at the bottom
        decl = '\tchar *p, *q;\n\tchar c;\n'
        body = ('\tp = s;\n\tfor (;;) {\n'
                '\t\tq = p;\n\t\tc = *q;\n\t\tp = q + 1;\n'
                "\t\tif (c == '\\0') {\n\t\t\t*stringp = NULL;\n\t\t\treturn s;\n\t\t}\n"
                + esc_block(k, 'q', 'p') +
                "\t\tif (c == delim) {\n\t\t\t*q = '\\0';\n"
                '\t\t\t*stringp = p;\n\t\t\treturn s;\n\t\t}\n\t}\n')
    elif s == 'c5':                     # q is the memmove destination only
        decl = '\tchar *p, *q;\n\tchar c;\n'
        body = ('\tp = s;\n\tq = s;\n\tfor (;;) {\n'
                '\t\tq = p;\n\t\tc = *p++;\n'
                "\t\tif (c == '\\0') {\n\t\t\t*stringp = NULL;\n\t\t\treturn s;\n\t\t}\n"
                + esc_block(k, 'q', 'p', mmsrc='q + 1') +
                "\t\tif (c == delim) {\n\t\t\t*q = '\\0';\n"
                '\t\t\t*stringp = q + 1;\n\t\t\treturn s;\n\t\t}\n\t}\n')
    elif s == 'c6':                     # while-form with the test in the head
        decl = '\tchar *p, *q;\n\tchar c;\n'
        body = ('\tp = s;\n\tq = p;\n'
                "\twhile ((c = *p++) != '\\0') {\n"
                + esc_block(k, 'q', 'p') +
                "\t\tif (c == delim) {\n\t\t\t*q = '\\0';\n"
                '\t\t\t*stringp = q + 1;\n\t\t\treturn s;\n\t\t}\n'
                '\t\tq = p;\n\t}\n'
                '\t*stringp = NULL;\n\treturn s;\n')
    else:                               # c7: two carriers, both updated
        decl = '\tchar *p, *q;\n\tchar c;\n'
        body = ('\tp = s;\n\tq = s;\n\tfor (;;) {\n'
                '\t\tc = *p;\n\t\tq = p;\n\t\tp = p + 1;\n'
                "\t\tif (c == '\\0') {\n\t\t\t*stringp = NULL;\n\t\t\treturn s;\n\t\t}\n"
                + esc_block(k, 'q', 'p') +
                "\t\tif (c == delim) {\n\t\t\t*q = '\\0';\n"
                '\t\t\t*stringp = p;\n\t\t\treturn s;\n\t\t}\n\t}\n')
    return HEAD + pre + decl + guard + body + '}\n'
