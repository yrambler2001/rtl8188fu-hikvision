# process_config_vars - stage 21: the two blocks that are still structurally
# different once the guard emits a single `orrs`/`beq`.
#
#  * the `(pos | n) != 0` arm: shipped keeps `pos = 0` inside both arms of the
#    `n` test (`moveq r2, r6` and `movne r2, r6`), ours hoists it into one
#    shared `mov`, because cross-jumping merges the two arms' tails - which it
#    can only do if the *last* copy in each arm is the same instruction;
#  * the `pick[j-1] == ' ' && buf[i] == ' '` test: shipped materialises `m` as
#    0/1 with a conditional-move pair and then branches on the same flags,
#    ours branches straight to the shared `m = 1`.
import os

UNIT = 'ez_wifi_config'
FUNC = 'process_config_vars'


def _ax(name, default):
    v = os.environ.get('PCV21_' + name)
    return v.split('|') if v else default


GT = [
    ("np_pe", "if (n) {\n\t\t\t\t\tn = 0;\n\t\t\t\t\tpos = 0;\n\t\t\t\t} else {\n\t\t\t\t\tpos = 0;\n\t\t\t\t\tend = 0;\n\t\t\t\t}"),
    ("pn_pe", "if (n) {\n\t\t\t\t\tpos = 0;\n\t\t\t\t\tn = 0;\n\t\t\t\t} else {\n\t\t\t\t\tpos = 0;\n\t\t\t\t\tend = 0;\n\t\t\t\t}"),
    ("np_ep", "if (n) {\n\t\t\t\t\tn = 0;\n\t\t\t\t\tpos = 0;\n\t\t\t\t} else {\n\t\t\t\t\tend = 0;\n\t\t\t\t\tpos = 0;\n\t\t\t\t}"),
    ("pn_ep", "if (n) {\n\t\t\t\t\tpos = 0;\n\t\t\t\t\tn = 0;\n\t\t\t\t} else {\n\t\t\t\t\tend = 0;\n\t\t\t\t\tpos = 0;\n\t\t\t\t}"),
    ("inv_pe_np", "if (!n) {\n\t\t\t\t\tpos = 0;\n\t\t\t\t\tend = 0;\n\t\t\t\t} else {\n\t\t\t\t\tn = 0;\n\t\t\t\t\tpos = 0;\n\t\t\t\t}"),
    ("eq0", "if (n == 0) {\n\t\t\t\t\tpos = 0;\n\t\t\t\t\tend = 0;\n\t\t\t\t} else {\n\t\t\t\t\tn = 0;\n\t\t\t\t\tpos = 0;\n\t\t\t\t}"),
    ("hoist", "if (n)\n\t\t\t\t\tn = 0;\n\t\t\t\telse\n\t\t\t\t\tend = 0;\n\t\t\t\tpos = 0;"),
    ("pre", "pos = 0;\n\t\t\t\tif (n)\n\t\t\t\t\tn = 0;\n\t\t\t\telse\n\t\t\t\t\tend = 0;"),
]

MB = [
    ("last_m", "int last = pick[j - 1];\n\n\t\t\t\t\tm = (last == ' ' && buf[i] == ' ');\n\t\t\t\t\tif (m) {\n\t\t\t\t\t\tpos = 0;\n\t\t\t\t\t\tcontinue;\n\t\t\t\t\t}"),
    ("nolast_m", "m = (pick[j - 1] == ' ' && buf[i] == ' ');\n\t\t\t\t\tif (m) {\n\t\t\t\t\t\tpos = 0;\n\t\t\t\t\t\tcontinue;\n\t\t\t\t\t}"),
    ("last_if", "int last = pick[j - 1];\n\n\t\t\t\t\tif (last == ' ' && buf[i] == ' ') {\n\t\t\t\t\t\tm = 1;\n\t\t\t\t\t\tpos = 0;\n\t\t\t\t\t\tcontinue;\n\t\t\t\t\t}"),
    ("rev_m", "int last = pick[j - 1];\n\n\t\t\t\t\tm = (buf[i] == ' ' && last == ' ');\n\t\t\t\t\tif (m) {\n\t\t\t\t\t\tpos = 0;\n\t\t\t\t\t\tcontinue;\n\t\t\t\t\t}"),
    ("and_m", "int last = pick[j - 1];\n\n\t\t\t\t\tm = (last == ' ') & (buf[i] == ' ');\n\t\t\t\t\tif (m) {\n\t\t\t\t\t\tpos = 0;\n\t\t\t\t\t\tcontinue;\n\t\t\t\t\t}"),
    ("mne_m", "int last = pick[j - 1];\n\n\t\t\t\t\tm = (last == ' ' && buf[i] == ' ');\n\t\t\t\t\tif (m != 0) {\n\t\t\t\t\t\tpos = 0;\n\t\t\t\t\t\tcontinue;\n\t\t\t\t\t}"),
    ("meq1_m", "int last = pick[j - 1];\n\n\t\t\t\t\tm = (last == ' ' && buf[i] == ' ');\n\t\t\t\t\tif (m == 1) {\n\t\t\t\t\t\tpos = 0;\n\t\t\t\t\t\tcontinue;\n\t\t\t\t\t}"),
]

AXES = {
    'g': _ax('G', ['(pos | n) | (pos & n)', '(pos | n) == 1']),
    'tpos': _ax('TPOS', ['unsigned int']),
    'tn': _ax('TN', ['u32']),
    'gt': [(g[0], '%d' % i) for i, g in enumerate(GT)],
    'mb': [(m[0], '%d' % i) for i, m in enumerate(MB)],
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
\t\t\t\t\t%(mbb)s
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
    d['gtb'] = GT[int(c['gt'])][1]
    d['mbb'] = MB[int(c['mb'])][1]
    return TEMPLATE % d
