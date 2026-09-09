# Variant spec for ez_wifi_config.c:process_config_vars - stage 11, the one
# that landed, and the search that is still open.
#
# The residual was always the same: the shipped build keeps `n` in a
# callee-saved register across `strlen`/`memcmp` - twelve call-crossing
# allocnos, three spills, `pick` on the stack - and ours rematerialised
# `n = 0` because VRP proved it from the loop guard.
#
# GCC 6's `register_edge_assert_for` recurses into an `IOR`'s operands only
# when the comparison is `== 0` (or `!= 1` on a one-bit type):
#
#     if (((comp_code == EQ_EXPR && integer_zerop (val))
#          || (comp_code == NE_EXPR && integer_onep (val))))
#       { ... if (rhs_code == BIT_IOR_EXPR && (precision == 1
#                                              || comp_code == EQ_EXPR)) ... }
#
# so a guard of `(pos | n) == 1` - equivalent here, both flags only ever hold
# 0 or 1 - leaves `n` un-asserted and produces the shipped allocation exactly.
# It costs one instruction: GCC then emits `orr` plus `cmp #1` where the
# shipped code has a single `orrs`.  Finding a spelling that gets both is the
# open question, and the `guard` axis is where to look.
import os

UNIT = 'ez_wifi_config'
FUNC = 'process_config_vars'


def _ax(name, default):
    v = os.environ.get('PCV11_' + name)
    return v.split(',') if v else default


AXES = {
    # spellings that block the assertion, and the ones that do not, for control
    'guard': _ax('GUARD', ['(pos | n) == 1', '(n | pos) == 1', '1 == (pos | n)',
                           '(pos | n) > 0', '(pos | n) >= 1', '(pos | n) & 1',
                           'n || pos', '(pos | n) != 0']),
    'tpos': _ax('TPOS', ['unsigned int', 'int']),
    'tn': _ax('TN', ['u32', 'int', 's32', 'long']),
    'hash': _ax('HASH', ['n = pos;', 'n |= pos;']),
}

TEMPLATE = """int process_config_vars(char *buf, u32 len, char *pick, const char *var)
{
\tu32 i;
\t%(tpos)s pos = 0;
\t%(tn)s n = 0;
\tint m = 0;
\tint j = 0;
\tint end = 0;

\tfor (i = 0; i < len; i++) {
\t\tif (buf[i] == '\\r')
\t\t\tcontinue;

\t\tif (%(guard)s) {
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

\t\tif (buf[i] == '#') {
\t\t\t%(hash)s
\t\t\tpos = 1;
\t\t\tcontinue;
\t\t}
\t\telse if (buf[i] == '\\\\') {
\t\t\tn = 1;
\t\t\tpos = 0;
\t\t\tcontinue;
\t\t}
\t\telse if (buf[i] == '\\n') {
\t\t\tend = pos | n;
\t\t\tn |= pos;
\t\t\tpos = 0;
\t\t\tcontinue;
\t\t}
\t\telse {
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
\t\t\t\t\tpos = 0;
\t\t\t\t\tcontinue;
\t\t\t\t}
\t\t\t\tend++;
\t\t\t\tif (!m) {
\t\t\t\t\tpos = 0;
\t\t\t\t\tcontinue;
\t\t\t\t}
\t\t\t}
\t\t\tif (buf[i] != '\\t') {
\t\t\t\tif (j) {
\t\t\t\t\tint last = pick[j - 1];

\t\t\t\t\tm = (last == ' ' && buf[i] == ' ');
\t\t\t\t\tif (m) {
\t\t\t\t\t\tpos = 0;
\t\t\t\t\t\tcontinue;
\t\t\t\t\t}
\t\t\t\t}
\t\t\t\tpick[j++] = buf[i];
\t\t\t}
\t\t\tm = 1;
\t\t\tpos = 0;
\t\t\tcontinue;
\t\t}
\t}

\treturn j;
}
"""


def render(c):
    return TEMPLATE % c
