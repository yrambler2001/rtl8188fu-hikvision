# ez_strsep - stage 10: broad sweep for the delimiter block's `*stringp` store.
#
# Everything else in the function is byte-identical; four words remain and they
# are all in the `c == delim` block.  The shipped build there is
#
#	mov r2, #0 ; add r3, r4, #1 ; strb r2, [r4] ; b <the shared store>
#
# - the address computation *before* the byte store, in a register of its own,
# so `q` is still live at the store, so `auto_inc_dec` cannot fold the pair,
# so the block ends in `str r3, [r7]` and cross-jumping merges it with the
# end-of-string path's identical store.  Ours emits the add after the store,
# it folds to `strb r3, [r4], #1`, and the value left in `q`'s own register
# makes the two stores different instructions.
#
# Axes: how the delimiter block is spelled, how the walk carries its pointer,
# how the escape test reads the next character, the NUL constant, the types of
# the two pointers and the character, and the loop form.
UNIT = 'ez_wifi_config'
FUNC = 'ez_strsep'

DEL = [
    ("qz_sp", "\t\t\t*q = '\\0';\n\t\t\t*stringp = q + 1;\n"),
    ("qz_sp1", "\t\t\t*q = '\\0';\n\t\t\t*stringp = 1 + q;\n"),
    ("qz_spi", "\t\t\t*q = '\\0';\n\t\t\t*stringp = &q[1];\n"),
    ("sp_qz", "\t\t\t*stringp = q + 1;\n\t\t\t*q = '\\0';\n"),
    ("t_qz_sp", "\t\t\tchar *t = q + 1;\n\n\t\t\t*q = '\\0';\n\t\t\t*stringp = t;\n"),
    ("p_qz_sp", "\t\t\tp = q + 1;\n\t\t\t*q = '\\0';\n\t\t\t*stringp = p;\n"),
    ("qz_p_sp", "\t\t\t*q = '\\0';\n\t\t\tp = q + 1;\n\t\t\t*stringp = p;\n"),
    ("qinc", "\t\t\t*q++ = '\\0';\n\t\t\t*stringp = q;\n"),
    ("preinc", "\t\t\t*q = '\\0';\n\t\t\t*stringp = ++q;\n"),
    ("qz_qadd_sp", "\t\t\t*q = '\\0';\n\t\t\tq += 1;\n\t\t\t*stringp = q;\n"),
    ("qz_spq_inc", "\t\t\t*q = '\\0';\n\t\t\t*stringp = q;\n\t\t\t(*stringp)++;\n"),
    ("idx0", "\t\t\tq[0] = '\\0';\n\t\t\t*stringp = q + 1;\n"),
    ("cast", "\t\t\t*q = '\\0';\n\t\t\t*stringp = (char *)(q + 1);\n"),
    ("sz", "\t\t\t*q = '\\0';\n\t\t\t*stringp = q + sizeof(char);\n"),
    ("t2", "\t\t\tchar *t = q + 1;\n\n\t\t\t*q = '\\0';\n\t\t\t*stringp = t;\n\t\t\tp = t;\n"),
]

AXES = {
    'del': [(d[0], '%d' % i) for i, d in enumerate(DEL)],
    'carry': ['c0', 'c3'],
    'esc': ['e0', 'e1'],
    'nul': ['n0', 'n1'],
    'tp': ['char', 'u8'],
    'loop': ['for', 'while'],
}

NUL = {
    'n0': "\t\tif (c == '\\0') {\n\t\t\t*stringp = NULL;\n\t\t\treturn s;\n\t\t}\n",
    'n1': "\t\tif (!c) {\n\t\t\t*stringp = NULL;\n\t\t\treturn s;\n\t\t}\n",
}


def render(c):
    if c['tp'] == 'char':
        decl = '\tchar *s = *stringp;\n\tchar *p, *q;\n\tchar c;\n'
    else:
        decl = '\tchar *s = *stringp;\n\tchar *p, *q;\n\tu8 c;\n'
    esc = 'q[1]' if c['esc'] == 'e0' else '*(q + 1)'
    mm = 'memmove(q, q + 1, strlen(q));'
    body = ('\t\tif (c == esc) {\n'
            '\t\t\tif (%s == esc) {\n\t\t\t\t%s\n\t\t\t\tp = q + 1;\n'
            '\t\t\t\tcontinue;\n\t\t\t}\n' % (esc, mm) +
            '\t\t\tif (%s == delim) {\n\t\t\t\t%s\n\t\t\t\tp = q + 1;\n'
            '\t\t\t\tcontinue;\n\t\t\t}\n' % (esc, mm) +
            '\t\t}\n')
    if c['carry'] == 'c3':
        body = body.replace('\t\t\t\tp = q + 1;\n', '')
    dele = "\t\tif (c == delim) {\n" + DEL[int(c['del'])][1] + "\t\t\treturn s;\n\t\t}\n"
    head = 'for (;;)' if c['loop'] == 'for' else 'while (1)'
    loop = ('\t%s {\n\t\tq = p;\n\t\tc = *q;\n' % head + NUL[c['nul']] +
            body + dele + '\t\tp = q + 1;\n\t}\n')
    return ('char *ez_strsep(char **stringp, char delim, char esc)\n{\n'
            + decl + '\n\tif (s == NULL)\n\t\treturn s;\n\n'
            "\tif (*s == '\\0')\n\t\treturn NULL;\n\n\tp = s;\n" + loop + '}\n')
