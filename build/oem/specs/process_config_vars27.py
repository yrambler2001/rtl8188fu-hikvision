# process_config_vars - stage 27: the last three instructions.
#
# With `(pos | n) | (pos & n)` as the guard - one `orrs`, and VRP's assertion
# blocked because the recursion one level down is gated on `has_single_use` -
# and the `n` test's arms writing `pos = n` rather than `pos = 0`, five
# instruction-level differences remain.  Three are the guard temp being
# coalesced into pos's partition: uncprop rewrites the seven main-path
# `pos = 0` PHI arguments into it, and out-of-SSA's coalesce costs accumulate
# per edge, so seven beats the two edges on which pos is unchanged.
#
# The only way to lose that is to have fewer edges carrying the temp, so this
# sweeps where `pos = 0` is written: once at the end of the loop body, reached
# by `goto`, versus once per arm.
import itertools, os

UNIT = 'ez_wifi_config'
FUNC = 'process_config_vars'


def _ax(name, default):
    v = os.environ.get('PCV27_' + name)
    return v.split('|') if v else default


GT = [
    ("mix", "if (n) {\n\t\t\t\t\tn = 0;\n\t\t\t\t\tpos = n;\n\t\t\t\t} else {\n\t\t\t\t\tpos = n;\n\t\t\t\t\tend = 0;\n\t\t\t\t}"),
    ("fromn", "if (n) {\n\t\t\t\t\tn = 0;\n\t\t\t\t\tpos = n;\n\t\t\t\t} else {\n\t\t\t\t\tpos = n;\n\t\t\t\t\tend = n;\n\t\t\t\t}"),
    ("zero", "if (n) {\n\t\t\t\t\tn = 0;\n\t\t\t\t\tpos = 0;\n\t\t\t\t} else {\n\t\t\t\t\tpos = 0;\n\t\t\t\t\tend = 0;\n\t\t\t\t}"),
]

AXES = {
    'g': _ax('G', ['(pos | n) | (pos & n)']),
    'tpos': _ax('TPOS', ['unsigned int']),
    'tn': _ax('TN', ['u32']),
    'gt': [(g[0], '%d' % i) for i, g in enumerate(GT)],
    'posz': _ax('POSZ', ['arm', 'tail']),
    'mb': _ax('MB', ['0', '1', '2']),
}

MB = [
    "int last = pick[j - 1];\n\n\t\t\t\t\tm = (last == ' ' && buf[i] == ' ');\n\t\t\t\t\tif (m) {\n\t\t\t\t\t\t%(pz)s\n\t\t\t\t\t}",
    "int last = pick[j - 1];\n\n\t\t\t\t\tif (last == ' ' && buf[i] == ' ') {\n\t\t\t\t\t\tm = 1;\n\t\t\t\t\t\t%(pz)s\n\t\t\t\t\t}",
    "m = (pick[j - 1] == ' ' && buf[i] == ' ');\n\t\t\t\t\tif (m) {\n\t\t\t\t\t\t%(pz)s\n\t\t\t\t\t}",
]

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
\t\t\t\t%(gtb)s
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
\t\t\t%(pz)s
\t\t}
\t\telse if (buf[i] == '\\n') {
\t\t\tend = 0;
\t\t\tn = 0;
\t\t\t%(pz)s
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
\t\t\t\t\t%(pz)s
\t\t\t\t}
\t\t\t\tend++;
\t\t\t\tif (!m) {
\t\t\t\t\t%(pz)s
\t\t\t\t}
\t\t\t}
\t\t\tif (buf[i] != '\\t') {
\t\t\t\tif (j) {
\t\t\t\t\t%(mbb)s
\t\t\t\t}
\t\t\t\tpick[j++] = buf[i];
\t\t\t}
\t\t\tm = 1;
\t\t\t%(pz)s
\t\t}
%(label)s\t}

\treturn j;
}
"""


def render(c):
    d = dict(c)
    if c['posz'] == 'arm':
        d['pz'] = 'pos = 0;\n\t\t\tcontinue;'
        d['label'] = ''
        mbpz = 'pos = 0;\n\t\t\t\t\t\tcontinue;'
    else:
        d['pz'] = 'goto zero_pos;'
        d['label'] = 'zero_pos:\n\t\tpos = 0;\n'
        mbpz = 'goto zero_pos;'
    d['gtb'] = GT[int(c['gt'])][1]
    d['mbb'] = MB[int(c['mb'])] % {'pz': mbpz}
    out = TEMPLATE % d
    if c['posz'] == 'tail':
        # the arms use goto, so drop the stray continue in the last arm
        out = out.replace('\t\t\tm = 1;\n\t\t\tgoto zero_pos;\n\t\t}',
                          '\t\t\tm = 1;\n\t\t}')
    return out
