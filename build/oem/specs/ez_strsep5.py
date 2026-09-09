# Variant spec for ez_wifi_config.c:ez_strsep - stage 5, the shared exit.
#
# The shipped code stores through `stringp` exactly once - `str r3, [r7]` - and
# both exits reach it: the end-of-string path with r3 = 0 and the delimiter
# path with `add r3, r4, #1` first.  Ours has two stores, because the two paths
# hold the value in different registers and cross-jumping cannot merge them.
#
# `ez_scan_device_ioctl_handle` closed on the observation that a shared tail in
# the shipped code is duplicated source that cross-jumping merged.  This is the
# other direction of the same question: a tail the shipped build shares and
# ours does not, so here the source is tried with the store written once and
# both paths reaching it - the shape the shipped code actually has.
UNIT = 'ez_wifi_config'
FUNC = 'ez_strsep'

AXES = {
    'exit': ['e0', 'e1', 'e2', 'e3'],
    'esc': ['x0', 'x1'],
    'res': ['char *', 'void *'],
    'ctype': ['char', 'int'],
}


def esc_block(kind):
    mv = '\t\t\t\tmemmove(q, p, strlen(q));\n\t\t\t\tcontinue;\n'
    if kind == 'x0':
        return ("\t\tif (c == esc) {\n"
                "\t\t\tif (*p == esc || *p == delim) {\n" + mv + "\t\t\t}\n\t\t}\n")
    return ("\t\tif (c == esc) {\n"
            "\t\t\tif (*p == esc) {\n" + mv + "\t\t\t}\n"
            "\t\t\tif (*p == delim) {\n" + mv + "\t\t\t}\n"
            "\t\t}\n")


def render(c):
    e, res = c['exit'], c['res']
    esc = esc_block(c['esc'])
    decl = '\tchar *s = *stringp;\n\tchar *p, *q;\n\t%s c;\n' % c['ctype']
    if e != 'e0':
        decl += '\t%snext;\n' % res
    head = ('char *ez_strsep(char **stringp, char delim, char esc)\n{\n' + decl +
            '\n\tif (s == NULL)\n\t\treturn s;\n\n'
            "\tif (*s == '\\0')\n\t\treturn NULL;\n\n\tp = s;\n")

    if e == 'e0':                       # baseline: two stores
        body = ('\tfor (;;) {\n'
                '\t\tq = p;\n\t\tc = *p++;\n'
                "\t\tif (c == '\\0') {\n\t\t\t*stringp = NULL;\n\t\t\treturn s;\n\t\t}\n"
                + esc +
                "\t\tif (c == delim) {\n\t\t\t*q = '\\0';\n"
                '\t\t\t*stringp = q + 1;\n\t\t\treturn s;\n\t\t}\n\t}\n')
    elif e == 'e1':                     # one store, reached by goto
        body = ('\tfor (;;) {\n'
                '\t\tq = p;\n\t\tc = *p++;\n'
                "\t\tif (c == '\\0') {\n\t\t\tnext = NULL;\n\t\t\tgoto out;\n\t\t}\n"
                + esc +
                "\t\tif (c == delim) {\n\t\t\t*q = '\\0';\n"
                '\t\t\tnext = q + 1;\n\t\t\tgoto out;\n\t\t}\n\t}\n'
                'out:\n\t*stringp = next;\n\treturn s;\n')
    elif e == 'e2':                     # one store, break out of the loop
        body = ('\tfor (;;) {\n'
                '\t\tq = p;\n\t\tc = *p++;\n'
                "\t\tif (c == '\\0') {\n\t\t\tnext = NULL;\n\t\t\tbreak;\n\t\t}\n"
                + esc +
                "\t\tif (c == delim) {\n\t\t\t*q = '\\0';\n"
                '\t\t\tnext = q + 1;\n\t\t\tbreak;\n\t\t}\n\t}\n'
                '\t*stringp = next;\n\treturn s;\n')
    else:                               # e3: the NUL case sets next from q
        body = ('\tfor (;;) {\n'
                '\t\tq = p;\n\t\tc = *p++;\n'
                "\t\tif (c == '\\0') {\n\t\t\tnext = NULL;\n\t\t\tgoto out;\n\t\t}\n"
                + esc +
                "\t\tif (c != delim)\n\t\t\tcontinue;\n"
                "\t\t*q = '\\0';\n"
                '\t\tnext = q + 1;\n'
                'out:\n\t\t*stringp = next;\n\t\treturn s;\n\t}\n')
    return head + body + '}\n'
