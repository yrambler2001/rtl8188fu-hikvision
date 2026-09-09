# process_config_vars - stage 25: stop uncprop putting the guard temp into
# pos's PHI, and keep the guard-true arms out of the shared `pos = 0` tail.
#
# Out-of-SSA coalescing is cost-based and the costs *accumulate per edge*
# (`add_coalesce`), so with seven main-path edges carrying `pos_5 = _30` -
# uncprop having rewritten each `pos = 0` into the guard temp - the temp beats
# `pos_6`'s two edges and the IOR ends up writing pos's own register, which
# costs a second register and a latch copy.  Making the guard value's type
# canonically different from pos's stops the rewrite: the zeros stay constants,
# `pos_6` wins, and the seven `mov r2, #0` copies cross-jump into one shared
# tail.
#
# That alone puts the guard-true arms' `pos = 0` in the same shared tail, which
# the shipped build does not do - there they are `moveq r2, r6` / `movne r2, r6`,
# i.e. copies from `n`.  Writing them as `pos = n` (which is what they mean:
# on that edge `n` is the zero) makes them SSA copies instead of constants, so
# cross-jumping cannot merge them with `mov r2, #0`.
import os

UNIT = 'ez_wifi_config'
FUNC = 'process_config_vars'


def _ax(name, default):
    v = os.environ.get('PCV26_' + name)
    return v.split('|') if v else default


GT = [
    ("zero", "if (n) {\n\t\t\t\t\tn = 0;\n\t\t\t\t\tpos = 0;\n\t\t\t\t} else {\n\t\t\t\t\tpos = 0;\n\t\t\t\t\tend = 0;\n\t\t\t\t}"),
    ("fromn", "if (n) {\n\t\t\t\t\tn = 0;\n\t\t\t\t\tpos = n;\n\t\t\t\t} else {\n\t\t\t\t\tpos = n;\n\t\t\t\t\tend = n;\n\t\t\t\t}"),
    ("fromn2", "if (n) {\n\t\t\t\t\tn = 0;\n\t\t\t\t\tpos = n;\n\t\t\t\t} else {\n\t\t\t\t\tend = n;\n\t\t\t\t\tpos = n;\n\t\t\t\t}"),
    ("mix", "if (n) {\n\t\t\t\t\tn = 0;\n\t\t\t\t\tpos = n;\n\t\t\t\t} else {\n\t\t\t\t\tpos = n;\n\t\t\t\t\tend = 0;\n\t\t\t\t}"),
]

AXES = {
    'g': _ax('G', ['(pos | n) | (pos & n)',
                   '((int)(pos | n)) | ((int)(pos & n))',
                   '((unsigned int)(pos | n)) | ((unsigned int)(pos & n))',
                   '((int)(pos | n)) | ((int)(pos & n)) | ((int)(pos ^ n))',
                   '((long)(pos | n)) | ((long)(pos & n))',
                   '((s32)(pos | n)) | ((s32)(pos & n))',
                   '(int)(pos | n) | (pos & n)',
                   '(pos | n) | (int)(pos & n)']),
    'tpos': _ax('TPOS', ['unsigned int', 'u32']),
    'tn': _ax('TN', ['u32', 'unsigned int']),
    'gt': [(g[0], '%d' % i) for i, g in enumerate(GT)],
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
    d['gtb'] = GT[int(c['gt'])][1]
    return TEMPLATE % d
