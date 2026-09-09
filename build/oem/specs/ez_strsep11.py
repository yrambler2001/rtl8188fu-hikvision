# ez_strsep - stage 11: break out of the loop so the address is not TER'd.
#
# GCC 6's expand runs TER, and `t = q + 1` with a single use in the *next*
# statement is replaced into that use - so the add lands after the NUL store
# no matter which order the source uses, and `auto_inc_dec`'s reverse scan
# then finds it (`reg_next_inc_use[q]`) and folds the pair into
# `strb r3, [r4], #1`.
#
# TER only replaces within one basic block (`find_replaceable_in_bb`).  If the
# delimiter path computes the new pointer, stores the NUL and *breaks*, the
# use of that pointer is in the block after the loop, TER leaves the add where
# the source put it, and with the add written first the reverse scan finds no
# inc after the store.  The end-of-string path keeps its own `*stringp = NULL`
# (section 19: a shared tail is duplicated source), so cross-jumping still
# merges the two `str` + `mov` + `pop` tails and keeps the earlier copy.
UNIT = 'ez_wifi_config'
FUNC = 'ez_strsep'

AXES = {
    'order': ['padd_first', 'nul_first'],
    'exitv': ['p', 't'],
    'exit': ['brk', 'goto'],
    'esc': ['e0', 'e1'],
    'carry': ['c0', 'c3'],
}


def render(c):
    esc = 'q[1]' if c['esc'] == 'e0' else '*(q + 1)'
    mm = 'memmove(q, q + 1, strlen(q));'
    if c['exitv'] == 'p':
        decl = '\tchar *s = *stringp;\n\tchar *p, *q;\n\tchar c;\n'
        var = 'p'
        setv = '\t\t\tp = q + 1;\n'
    else:
        decl = '\tchar *s = *stringp;\n\tchar *p, *q, *t;\n\tchar c;\n'
        var = 't'
        setv = '\t\t\tt = q + 1;\n'
    nulz = "\t\t\t*q = '\\0';\n"
    leave = 'break;' if c['exit'] == 'brk' else 'goto out;'
    if c['order'] == 'padd_first':
        dele = "\t\tif (c == delim) {\n" + setv + nulz + '\t\t\t%s\n\t\t}\n' % leave
    else:
        dele = "\t\tif (c == delim) {\n" + nulz + setv + '\t\t\t%s\n\t\t}\n' % leave
    body = ('\t\tif (c == esc) {\n'
            '\t\t\tif (%s == esc) {\n\t\t\t\t%s\n\t\t\t\tp = q + 1;\n'
            '\t\t\t\tcontinue;\n\t\t\t}\n' % (esc, mm) +
            '\t\t\tif (%s == delim) {\n\t\t\t\t%s\n\t\t\t\tp = q + 1;\n'
            '\t\t\t\tcontinue;\n\t\t\t}\n' % (esc, mm) +
            '\t\t}\n')
    if c['carry'] == 'c3':
        body = body.replace('\t\t\t\tp = q + 1;\n', '')
    nul = "\t\tif (c == '\\0') {\n\t\t\t*stringp = NULL;\n\t\t\treturn s;\n\t\t}\n"
    tail = ('out:\n' if c['exit'] == 'goto' else '') + \
           '\t*stringp = %s;\n\treturn s;\n}\n' % var
    return ('char *ez_strsep(char **stringp, char delim, char esc)\n{\n'
            + decl + '\n\tif (s == NULL)\n\t\treturn s;\n\n'
            "\tif (*s == '\\0')\n\t\treturn NULL;\n\n\tp = s;\n"
            '\tfor (;;) {\n\t\tq = p;\n\t\tc = *q;\n'
            + nul + body + dele + '\t\tp = q + 1;\n\t}\n\n' + tail)
