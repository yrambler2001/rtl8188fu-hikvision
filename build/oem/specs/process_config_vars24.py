# process_config_vars - stage 24: the full type cross product under a guard
# that blocks VRP's assertion.
#
# What the shipped build needs, all at once:
#
#   * a single `orrs`/`beq` guard, so cse1 knows the guard register is zero on
#     the main path;
#   * VRP's `register_edge_assert_for` not to reach `n`, so `n` stays live
#     across strlen/memcmp as the twelfth call-crossing allocno.  Nesting the
#     IOR one level - `(pos | n) | (pos & n)` is the same value - does it,
#     because the recursion into an IOR's operands *is* guarded by
#     `has_single_use` one level down;
#   * `uncprop` to rewrite the zeros of `end`, `m` and `n` into the guard
#     temp but *not* pos's, because pos's must stay plain `mov r2, #0` copies
#     that cross-jumping merges into one shared tail.  uncprop looks its
#     equivalences up by the *tree node* of the constant, which carries the
#     type, and then filters on `gimple_can_coalesce_p`, so this is decided
#     entirely by which typedef each local is declared with.
import itertools, os

UNIT = 'ez_wifi_config'
FUNC = 'process_config_vars'


def _ax(name, default):
    v = os.environ.get('PCV24_' + name)
    return v.split('|') if v else default


AXES = {
    'g': _ax('G', ['(pos | n) | (pos & n)', '(n | pos) | (n & pos)',
                   '(pos | n) == 1']),
    'tpos': _ax('TPOS', ['unsigned int', 'u32', 'int', 's32', 'long', 'unsigned long']),
    'tn': _ax('TN', ['u32', 'unsigned int', 'int', 's32', 'long', 'unsigned long']),
    'tend': _ax('TEND', ['int', 's32', 'long', 'u32']),
    'tm': _ax('TM', ['int', 's32', 'u32']),
    'tj': _ax('TJ', ['int', 's32']),
    'nl': _ax('NL', ['end = pos | n;\n\t\t\tn |= pos;', 'end = 0;\n\t\t\tn = 0;']),
}

TEMPLATE = """int process_config_vars(char *buf, u32 len, char *pick, const char *var)
{
\tu32 i;
\t%(tpos)s pos = 0;
\t%(tn)s n = 0;
\t%(tm)s m = 0;
\t%(tj)s j = 0;
\t%(tend)s end = 0;

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
\t\t\tn = 0;
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
