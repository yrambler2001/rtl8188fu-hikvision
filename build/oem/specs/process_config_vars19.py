# process_config_vars - stage 19: declaration order is PHI order.
#
# Out-of-SSA emits one copy per PHI on each incoming edge, in the order the
# PHIs sit in the block, and `into_ssa` creates those PHIs in the order of the
# variables' SSA versions - which is the order the locals are declared.  That
# order decides which copy is *last* in each arm of the `n` test, and therefore
# whether cross-jumping can merge the two arms' tails.  The shipped build does
# not merge them (`moveq r2, r6` and `movne r2, r6` are both there); ours does.
#
# So this sweeps the declaration order of the six locals, on top of the guard
# spelling from stage 18 that already blocks VRP's assertion while still
# emitting a single `orrs`.
import itertools, os

UNIT = 'ez_wifi_config'
FUNC = 'process_config_vars'

DECLS = {
    'i': '\tu32 i;',
    'pos': '\t%(tpos)s pos = 0;',
    'n': '\t%(tn)s n = 0;',
    'm': '\tint m = 0;',
    'j': '\tint j = 0;',
    'end': '\tint end = 0;',
}
ORDERS = [''.join(p) for p in itertools.permutations('ipnmje')]
KEY = {'i': 'i', 'p': 'pos', 'n': 'n', 'm': 'm', 'j': 'j', 'e': 'end'}


def _ax(name, default):
    v = os.environ.get('PCV19_' + name)
    return v.split('|') if v else default


AXES = {
    'order': _ax('ORDER', ORDERS),
    'g': _ax('G', ['(pos | n) | (pos & n)']),
    'tpos': _ax('TPOS', ['unsigned int']),
    'tn': _ax('TN', ['u32']),
    'gt': _ax('GT', [('pe_np', 'pos = 0;\n\t\t\t\t\tend = 0;|n = 0;\n\t\t\t\t\tpos = 0;')]),
}

TEMPLATE = """int process_config_vars(char *buf, u32 len, char *pick, const char *var)
{
%(decls)s

\tfor (i = 0; i < len; i++) {
\t\tif (buf[i] == '\\r')
\t\t\tcontinue;

\t\tif (%(g)s) {
\t\t\tif (buf[i] == '\\n') {
\t\t\t\tif (n) {
\t\t\t\t\t%(gt_ne)s
\t\t\t\t} else {
\t\t\t\t\t%(gt_eq)s
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
    d['decls'] = '\n'.join(DECLS[KEY[ch]] % c for ch in c['order'])
    eq, ne = c['gt'].split('|')
    d['gt_eq'], d['gt_ne'] = eq, ne
    return TEMPLATE % d
