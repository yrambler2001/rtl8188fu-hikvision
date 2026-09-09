# process_config_vars - stage 14: the type of the guard value decides four
# separate differences at once.
#
# uncprop rewrites a PHI argument that is the constant 0 into an SSA name
# known to be 0 on that edge, but only when `gimple_can_coalesce_p` says the
# two could share a register - which for integers means the same
# TYPE_CANONICAL, i.e. the same signedness.  The shipped build rewrites the
# zeros belonging to `end`, `m` and `n` (`movne r4, r9`, `moveq r6, r4`) but
# NOT the ones belonging to `pos`, which stay a plain `mov r2, #0` in a shared
# tail.  So the guard value is signed, like `end`/`m`/`n`, and `pos` is not.
#
# `pos | n` cannot be signed if `pos` is unsigned - the usual arithmetic
# conversions make the IOR unsigned - so the vendor's guard must have a
# conversion in it, and a conversion is also exactly what stops
# `register_edge_assert_for` recursing into the IOR and proving `n == 0`.
import os

UNIT = 'ez_wifi_config'
FUNC = 'process_config_vars'


def _ax(name, default):
    v = os.environ.get('PCV15_' + name)
    return v.split('|') if v else default


AXES = {
    'guard': _ax('GUARD', [
        ('eq1', '(pos | n) == 1'),
        ('plain', 'pos | n'),
        ('ceq1', '(int)(pos | n) == 1'),
        ('gt0', '(pos | n) > 0'),
    ]),
    'tpos': _ax('TPOS', ['int', 's32', 'unsigned int', 'u32']),
    'tn': _ax('TN', ['u32', 'unsigned int', 'int', 's32']),
    'tend': _ax('TEND', ['u32', 'unsigned int', 'int', 's32']),
    'tm': _ax('TM', ['u32', 'unsigned int', 'int', 's32']),
    'tj': _ax('TJ', ['int', 'u32']),
    'hash': _ax('HASH', ['n = 0;']),
    'nl': _ax('NL', ['end = 0;\n\t\t\tn = 0;']),
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
