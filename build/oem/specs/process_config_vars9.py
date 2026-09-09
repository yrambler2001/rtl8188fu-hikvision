# Variant spec for ez_wifi_config.c:process_config_vars - stage 9.
#
# Stage 8 settled the shape: an if-chain rather than a `switch`, `pos = 0`
# written on each path that falls out of it, and `pos` a different type from
# the `pos | n` the guard computes (`unsigned int` against `u32` - a typedef
# of `unsigned int`, and a distinct tree node to uncprop, section 15).  That
# is instruction edit distance 12 out of 86, from 21.
#
# This sweeps the rest of the structure against it: how the guard is spelt,
# how its body tests `n`, and how the two `|=` in the selector are written.
import os

UNIT = 'ez_wifi_config'
FUNC = 'process_config_vars'


def _ax(name, default):
    v = os.environ.get('PCV9_' + name)
    return v.split(',') if v else default


AXES = {
    'tn': _ax('TN', ['u32', 's32', 'long', 'int']),
    'tm': _ax('TM', ['int', 'u32']),
    'tj': _ax('TJ', ['int', 'u32']),
    'tend': _ax('TEND', ['int', 'u32']),
    'tpos': _ax('TPOS', ['unsigned int', 'int']),
    'guard': _ax('GUARD', ['q0', 'q1', 'q2', 'q3']),
    'inner': _ax('INNER', ['i0', 'i1', 'i2']),
    'hash': _ax('HASH', ['h0', 'h1']),
    'nl': _ax('NL', ['e0', 'e1', 'e2']),
}

GUARDS = {
    'q0': 'n || pos',
    'q1': 'pos || n',
    'q2': 'n | pos',
    'q3': 'pos | n',
}

INNER = {
    'i0': ("\t\t\t\tif (n) {\n\t\t\t\t\tn = 0;\n\t\t\t\t\tpos = 0;\n"
           "\t\t\t\t} else {\n\t\t\t\t\tpos = 0;\n\t\t\t\t\tend = 0;\n\t\t\t\t}\n"),
    'i1': ("\t\t\t\tif (!n) {\n\t\t\t\t\tpos = 0;\n\t\t\t\t\tend = 0;\n"
           "\t\t\t\t} else {\n\t\t\t\t\tn = 0;\n\t\t\t\t\tpos = 0;\n\t\t\t\t}\n"),
    'i2': ("\t\t\t\tpos = 0;\n\t\t\t\tif (n)\n\t\t\t\t\tn = 0;\n"
           "\t\t\t\telse\n\t\t\t\t\tend = 0;\n"),
}

HASH = {
    'h0': '\t\t\tn |= pos;\n\t\t\tpos = 1;\n\t\t\tcontinue;\n',
    'h1': '\t\t\tn = n | pos;\n\t\t\tpos = 1;\n\t\t\tcontinue;\n',
}

NL = {
    'e0': '\t\t\tend = pos | n;\n\t\t\tn |= pos;\n\t\t\tpos = 0;\n\t\t\tcontinue;\n',
    'e1': '\t\t\tn |= pos;\n\t\t\tend = n;\n\t\t\tpos = 0;\n\t\t\tcontinue;\n',
    'e2': '\t\t\tend = pos | n;\n\t\t\tn = end;\n\t\t\tpos = 0;\n\t\t\tcontinue;\n',
}

DEFAULT = """\t\t\tsize_t vlen = strlen(var);
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
"""

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
%(inner)s\t\t\t}
\t\t\tcontinue;
\t\t}

\t\tif (buf[i] == '#') {
%(hash)s\t\t}
\t\telse if (buf[i] == '\\\\') {
\t\t\tn = 1;
\t\t\tpos = 0;
\t\t\tcontinue;
\t\t}
\t\telse if (buf[i] == '\\n') {
%(nl)s\t\t}
\t\telse {
%(default)s\t\t}
\t}

\treturn j;
}
"""


def render(c):
    d = dict(c)
    d['guard'] = GUARDS[c['guard']]
    d['inner'] = INNER[c['inner']]
    d['hash'] = HASH[c['hash']]
    d['nl'] = NL[c['nl']]
    d['default'] = DEFAULT
    return TEMPLATE % d
