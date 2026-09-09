# process_config_vars - stage 13: where `pos = 0` lives.
#
# The shipped build has a single `mov r2, #0` in a shared tail just before the
# `i++`, and `pos` never needs a second register.  Ours had `pos = 0` written
# in every arm, so out-of-SSA saw `pos_5 = PHI <..., _30, _30, _30, ...>` -
# uncprop having replaced each constant 0 with the guard temp, which is legal
# because both are `unsigned int` - coalesced the guard temp into pos's
# partition, and had to carry pos in a second register with a latch copy.
#
# Writing `pos = 0` once, at the end of the loop body, takes it out of the PHI
# entirely: it becomes a statement, uncprop never sees it, and nothing can
# coalesce the guard temp with pos.
import os

UNIT = 'ez_wifi_config'
FUNC = 'process_config_vars'


def _ax(name, default):
    v = os.environ.get('PCV23_' + name)
    return v.split('|') if v else default


AXES = {
    'guard': _ax('GUARD', [
        ('g00', '(pos | n) | (pos & n)'),
        ('g01', '(n | pos) | (n & pos)'),
        ('g02', '(pos ^ n) | (pos & n)'),
        ('plain', 'pos | n'),
        ('eq1', '(pos | n) == 1'),
    ]),
    'tpos': _ax('TPOS', ['unsigned int', 'int']),
    'tn': _ax('TN', ['u32', 'int']),
    'hash': _ax('HASH', ['n = 0;', 'n = pos;', 'n |= pos;']),
    'nl': _ax('NL', ['end = 0;\n\t\t\tn = 0;',
                     'n = 0;\n\t\t\tend = 0;',
                     'end = pos | n;\n\t\t\tn = end;',
                     'end = pos | n;\n\t\t\tn |= pos;']),
    'skipz': _ax('SKIPZ', ['end = 0;\n\t\t\t\t\tm = 0;',
                           'm = 0;\n\t\t\t\t\tend = 0;',
                           'end = pos | n;\n\t\t\t\t\tm = end;']),
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
\t\t}
\t\telse if (buf[i] == '\\n') {
\t\t\t%(nl)s
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
\t\t\t\t\t%(skipz)s
\t\t\t\t\tgoto zero_pos;
\t\t\t\t}
\t\t\t\tend++;
\t\t\t\tif (!m)
\t\t\t\t\tgoto zero_pos;
\t\t\t}
\t\t\tif (buf[i] != '\\t') {
\t\t\t\tif (j) {
\t\t\t\t\tint last = pick[j - 1];

\t\t\t\t\tm = (last == ' ' && buf[i] == ' ');
\t\t\t\t\tif (m)
\t\t\t\t\t\tgoto zero_pos;
\t\t\t\t}
\t\t\t\tpick[j++] = buf[i];
\t\t\t}
\t\t\tm = 1;
\t\t}
zero_pos:
\t\tpos = 0;
\t}

\treturn j;
}
"""


def render(c):
    return TEMPLATE % c
