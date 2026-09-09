# ez_strsep - stage 12: give `q + 1` a second use so TER leaves it alone.
#
# `ssa_is_replaceable_p` refuses to move an expression whose result has more
# than one immediate use, and `find_replaceable_in_bb` only ever moves within
# one block.  Advancing the walk pointer *before* the delimiter test gives
# `p = q + 1` two uses - the loop's back edge and the `*stringp` store - so the
# add is emitted where the source puts it and `auto_inc_dec`'s reverse scan,
# which only looks for an inc *after* the memory reference, finds nothing.
UNIT = 'ez_wifi_config'
FUNC = 'ez_strsep'

AXES = {
    'adv': ['before_delim', 'before_esc', 'at_top'],
    'order': ['nul_first', 'sp_first'],
    'esc': ['e0', 'e1'],
    'escadv': ['own', 'shared'],
}


def render(c):
    esc = 'q[1]' if c['esc'] == 'e0' else '*(q + 1)'
    mm = 'memmove(q, q + 1, strlen(q));'
    adv = '\t\tp = q + 1;\n'
    escadv = '\t\t\t\tp = q + 1;\n' if c['escadv'] == 'own' else ''
    body = ('\t\tif (c == esc) {\n'
            '\t\t\tif (%s == esc) {\n\t\t\t\t%s\n%s'
            '\t\t\t\tcontinue;\n\t\t\t}\n' % (esc, mm, escadv) +
            '\t\t\tif (%s == delim) {\n\t\t\t\t%s\n%s'
            '\t\t\t\tcontinue;\n\t\t\t}\n' % (esc, mm, escadv) +
            '\t\t}\n')
    if c['order'] == 'nul_first':
        dele = ("\t\tif (c == delim) {\n\t\t\t*q = '\\0';\n"
                "\t\t\t*stringp = p;\n\t\t\treturn s;\n\t\t}\n")
    else:
        dele = ("\t\tif (c == delim) {\n\t\t\t*stringp = p;\n"
                "\t\t\t*q = '\\0';\n\t\t\treturn s;\n\t\t}\n")
    nul = "\t\tif (c == '\\0') {\n\t\t\t*stringp = NULL;\n\t\t\treturn s;\n\t\t}\n"
    if c['adv'] == 'at_top':
        loop = '\tfor (;;) {\n\t\tq = p;\n\t\tc = *q;\n' + adv + nul + body + dele + '\t}\n'
    elif c['adv'] == 'before_esc':
        loop = '\tfor (;;) {\n\t\tq = p;\n\t\tc = *q;\n' + nul + adv + body + dele + '\t}\n'
    else:
        loop = '\tfor (;;) {\n\t\tq = p;\n\t\tc = *q;\n' + nul + body + adv + dele + '\t}\n'
    return ('char *ez_strsep(char **stringp, char delim, char esc)\n{\n'
            '\tchar *s = *stringp;\n\tchar *p, *q;\n\tchar c;\n'
            '\n\tif (s == NULL)\n\t\treturn s;\n\n'
            "\tif (*s == '\\0')\n\t\treturn NULL;\n\n\tp = s;\n" + loop + '}\n')
