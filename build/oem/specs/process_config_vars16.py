# process_config_vars - stage 16: a guard temp of its own type.
#
# The shipped guard is a single `orrs r9, r2, r6` followed by `beq`, i.e. a
# comparison against zero - and that is load-bearing twice over.  It is what
# lets `cse1` replace every `mov rX, #0` on the main path with `mov rX, r9`
# (the shipped `moveq r6, r9`, `moveq r4, r9`, `movne r4, r9`, none of which
# we produce), because after `orrs`/`beq` the register is provably zero there.
#
# But a plain `if (pos | n)` makes GCC 6's `register_edge_assert_for` recurse
# into the IOR and assert `n == 0` on the main path, which rematerialises `n`
# and loses the shipped register allocation.  The recursion keys on
# SSA_NAME_DEF_STMT of the *compared* name being the BIT_IOR itself, so a
# guard value held in a variable of a different signedness -
#
#     unsigned int t = pos | n;   /* with pos, n int */
#     if (t) { ... }
#
# - puts a NOP_EXPR in between, blocks the recursion, and is still one `orrs`.
import os

UNIT = 'ez_wifi_config'
FUNC = 'process_config_vars'


def _ax(name, default):
    v = os.environ.get('PCV16_' + name)
    return v.split('|') if v else default


# (label, declaration line or '', condition text)
GUARDS = [
    ('none', '', 'pos | n'),
    ('eq1', '', '(pos | n) == 1'),
    ('ti', 'int t = pos | n;', 't'),
    ('tu', 'unsigned int t = pos | n;', 't'),
    ('tu32', 'u32 t = pos | n;', 't'),
    ('ts32', 's32 t = pos | n;', 't'),
    ('tl', 'long t = pos | n;', 't'),
    ('tul', 'unsigned long t = pos | n;', 't'),
    ('tsz', 'size_t t = pos | n;', 't'),
    ('tine', 'int t = pos | n;', 't != 0'),
    ('tune', 'unsigned int t = pos | n;', 't != 0'),
]

AXES = {
    'g': _ax('G', [(g[0], '%d' % i) for i, g in enumerate(GUARDS)]),
    'tpos': _ax('TPOS', ['int', 'unsigned int', 'u32', 's32']),
    'tn': _ax('TN', ['int', 'u32', 'unsigned int', 's32']),
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

%(decl)s\t\tif (%(cond)s) {
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
    d = dict(c)
    _, decl, cond = GUARDS[int(c['g'])]
    d['decl'] = ('\t\t%s\n\n' % decl) if decl else ''
    d['cond'] = cond
    return TEMPLATE % d
