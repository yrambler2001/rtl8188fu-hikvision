# process_config_vars - stage 17: the guard spelling, exhaustively.
#
# Two things have to be true at once and no spelling found so far does both:
#
#  * the RTL must be a single `orrs`/`beq`, i.e. a comparison against zero,
#    because that is what lets `cse1` turn every later `mov rX, #0` on the main
#    path into `mov rX, r9` and what keeps the guard temp live across the two
#    calls as the twelfth call-crossing allocno;
#  * VRP's `register_edge_assert_for` must not recurse into the IOR and assert
#    `n == 0`, because that kills `n`'s loop-carried live range and frees the
#    register that `pick` then keeps instead of being spilled.
#
# The recursion fires when the *compared* name's SSA_NAME_DEF_STMT is the
# BIT_IOR and the comparison is `== 0`; the nested recursion inside
# `register_edge_assert_for_1` additionally requires `has_single_use` of the
# operand, which `pos` and `n` do not have.  So anything that puts one more
# level between the compare and the IOR should work - if it survives folding.
import os

UNIT = 'ez_wifi_config'
FUNC = 'process_config_vars'


def _ax(name, default):
    v = os.environ.get('PCV20_' + name)
    return v.split('|') if v else default


GUARDS = [
    '(pos | n) | (pos & n)',
    '(n | pos) | (n & pos)',
    '(n | pos) | (pos & n)',
    '(pos | n) | (n & pos)',
    '(n & pos) | (n | pos)',
    '(pos & n) | (pos | n)',
    '(n ^ pos) | (n & pos)',
    '(pos ^ n) | (pos & n)',
    '(n & pos) | (n ^ pos)',
    '(pos & n) | (pos ^ n)',
    '(n | pos) | (n ^ pos)',
    '(pos | n) | (pos ^ n)',
]

AXES = {
    'g': _ax('G', [('g%02d' % i, s) for i, s in enumerate(GUARDS)]),
    'tpos': _ax('TPOS', ['unsigned int', 'u32', 'int', 's32']),
    'tn': _ax('TN', ['u32', 'unsigned int', 'int', 's32']),
    'hash': _ax('HASH', ['n = 0;', 'n = pos;']),
    'nl': _ax('NL', ['end = pos | n;\n\t\t\tn |= pos;', 'end = 0;\n\t\t\tn = 0;']),
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

\t\tif (%(g)s) {
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
\t\t\t%(nl)s
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
