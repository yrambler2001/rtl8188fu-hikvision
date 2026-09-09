# Variant spec for ez_wifi_config.c:process_config_vars.
#
# Ours is 352 bytes to the shipped 344: two extra instructions, a `mov r5,r1`
# / `mov r1,r5` pair on the loop back edge.  IRA's dump says why: the shipped
# build has twelve allocnos restricted to r3-r11 and spills three (len, var,
# pick); ours has eleven and spills two, and to fit it splits `pos` into two
# pseudos (r111 in a callee-saved register, r112 in r1) - hence the copies.
#
# The mechanism is visible in the shipped code.  The loop guard's `orrs r9,
# r2, r6` result (pos|n) survives into the switch: `case '#'` is `moveq r6,
# r9` and `case '\n'` is `moveq r4, r9 / moveq r6, r4`.  That is uncprop
# rewriting the constant 0 in those PHI arguments into an SSA name known to
# hold 0 on the edge.  In our build the same value ends up coalesced into
# `pos`'s partition instead of getting its own, which is what splits `pos`.
#
# So the axes here are the ones that can change which SSA names exist around
# that guard and which of them a PHI argument can borrow: how the guard is
# spelt, whether the or-value has a name of its own, how the two `|=` in the
# switch are written, where `pos = 0` sits, and the usual declaration order
# and types.
UNIT = 'ez_wifi_config'
FUNC = 'process_config_vars'

AXES = {
    'decl': ['d0', 'd1', 'd2', 'd3', 'd4', 'd5'],
    'guard': ['g0', 'g1', 'g2', 'g3', 'g4', 'g5', 'g6'],
    'hash': ['h0', 'h1', 'h2', 'h3'],
    'nl': ['n0', 'n1', 'n2', 'n3'],
    'bottom': ['b0', 'b1', 'b2'],
    'loop': ['l0', 'l1'],
}

DECLS = {
    'd0': "\tu32 i;\n\tint pos = 0;\n\tint n = 0;\n\tint m = 0;\n\tint j = 0;\n\tint end = 0;\n",
    'd1': "\tu32 i;\n\tint n = 0;\n\tint pos = 0;\n\tint m = 0;\n\tint j = 0;\n\tint end = 0;\n",
    'd2': "\tu32 i;\n\tint pos = 0, n = 0, m = 0, j = 0, end = 0;\n",
    'd3': "\tint pos = 0;\n\tint n = 0;\n\tint m = 0;\n\tint j = 0;\n\tint end = 0;\n\tu32 i;\n",
    'd4': "\tu32 i;\n\tint end = 0;\n\tint pos = 0;\n\tint n = 0;\n\tint m = 0;\n\tint j = 0;\n",
    'd5': "\tu32 i;\n\tint pos = 0;\n\tint n = 0;\n\tint m = 0;\n\tint j = 0;\n\tint end = 0;\n\tint t;\n",
}

# The guard.  `t` is only declared by d5; guards that need it are skipped
# otherwise.
GUARDS = {
    'g0': "\t\tif (n || pos) {\n",
    'g1': "\t\tif (pos || n) {\n",
    'g2': "\t\tif (n | pos) {\n",
    'g3': "\t\tif (pos | n) {\n",
    'g4': "\t\tif (n != 0 || pos != 0) {\n",
    'g5': "\t\tt = pos | n;\n\t\tif (t) {\n",
    'g6': "\t\tt = n | pos;\n\t\tif (t) {\n",
}

HASH = {
    'h0': "\t\t\tn |= pos;\n\t\t\tpos = 1;\n\t\t\tcontinue;\n",
    'h1': "\t\t\tn = n | pos;\n\t\t\tpos = 1;\n\t\t\tcontinue;\n",
    'h2': "\t\t\tn = pos | n;\n\t\t\tpos = 1;\n\t\t\tcontinue;\n",
    'h3': "\t\t\tif (pos)\n\t\t\t\tn = 1;\n\t\t\tpos = 1;\n\t\t\tcontinue;\n",
}

NL = {
    'n0': "\t\t\tend = pos | n;\n\t\t\tn |= pos;\n\t\t\tbreak;\n",
    'n1': "\t\t\tend = n | pos;\n\t\t\tn |= pos;\n\t\t\tbreak;\n",
    'n2': "\t\t\tn |= pos;\n\t\t\tend = n;\n\t\t\tbreak;\n",
    'n3': "\t\t\tend = pos | n;\n\t\t\tn = end;\n\t\t\tbreak;\n",
}

