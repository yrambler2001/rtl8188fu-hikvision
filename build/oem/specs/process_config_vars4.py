# Variant spec for ez_wifi_config.c:process_config_vars - stage 4, the explicit
# guard value.
#
# The shipped code keeps the loop guard's `pos|n` in r9 - a callee-saved
# register, live across both calls - and writes it into `n`, `end` and `m`
# where a zero is wanted (`moveq r6, r9`, `moveq r4, r9`, `movne r4, r9`).
# In our build that value has no name of its own: uncprop invents those uses
# and the out-of-SSA coalescer folds the value into `pos`'s partition, which
# splits `pos` across two registers.
#
# This tries the shape where the vendor wrote it out - a real local holding
# `pos | n`, assigned explicitly where the shipped code uses r9 - crossed with
# the type family (a typedef of `int` is a distinct node to uncprop, so `pos`
# can be kept out of the substitution).
import os

UNIT = 'ez_wifi_config'
FUNC = 'process_config_vars'


def _ax(name, default):
    v = os.environ.get('PCV4_' + name)
    return v.split(',') if v else default


AXES = {
    'ty': _ax('TY', ['y0', 'y1', 'y2', 'y3', 'y4', 'y5']),
    'use': _ax('USE', ['u0', 'u1', 'u2', 'u3', 'u4', 'u5', 'u6', 'u7']),
    'guard': _ax('GUARD', ['g0', 'g1', 'g2']),
    'bot': _ax('BOT', ['b0', 'b1', 'b2']),
}

# (pos, n, m, j, end, t)
TYPES = {
    'y0': ('int', 'int', 'int', 'int', 'int', 'int'),
    'y1': ('int', 's32', 's32', 's32', 's32', 's32'),
    'y2': ('int', 's32', 'int', 'int', 'int', 's32'),
    'y3': ('s32', 'int', 'int', 'int', 'int', 'int'),
    'y4': ('int', 'int', 'int', 'int', 'int', 's32'),
    'y5': ('u32', 'int', 'int', 'int', 'int', 'int'),
}

GUARD = {
    'g0': '\t\tt = pos | n;\n\t\tif (t) {\n',
    'g1': '\t\tt = n | pos;\n\t\tif (t) {\n',
    'g2': '\t\tt = pos | n;\n\t\tif (t != 0) {\n',
}

BOT = {
    'b0': '\t\tpos = 0;\n',
    'b1': '\t\tpos = t;\n',
    'b2': '\t\tpos = 0;\n',
}

TEMPLATE = """int process_config_vars(char *buf, u32 len, char *pick, const char *var)
{
\tu32 i;
\t%(tpos)s pos = 0;
\t%(tn)s n = 0;
\t%(tm)s m = 0;
\t%(tj)s j = 0;
\t%(tend)s end = 0;
\t%(tt)s t;

\tfor (i = 0; i < len; i++) {
\t\tif (buf[i] == '\\r')
\t\t\tcontinue;

%(guard)s\t\t\tif (buf[i] == '\\n') {
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

\t\tswitch (buf[i]) {
\t\tcase '#':
\t\t\tn = %(zn)s;
\t\t\tpos = 1;
\t\t\tcontinue;
\t\tcase '\\\\':
\t\t\tn = 1;
\t\t\tbreak;
\t\tcase '\\n':
\t\t\tend = %(ze)s;
\t\t\tn = end;
\t\t\tbreak;
\t\tdefault: {
\t\t\tsize_t vlen = strlen(var);
\t\t\tint cmp = memcmp(&buf[i], var, vlen);

\t\t\tif (!end && !cmp) {
\t\t\t\tend = vlen;
\t\t\t\tj = %(zj)s;
\t\t\t\ti += end;
\t\t\t} else {
\t\t\t\tint skip;

\t\t\t\tif (end)
\t\t\t\t\tskip = 0;
\t\t\t\telse
\t\t\t\t\tskip = m & 1;
\t\t\t\tif (skip) {
\t\t\t\t\tend = %(zs)s;
\t\t\t\t\tm = end;
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
\t\t}
%(bot)s\t}

\treturn j;
}
"""

# which of the four zeroes are written as `t` rather than a literal 0
USES = {
    'u0': ('t', 't', '0', 't'),
    'u1': ('t', 't', 't', 't'),
    'u2': ('t', 't', '0', '0'),
    'u3': ('0', 't', '0', 't'),
    'u4': ('t', '0', '0', 't'),
    'u5': ('t', 't', '0', 'end'),
    'u6': ('0', '0', '0', 't'),
    'u7': ('0', '0', '0', '0'),
}


def render(c):
    tpos, tn, tm, tj, tend, tt = TYPES[c['ty']]
    zn, ze, zj, zs = USES[c['use']]
    if c['bot'] == 'b2' and zs == '0':
        return None
    return TEMPLATE % {
        'tpos': tpos, 'tn': tn, 'tm': tm, 'tj': tj, 'tend': tend, 'tt': tt,
        'guard': GUARD[c['guard']], 'bot': BOT[c['bot']],
        'zn': zn, 'ze': ze, 'zj': zj, 'zs': zs,
    }
