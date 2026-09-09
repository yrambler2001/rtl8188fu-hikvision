# Variant spec for ez_wifi_config.c:ez_strsep - stage 2, the coalescing tie.
#
# Stage 1 found the block layout: writing the escape test as two `if`s with a
# duplicated memmove (cross-jumping merges them again) reproduces the shipped
# order exactly - three instructions from identical, and the only remaining
# difference is one copy on the loop back edge.
#
# The loop is
#
#	q = p;
#	c = *p++;
#
# so `q` is a copy of the loop PHI and `p + 1` is the PHI's back-edge value.
# Exactly one of them can be coalesced with the PHI.  The shipped build
# coalesces `p + 1` (`mov r4, r5 / ldrb r3, [r5], #1`, nothing on the back
# edge); ours coalesces `q` and pays a `mov r5, r4` to close the loop.
#
# GCC 6's gimple_can_coalesce_p starts with `if (t1 == t2)` - a *pointer*
# comparison of the two types - and only falls back to TYPE_CANONICAL plus
# types_compatible_p otherwise.  `char` and `unsigned char` are distinct types
# with distinct canonical types even where char is unsigned, so giving `q` a
# different character pointer type from `p` makes that pair uncoalescable and
# leaves `p + 1` as the only candidate.  The driver builds with
# -Wno-pointer-sign, so the mixed assignments are not even warnings.
UNIT = 'ez_wifi_config'
FUNC = 'ez_strsep'

AXES = {
    'tp': ['char *', 'u8 *', 'unsigned char *', 'signed char *', 's8 *'],
    'tq': ['char *', 'u8 *', 'unsigned char *', 'signed char *', 's8 *'],
    'ts': ['char *', 'u8 *'],
    'ctype': ['char', 'int', 'u8'],
    'esc': ['x0', 'x1'],
}

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
}


def render(c):
    tp, tq, ts = c['tp'], c['tq'], c['ts']
    cast_s = '' if ts == 'char *' else '(%s)' % ts
    return ('char *ez_strsep(char **stringp, char delim, char esc)\n'
            '{\n'
            '\t%ss = %s*stringp;\n' % (ts, cast_s) +
            '\t%sp;\n' % tp +
            '\t%sq;\n' % tq +
            '\t%s c;\n' % c['ctype'] +
            '\n'
            '\tif (s == NULL)\n\t\treturn (char *)s;\n\n'
            "\tif (*s == '\\0')\n\t\treturn NULL;\n\n"
            '\tp = (%s)s;\n' % tp +
            '\tfor (;;) {\n'
            '\t\tq = (%s)p;\n' % tq +
            '\t\tc = *p++;\n'
            "\t\tif (c == '\\0') {\n"
            '\t\t\t*stringp = NULL;\n'
            '\t\t\treturn (char *)s;\n'
            '\t\t}\n'
            + ESC[c['esc']] +
            '\t\tif (c == delim) {\n'
            "\t\t\t*q = '\\0';\n"
            '\t\t\t*stringp = (char *)(q + 1);\n'
            '\t\t\treturn (char *)s;\n'
            '\t\t}\n'
            '\t}\n'
            '}\n')
