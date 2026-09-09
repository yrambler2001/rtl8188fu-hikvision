# Variant spec for ez_wifi_config.c:process_config_vars - stage 10.
#
# Stage 9 settled the outer shape (if-chain, `pos = 0` per path, `pos` a
# different tree type from `n`), which is instruction edit distance 12 out of
# 86 and puts everything from the `strlen` call to the end of the comparison
# byte for byte.  What is left is the default arm and the entry: the shipped
# build spills `pick` and keeps `n` in a callee-saved register across the two
# calls, ours keeps `pick` in `sl`.
#
# So this sweeps the inside of the default arm - the types of its three
# temporaries, how `skip` is computed, how the "found it" branch is written,
# and how the character is stored into `pick`.
import os

UNIT = 'ez_wifi_config'
FUNC = 'process_config_vars'


def _ax(name, default):
    v = os.environ.get('PCV10_' + name)
    return v.split(',') if v else default


AXES = {
    'tvlen': _ax('TVLEN', ['size_t', 'int', 'u32', 'unsigned int']),
    'tcmp': _ax('TCMP', ['int', 's32']),
    'tskip': _ax('TSKIP', ['int', 's32', 'u32']),
    'tlast': _ax('TLAST', ['int', 'char', 'u8']),
    'skipf': _ax('SKIPF', ['k0', 'k1', 'k2']),
    'store': _ax('STORE', ['p0', 'p1']),
    'found': _ax('FOUND', ['f0', 'f1']),
    'mset': _ax('MSET', ['m0', 'm1']),
}

SKIP = {
    'k0': ("\t\t\t\t%(tskip)s skip;\n\n"
           "\t\t\t\tif (end)\n\t\t\t\t\tskip = 0;\n"
           "\t\t\t\telse\n\t\t\t\t\tskip = m & 1;\n"
           "\t\t\t\tif (skip) {\n"),
    'k1': ("\t\t\t\t%(tskip)s skip = end ? 0 : (m & 1);\n\n"
           "\t\t\t\tif (skip) {\n"),
    'k2': ("\t\t\t\t%(tskip)s skip;\n\n"
           "\t\t\t\tskip = end ? 0 : m & 1;\n"
           "\t\t\t\tif (skip) {\n"),
}

FOUND = {
    'f0': '\t\t\t\tend = vlen;\n\t\t\t\tj = 0;\n\t\t\t\ti += end;\n',
    'f1': '\t\t\t\tj = 0;\n\t\t\t\tend = vlen;\n\t\t\t\ti += end;\n',
}

STORE = {
    'p0': '\t\t\t\tpick[j++] = buf[i];\n',
    'p1': '\t\t\t\tpick[j] = buf[i];\n\t\t\t\tj++;\n',
}

MSET = {
    'm0': ("\t\t\t\t\tm = (last == ' ' && buf[i] == ' ');\n"
           "\t\t\t\t\tif (m) {\n\t\t\t\t\t\tpos = 0;\n"
           "\t\t\t\t\t\tcontinue;\n\t\t\t\t\t}\n"),
    'm1': ("\t\t\t\t\tif (last == ' ' && buf[i] == ' ') {\n"
           "\t\t\t\t\t\tm = 1;\n\t\t\t\t\t\tpos = 0;\n"
           "\t\t\t\t\t\tcontinue;\n\t\t\t\t\t}\n\t\t\t\t\tm = 0;\n"),
}

TEMPLATE = """int process_config_vars(char *buf, u32 len, char *pick, const char *var)
{
\tu32 i;
\tunsigned int pos = 0;
\tu32 n = 0;
\tint m = 0;
\tint j = 0;
\tint end = 0;

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

\t\tif (buf[i] == '#') {
\t\t\tn |= pos;
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
\t\t\t%(tvlen)s vlen = strlen(var);
\t\t\t%(tcmp)s cmp = memcmp(&buf[i], var, vlen);

\t\t\tif (!end && !cmp) {
%(found)s\t\t\t} else {
%(skip)s\t\t\t\t\tend = 0;
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
\t\t\t\t\t%(tlast)s last = pick[j - 1];

%(mset)s\t\t\t\t}
%(store)s\t\t\t}
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
    d['skip'] = SKIP[c['skipf']] % {'tskip': c['tskip']}
    d['found'] = FOUND[c['found']]
    d['store'] = STORE[c['store']]
    d['mset'] = MSET[c['mset']]
    return TEMPLATE % d
