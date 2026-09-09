# Variant spec for ez_wifi_config.c:process_config_vars - the type cross product.
#
# The shipped code keeps `pos` in one caller-saved register (r2) and writes
# `pos = 0` at the loop bottom as a literal `mov r2, #0`.  Ours has no literal
# there at all: uncprop rewrote that PHI argument into the `pos|n` value that
# the loop guard's `orrs` already computed, which puts `pos` in the same
# out-of-SSA partition as that value, which is what forces IRA to split `pos`
# across r5 and r1 and costs the two extra copies.
#
# uncprop only substitutes an SSA name whose type matches the PHI argument's
# (catalogue section 13 - that is what a `u32` did to ez_set_new_sc).  The
# shipped build substitutes the or-value for `n`, `end` and `m` but not for
# `pos`, so `pos` plausibly has a different type from the rest.  This sweeps
# the type of each of the six locals independently.
UNIT = 'ez_wifi_config'
FUNC = 'process_config_vars'

TYPES = ['int', 'unsigned int', 'u32', 's32', 'u8', 's8', 'char', 'u16', 's16',
         'short', 'long', 'unsigned long', 'size_t', '_Bool', 'unsigned char']

# A typedef of `int` is *not* `int` as far as uncprop is concerned: pushdecl
# gives every named typedef its own variant type node, and the pass compares
# TREE_TYPE pointers.  `s32` and `int` therefore behave differently even
# though `types_compatible_p` says they are the same - which is why the word
# types below are spelt several ways on purpose.
WORD = ['int', 's32', 'u32', 'unsigned int', 'long', 'unsigned long', 'size_t']

import os
def _ax(name, default):
    v = os.environ.get('PCV_' + name)
    return v.split(',') if v else default

AXES = {
    'ti': _ax('TI', ['u32']),
    'tpos': _ax('TPOS', WORD),
    'tn': _ax('TN', WORD),
    'tm': _ax('TM', WORD),
    'tj': _ax('TJ', WORD),
    'tend': _ax('TEND', WORD),
}

TEMPLATE = """int process_config_vars(char *buf, u32 len, char *pick, const char *var)
{
\t%(ti)s i;
\t%(tpos)s pos = 0;
\t%(tn)s n = 0;
\t%(tm)s m = 0;
\t%(tj)s j = 0;
\t%(tend)s end = 0;

\tfor (i = 0; i < len; i++) {
\t\tif (buf[i] == '\\r')
\t\t\tcontinue;

\t\tif (n || pos) {
\t\t\tif (buf[i] == '\\n') {
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
\t\t\tn |= pos;
\t\t\tpos = 1;
\t\t\tcontinue;
\t\tcase '\\\\':
\t\t\tn = 1;
\t\t\tbreak;
\t\tcase '\\n':
\t\t\tend = pos | n;
\t\t\tn |= pos;
\t\t\tbreak;
\t\tdefault: {
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
\t\t}
\t\tpos = 0;
\t}

\treturn j;
}
"""


def render(c):
    return TEMPLATE % c
