# ez_strsep - stage 9: the `*stringp` store is one statement, not two.
#
# The shipped delimiter path branches to the *same* `str r3, [r7]` the
# end-of-string path uses, and pays an extra `add r3, r4, #1` for it.  Two
# separate `*stringp = ...` stores cannot produce that: expand's TER inlines
# `q + 1` into its single use, so the add lands *after* the NUL store and
# `auto_inc_dec` folds the pair into `strb r3, [r4], #1`, leaving the value in
# `q`'s own register and the two stores textually different.
#
# Writing the result into a variable and storing it once after the loop makes
# `q + 1` a PHI argument instead - out-of-SSA emits it as a copy in the
# delimiter block, before the branch, so TER never moves it and auto-inc never
# sees an add next to the store.
UNIT = 'ez_wifi_config'
FUNC = 'ez_strsep'

AXES = {
    'decl': ['together', 'separate'],
    'order': ['zero_first', 'ptr_first'],
    'exit': ['brk', 'goto'],
    'esc': ['e0', 'e1'],
    'nulval': ['NULL', '0'],
}


def render(c):
    esc = 'q[1]' if c['esc'] == 'e0' else '*(q + 1)'
    mm = 'memmove(q, q + 1, strlen(q));'
    if c['decl'] == 'together':
        decl = '\tchar *s = *stringp;\n\tchar *p, *q, *r;\n\tchar c;\n'
    else:
        decl = '\tchar *s = *stringp;\n\tchar *p, *q;\n\tchar *r;\n\tchar c;\n'
    leave = 'break;' if c['exit'] == 'brk' else 'goto out;'
    if c['order'] == 'zero_first':
        dele = ("\t\tif (c == delim) {\n\t\t\t*q = '\\0';\n\t\t\tr = q + 1;\n"
                "\t\t\t%s\n\t\t}\n" % leave)
    else:
        dele = ("\t\tif (c == delim) {\n\t\t\tr = q + 1;\n\t\t\t*q = '\\0';\n"
                "\t\t\t%s\n\t\t}\n" % leave)
    nul = ("\t\tif (c == '\\0') {\n\t\t\tr = %s;\n\t\t\t%s\n\t\t}\n"
           % (c['nulval'], leave))
    body = ('\t\tif (c == esc) {\n'
            '\t\t\tif (%s == esc) {\n\t\t\t\t%s\n\t\t\t\tp = q + 1;\n'
            '\t\t\t\tcontinue;\n\t\t\t}\n' % (esc, mm) +
            '\t\t\tif (%s == delim) {\n\t\t\t\t%s\n\t\t\t\tp = q + 1;\n'
            '\t\t\t\tcontinue;\n\t\t\t}\n' % (esc, mm) +
            '\t\t}\n')
    tail = 'out:\n' if c['exit'] == 'goto' else ''
    return ('char *ez_strsep(char **stringp, char delim, char esc)\n{\n'
            + decl +
            '\n\tif (s == NULL)\n\t\treturn s;\n\n'
            "\tif (*s == '\\0')\n\t\treturn NULL;\n\n\tp = s;\n"
            '\tfor (;;) {\n\t\tq = p;\n\t\tc = *q;\n'
            + nul + body + dele + '\t\tp = q + 1;\n\t}\n\n'
            + tail + '\t*stringp = r;\n\treturn s;\n}\n')
