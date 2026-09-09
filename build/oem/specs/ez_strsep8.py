# ez_strsep - stage 8: the delimiter path's `*stringp` store.
#
# Four words remain.  The shipped build routes the delimiter path through the
# *same* store the end-of-string path uses:
#
#	mov  r2, #0        add  r3, r4, #1        strb r2, [r4]     b .+64
#	                                    .+64: str  r3, [r7]
#
# `*stringp = NULL` became `str r3, [r7]` because cse1 knows r3 (the loaded
# character) is zero on that edge, and the delimiter path puts `q + 1` in the
# same r3 and cross-jumps onto it.  Ours computes the address *after* the NUL
# store, so `auto_inc_dec` folds the two into `strb r3, [r4], #1`, the value
# stored to `*stringp` is `q` itself in r4, and the two stores are no longer
# the same instruction, so cross-jumping cannot merge them.
#
# So the question is only which spelling of the delimiter block computes
# `q + 1` before the NUL store, into a register the allocator is free to make
# r3.  This sweeps every ordering, plus a named temporary, plus the store
# widths and the escape-test spelling that were already known to matter.
UNIT = 'ez_wifi_config'
FUNC = 'ez_strsep'

DEL = [
    ("qz_sp", "\t\t\t*q = '\\0';\n\t\t\t*stringp = q + 1;\n"),
    ("sp_qz", "\t\t\t*stringp = q + 1;\n\t\t\t*q = '\\0';\n"),
    ("t_qz_sp", "\t\t\tchar *t = q + 1;\n\n\t\t\t*q = '\\0';\n\t\t\t*stringp = t;\n"),
    ("p_qz_sp", "\t\t\tp = q + 1;\n\t\t\t*q = '\\0';\n\t\t\t*stringp = p;\n"),
    ("qz_p_sp", "\t\t\t*q = '\\0';\n\t\t\tp = q + 1;\n\t\t\t*stringp = p;\n"),
    ("qinc", "\t\t\t*q++ = '\\0';\n\t\t\t*stringp = q;\n"),
    ("idx", "\t\t\tq[0] = '\\0';\n\t\t\t*stringp = &q[1];\n"),
    ("t_sp_qz", "\t\t\tchar *t = q + 1;\n\n\t\t\t*stringp = t;\n\t\t\t*q = '\\0';\n"),
    ("s1_qz_sp", "\t\t\ts = q + 1;\n\t\t\t*q = '\\0';\n\t\t\t*stringp = s;\n"),
    ("c_qz_sp", "\t\t\t*q = c - c;\n\t\t\t*stringp = q + 1;\n"),
]
RET = [('rs', '\t\t\treturn s;\n')]

AXES = {
    'del': [(d[0], '%d' % i) for i, d in enumerate(DEL)],
    'carry': ['c0', 'c3'],
    'esc': ['e0', 'e1'],
    'nul': ['n0', 'n1', 'n2'],
}

HEAD = ('char *ez_strsep(char **stringp, char delim, char esc)\n{\n'
        '\tchar *s = *stringp;\n\tchar *p, *q;\n\tchar c;\n\n'
        '\tif (s == NULL)\n\t\treturn s;\n\n'
        "\tif (*s == '\\0')\n\t\treturn NULL;\n\n\tp = s;\n")
NUL = {
    'n0': "\t\tif (c == '\\0') {\n\t\t\t*stringp = NULL;\n\t\t\treturn s;\n\t\t}\n",
    'n1': "\t\tif (!c) {\n\t\t\t*stringp = NULL;\n\t\t\treturn s;\n\t\t}\n",
    'n2': "\t\tif (c == '\\0') {\n\t\t\t*stringp = 0;\n\t\t\treturn s;\n\t\t}\n",
}


def render(c):
    esc = 'q[1]' if c['esc'] == 'e0' else '*(q + 1)'
    mm = 'memmove(q, q + 1, strlen(q));'
    body = ('\t\tif (c == esc) {\n'
            '\t\t\tif (%s == esc) {\n\t\t\t\t%s\n\t\t\t\tp = q + 1;\n'
            '\t\t\t\tcontinue;\n\t\t\t}\n' % (esc, mm) +
            '\t\t\tif (%s == delim) {\n\t\t\t\t%s\n\t\t\t\tp = q + 1;\n'
            '\t\t\t\tcontinue;\n\t\t\t}\n' % (esc, mm) +
            '\t\t}\n')
    dele = ("\t\tif (c == delim) {\n" + DEL[int(c['del'])][1] +
            "\t\t\treturn s;\n\t\t}\n")
    if c['carry'] == 'c0':
        loop = ('\tfor (;;) {\n\t\tq = p;\n\t\tc = *q;\n' + NUL[c['nul']] +
                body + dele + '\t\tp = q + 1;\n\t}\n')
    else:
        loop = ('\tfor (;;) {\n\t\tq = p;\n\t\tc = *q;\n' + NUL[c['nul']] +
                body.replace('\t\t\t\tp = q + 1;\n', '') + dele +
                '\t\tp = q + 1;\n\t}\n')
    return HEAD + loop + '}\n'