BODY_DEFAULT = """\t\tdefault: {
\t\t\tsize_t vlen = strlen(var);
\t\t\tint cmp = memcmp(&buf[i], var, vlen);

\t\t\tif (!end && !cmp) {
\t\t\t\tend = vlen;
\t\t\t\tj = 0;
\t\t\t\ti += end;
\t\t\t} else {
\t\t\t\tint skip;

\t\t\t\tif (end)
\t\t\t\t\tskip = 0;
\t\t\t\telse
\t\t\t\t\tskip = m & 1;
\t\t\t\tif (skip) {
\t\t\t\t\tend = 0;
\t\t\t\t\tm = 0;
\t\t\t\t\tbreak;
\t\t\t\t}
\t\t\t\tend++;
\t\t\t\tif (!m)
\t\t\t\t\tbreak;
\t\t\t}
\t\t\tif (buf[i] != '\\t') {
\t\t\t\tif (j) {
\t\t\t\t\tint last = pick[j - 1];

\t\t\t\t\tm = (last == ' ' && buf[i] == ' ');
\t\t\t\t\tif (m)
\t\t\t\t\t\tbreak;
\t\t\t\t}
\t\t\t\tpick[j++] = buf[i];
\t\t\t}
\t\t\tm = 1;
\t\t\tbreak;
\t\t}
"""

GUARD_BODY = """\t\t\tif (buf[i] == '\\n') {
\t\t\t\tif (n) {
\t\t\t\t\tn = 0;
\t\t\t\t\tpos = 0;
\t\t\t\t} else {
\t\t\t\t\tpos = 0;
\t\t\t\t\tend = 0;
\t\t\t\t}
\t\t\t}
\t\t\tcontinue;
\t\t}
"""


def render(c):
    decl, guard, h, nl, bottom, loop = (c['decl'], c['guard'], c['hash'],
                                        c['nl'], c['bottom'], c['loop'])
    if guard in ('g5', 'g6') and decl != 'd5':
        return None
    if guard not in ('g5', 'g6') and decl == 'd5':
        return None
    s = 'int process_config_vars(char *buf, u32 len, char *pick, const char *var)\n{\n'
    s += DECLS[decl] + '\n'
    if loop == 'l0':
        s += '\tfor (i = 0; i < len; i++) {\n'
    else:
        s += '\ti = 0;\n\twhile (i < len) {\n'
    s += "\t\tif (buf[i] == '\\r')\n\t\t\tcontinue;\n\n" if loop == 'l0' else \
         "\t\tif (buf[i] == '\\r') {\n\t\t\ti++;\n\t\t\tcontinue;\n\t\t}\n\n"
    s += GUARDS[guard] + GUARD_BODY.replace('\t\t\tcontinue;\n',
                                            '\t\t\tcontinue;\n' if loop == 'l0'
                                            else '\t\t\ti++;\n\t\t\tcontinue;\n')
    s += '\n\t\tswitch (buf[i]) {\n'
    s += "\t\tcase '#':\n" + (HASH[h] if loop == 'l0'
                              else HASH[h].replace('\t\t\tcontinue;\n',
                                                   '\t\t\ti++;\n\t\t\tcontinue;\n'))
    s += "\t\tcase '\\\\':\n\t\t\tn = 1;\n\t\t\tbreak;\n"
    s += "\t\tcase '\\n':\n" + NL[nl]
    s += BODY_DEFAULT
    s += '\t\t}\n'
    if bottom == 'b0':
        s += '\t\tpos = 0;\n'
    elif bottom == 'b1':
        s += '\t\tif (pos)\n\t\t\tpos = 0;\n'
    else:
        s += '\t\tpos = 0;\n'
    if loop == 'l1':
        s += '\t\ti++;\n'
    s += '\t}\n\n\treturn j;\n}\n'
    if bottom == 'b2':
        # move `pos = 0` above the switch instead of below it
        s = s.replace('\t\tswitch (buf[i]) {\n', '\t\tpos = 0;\n\t\tswitch (buf[i]) {\n')
        s = s.replace('\t\t}\n\t\tpos = 0;\n', '\t\t}\n')
        # ... but `case '#'` must then set pos itself, which it already does
    return s
