# Variant spec for ez_wifi_config.c:ez_strsep - stage 7, the one that landed.
#
# Stages 1-6 all bottomed out at three instruction-level differences and four
# bytes too long, because `q = p; c = *p++;` makes the loop PHI and its
# back-edge value interfere: `q` is copy-propagated away, so the PHI *is* `q`,
# and `p_10 = p_1 + 1` is defined while `p_1` is still live for the memmove,
# the strlen and the NUL store.
#
# The shape that works carries the *read* position and advances at the end of
# each path:
#
#	q = p;
#	c = *q;
#	...
#	p = q + 1;
#
# Now every use of `q` precedes the increment, the two do not interfere,
# out-of-SSA coalesces them, and the back-edge copy is gone.  156 bytes, four
# differing words - and those four are only that the shipped build routes the
# delimiter path through the shared `*stringp` store while ours fuses the NUL
# store into a post-increment.  The `carry` axis below is what found it; the
# `del` axis is the search for those last four words, which has not landed.
UNIT = 'ez_wifi_config'
FUNC = 'ez_strsep'

AXES = {
    'carry': ['c0', 'c1', 'c2', 'c3'],
    'del': ['d0', 'd1', 'd2', 'd3', 'd4', 'd5'],
    'esc': ['e0', 'e1'],
}

HEAD = ('char *ez_strsep(char **stringp, char delim, char esc)\n{\n'
        '\tchar *s = *stringp;\n\tchar *p, *q;\n\tchar c;\n\n'
        '\tif (s == NULL)\n\t\treturn s;\n\n'
        "\tif (*s == '\\0')\n\t\treturn NULL;\n\n\tp = s;\n")
NUL = ("\t\tif (c == '\\0') {\n\t\t\t*stringp = NULL;\n\t\t\treturn s;\n\t\t}\n")

DEL = {
    'd0': "\t\tif (c == delim) {\n\t\t\t*q = '\\0';\n\t\t\t*stringp = q + 1;\n\t\t\treturn s;\n\t\t}\n",
    'd1': "\t\tif (c == delim) {\n\t\t\t*stringp = q + 1;\n\t\t\t*q = '\\0';\n\t\t\treturn s;\n\t\t}\n",
    'd2': "\t\tif (c == delim) {\n\t\t\tp = q + 1;\n\t\t\t*q = '\\0';\n\t\t\t*stringp = p;\n\t\t\treturn s;\n\t\t}\n",
    'd3': "\t\tif (c == delim) {\n\t\t\t*q = '\\0';\n\t\t\tp = q + 1;\n\t\t\t*stringp = p;\n\t\t\treturn s;\n\t\t}\n",
    'd4': "\t\tif (c == delim) {\n\t\t\t*q++ = '\\0';\n\t\t\t*stringp = q;\n\t\t\treturn s;\n\t\t}\n",
    'd5': "\t\tif (c == delim) {\n\t\t\tq[0] = '\\0';\n\t\t\t*stringp = &q[1];\n\t\t\treturn s;\n\t\t}\n",
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
    if c['carry'] == 'c0':          # the one that lands
        loop = ('\tfor (;;) {\n\t\tq = p;\n\t\tc = *q;\n' + NUL + body +
                DEL[c['del']] + '\t\tp = q + 1;\n\t}\n')
    elif c['carry'] == 'c1':        # advance immediately after the load
        loop = ('\tfor (;;) {\n\t\tq = p;\n\t\tc = *q;\n\t\tp = q + 1;\n' +
                NUL + body.replace('\t\t\t\tp = q + 1;\n', '') +
                DEL[c['del']] + '\t}\n')
    elif c['carry'] == 'c2':        # post-increment (the previous shape)
        loop = ('\tfor (;;) {\n\t\tq = p;\n\t\tc = *p++;\n' + NUL +
                body.replace('\t\t\t\tp = q + 1;\n', '') +
                DEL[c['del']] + '\t}\n')
    else:                           # c3: advance only where the walk continues
        loop = ('\tfor (;;) {\n\t\tq = p;\n\t\tc = *q;\n' + NUL +
                body.replace('\t\t\t\tp = q + 1;\n', '') +
                DEL[c['del']] + '\t\tp = q + 1;\n\t}\n')
    return HEAD + loop + '}\n'
