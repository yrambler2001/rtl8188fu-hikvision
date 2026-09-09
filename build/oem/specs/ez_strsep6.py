# Variant spec for ez_wifi_config.c:ez_strsep - stage 6, the step duplicated.
#
# The residual is one copy on the loop back edge: the loop PHI is coalesced
# with `q` rather than with `p + 1`, because `q = p` is copy-propagated away
# and `p_1` is still live where `p_10 = p_1 + 1` is defined.
#
# Duplicating a block in the source and letting cross-jumping merge it is what
# closed `ez_scan_device_ioctl_handle`.  Here the block to try duplicating is
# the walk step itself - `q = p; c = *p++;` - written once per path into the
# loop instead of once at its head, which changes which value the back edge
# carries.
UNIT = 'ez_wifi_config'
FUNC = 'ez_strsep'

AXES = {
    'shape': ['v0', 'v1', 'v2', 'v3', 'v4', 'v5'],
    'esc': ['x0', 'x1'],
}

STEP = 'q = p;\n%sc = *p++;\n'


def render(c):
    v, k = c['shape'], c['esc']

    def mv(ind, step=''):
        one = ('%smemmove(q, p, strlen(q));\n' % ind) + step
        return one

    def esc(ind, step, cont):
        m = mv(ind + '\t') + (step or '') + ind + '\t' + cont + '\n'
        if k == 'x0':
            return (ind + 'if (c == esc) {\n' +
                    ind + '\tif (*p == esc || *p == delim) {\n' +
                    mv(ind + '\t\t') + (step or '') + ind + '\t\t' + cont + '\n' +
                    ind + '\t}\n' + ind + '}\n')
        return (ind + 'if (c == esc) {\n' +
                ind + '\tif (*p == esc) {\n' +
                mv(ind + '\t\t') + (step or '') + ind + '\t\t' + cont + '\n' +
                ind + '\t}\n' +
                ind + '\tif (*p == delim) {\n' +
                mv(ind + '\t\t') + (step or '') + ind + '\t\t' + cont + '\n' +
                ind + '\t}\n' + ind + '}\n')

    head = ('char *ez_strsep(char **stringp, char delim, char esc)\n{\n'
            '\tchar *s = *stringp;\n\tchar *p, *q;\n\tchar c;\n\n'
            '\tif (s == NULL)\n\t\treturn s;\n\n'
            "\tif (*s == '\\0')\n\t\treturn NULL;\n\n\tp = s;\n")
    NUL = ("\t\tif (c == '\\0') {\n\t\t\t*stringp = NULL;\n\t\t\treturn s;\n\t\t}\n")
    DEL = ("\t\tif (c == delim) {\n\t\t\t*q = '\\0';\n"
           '\t\t\t*stringp = q + 1;\n\t\t\treturn s;\n\t\t}\n')

    if v == 'v0':                       # baseline: step at the head
        body = ('\tfor (;;) {\n\t\tq = p;\n\t\tc = *p++;\n' + NUL +
                esc('\t\t', None, 'continue;') + DEL + '\t}\n')
    elif v == 'v1':                     # step duplicated per path
        step = '\t\t\t\tq = p;\n\t\t\t\tc = *p++;\n'
        body = ('\tq = p;\n\tc = *p++;\n\tfor (;;) {\n' + NUL +
                esc('\t\t', step, 'continue;') + DEL +
                '\t\tq = p;\n\t\tc = *p++;\n\t}\n')
    elif v == 'v2':                     # step at the bottom, do/while
        body = ('\tq = p;\n\tc = *p++;\n\tdo {\n' + NUL +
                esc('\t\t', None, 'goto step;') + DEL +
                'step:\n\t\tq = p;\n\t\tc = *p++;\n\t} while (1);\n')
    elif v == 'v3':                     # while with the step in the condition
        body = ('\tq = p;\n'
                "\twhile ((c = *p++) != '\\0') {\n" +
                esc('\t\t', None, 'continue;') + DEL +
                '\t\tq = p;\n\t}\n'
                '\t*stringp = NULL;\n\treturn s;\n')
    elif v == 'v4':                     # q updated after the delimiter test
        body = ('\tfor (;;) {\n\t\tq = p;\n\t\tc = *p;\n\t\tp = q + 1;\n' + NUL +
                esc('\t\t', None, 'continue;') + DEL + '\t}\n')
    else:                               # v5: step duplicated, esc path re-reads
        step = '\t\t\t\tq = p;\n\t\t\t\tc = *q;\n\t\t\t\tp = q + 1;\n'
        body = ('\tq = p;\n\tc = *q;\n\tp = q + 1;\n\tfor (;;) {\n' + NUL +
                esc('\t\t', step, 'continue;') + DEL +
                '\t\tq = p;\n\t\tc = *q;\n\t\tp = q + 1;\n\t}\n')
    return head + body + '}\n'
