# Variant spec for ez_wifi_config.c:ez_strsep - stage 3, the two pointers.
#
# With the escape test split in two (stage 1) the function is three
# instructions from the shipped code and one instruction too long.  The whole
# residual is a copy on the loop back edge.
#
# The GIMPLE explains it.  `q = p` is copy-propagated away, so `q` *is* the
# loop PHI `p_1`, and the walk becomes
#
#	p_10 = p_1 + 1;
#	c_11 = MEM[p_10 + -1];
#
# The ARM post-increment then forces `p_1` and `p_10` into one register, so
# whichever of the two the PHI is coalesced with keeps its register free and
# the other needs a copy.  The shipped build coalesces the PHI with `p_10`
# (`mov r4, r5 / ldrb r3, [r5], #1`, nothing on the back edge); ours coalesces
# it with the copy and pays `mov r5, r4` to close the loop.  Ours also reuses
# `p_10` for `q + 1` where the shipped build recomputes `add r3, r4, #1`,
# which says the two are *not* the same SSA name there.
#
# So this sweeps which of the two pointers each use is written in terms of -
# that is what decides which one the PHI ends up being.
UNIT = 'ez_wifi_config'
FUNC = 'ez_strsep'

AXES = {
    'mmsrc': ['p', 'q + 1', '&q[1]', 'q'],
    'slen': ['q', 'p - 1', '&q[0]'],
    'store': ['q + 1', 'p', '&q[1]'],
    'nul': ['*q', 'q[0]', '*(q + 0)'],
    'test': ['*p', 'q[1]', '*(q + 1)'],
    'esc': ['x0', 'x1'],
}


def render(c):
    mm, sl, st, nul, test = (c['mmsrc'], c['slen'], c['store'], c['nul'],
                             c['test'])
    if mm == 'q':
        return None          # not the same value - would change behaviour
    mv = ('\t\t\t\tmemmove(q, %s, strlen(%s));\n\t\t\t\tcontinue;\n' % (mm, sl))
    if c['esc'] == 'x0':
        esc = ("\t\tif (c == esc) {\n"
               "\t\t\tif (%s == esc || %s == delim) {\n" % (test, test)
               + mv + "\t\t\t}\n\t\t}\n")
    else:
        esc = ("\t\tif (c == esc) {\n"
               "\t\t\tif (%s == esc) {\n" % test + mv + "\t\t\t}\n"
               "\t\t\tif (%s == delim) {\n" % test + mv + "\t\t\t}\n"
               "\t\t}\n")
    return ('char *ez_strsep(char **stringp, char delim, char esc)\n'
            '{\n'
            '\tchar *s = *stringp;\n'
            '\tchar *p, *q;\n'
            '\tchar c;\n'
            '\n'
            '\tif (s == NULL)\n\t\treturn s;\n\n'
            "\tif (*s == '\\0')\n\t\treturn NULL;\n\n"
            '\tp = s;\n'
            '\tfor (;;) {\n'
            '\t\tq = p;\n'
            '\t\tc = *p++;\n'
            "\t\tif (c == '\\0') {\n"
            '\t\t\t*stringp = NULL;\n'
            '\t\t\treturn s;\n'
            '\t\t}\n'
            + esc +
            '\t\tif (c == delim) {\n'
            "\t\t\t%s = '\\0';\n" % nul +
            '\t\t\t*stringp = %s;\n' % st +
            '\t\t\treturn s;\n'
            '\t\t}\n'
            '\t}\n'
            '}\n')
