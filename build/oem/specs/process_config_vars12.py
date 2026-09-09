# Variant spec for ez_wifi_config.c:process_config_vars - stage 12.
#
# Mechanism, read out of GCC 6.5.0 rather than guessed:
#
#   * `uncprop` replaces a PHI argument that is the constant 0 with any SSA
#     name known equal to 0 on that edge, but only if
#     `gimple_can_coalesce_p (equiv, phi_result)` - which for two integer
#     types means the same TYPE_CANONICAL, i.e. the same signedness.
#   * With `pos` and the guard temp both unsigned, `pos_5 = PHI <..., _30, ...>`
#     on every `pos = 0` edge, out-of-SSA coalesces the guard temp into pos's
#     partition, the `orr` writes pos's register, and pos needs a second
#     register plus a latch copy.  The shipped build has `mov r2, #0` in a
#     shared tail instead, so there the guard temp is *not* coalescable with
#     `pos`.
#   * `register_edge_assert_for` recurses into an IOR's operands only when
#     SSA_NAME_DEF_STMT of the compared name *is* the IOR.  Any conversion in
#     between blocks it, which is what keeps `n` live across strlen/memcmp
#     without needing the `== 1` spelling that costs an extra `cmp`.
#
# So the axis that matters is the type of the guard value relative to `pos`
# and to `end`/`m`/`j`.
import os

UNIT = 'ez_wifi_config'
FUNC = 'process_config_vars'


def _ax(name, default):
    v = os.environ.get('PCV12_' + name)
    return v.split('|') if v else default


AXES = {
    'guard': _ax('GUARD', [
        ('cast_int',   'if ((int)(pos | n)) {'),
        ('plain',      'if (pos | n) {'),
        ('eq1',        'if ((pos | n) == 1) {'),
        ('cast_uint',  'if ((unsigned int)(pos | n)) {'),
        ('cast_s32',   'if ((s32)(pos | n)) {'),
        ('cast_u32',   'if ((u32)(pos | n)) {'),
    ]),
    'tpos': _ax('TPOS', ['unsigned int', 'int', 'u32', 's32']),
    'tn': _ax('TN', ['int', 'u32', 'unsigned int', 's32']),
    'tend': _ax('TEND', ['int']),
    'tm': _ax('TM', ['int']),
    'tj': _ax('TJ', ['int']),
    'hash': _ax('HASH', ['n = 0;', 'n = pos;', 'n |= pos;']),
    'nl': _ax('NL', ['end = pos | n;\n\t\t\tn |= pos;',
                     'end = 0;\n\t\t\tn = 0;',
                     'n = 0;\n\t\t\tend = 0;']),
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

\t\t%(guard)s
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
