# process_config_vars - stage 30: the last five instructions, everything crossed.
#
# Five instruction-level differences remain and they are two mechanisms:
#
#  * the guard temp is coalesced into pos's partition, because uncprop rewrites
#    all seven main-path `pos = 0` PHI arguments into it and out-of-SSA's
#    coalesce costs accumulate per edge - seven beats pos's own two - so the
#    `orr` writes pos's register and pos needs a second one plus a latch copy;
#  * the shipped build materialises `m` with a `moveq #1` / `movne #0` pair and
#    branches on the same flags, where ours branches straight to the shared
#    `m = 1` because VRP proves the flag is 1 on the taken edge.
#
# This crosses every axis that has ever moved either of them: the declaration
# order (which is the PHI order, which is the copy order), the `n`-test arms,
# the `#` and `\n` arms, and the guard spelling.
import itertools, os

UNIT = 'ez_wifi_config'
FUNC = 'process_config_vars'

DECLS = {'i': '\tu32 i;', 'pos': '\t%(tpos)s pos = 0;', 'n': '\t%(tn)s n = 0;',
         'm': '\tint m = 0;', 'j': '\tint j = 0;', 'end': '\tint end = 0;'}
KEY = {'i': 'i', 'p': 'pos', 'n': 'n', 'm': 'm', 'j': 'j', 'e': 'end'}
def _arm(a, b):
    return "if (n) {\n\t\t\t\t\t%s\n\t\t\t\t} else {\n\t\t\t\t\t%s\n\t\t\t\t}" % (a, b)


_TRUE = ["n = 0;\n\t\t\t\t\tpos = n;", "pos = 0;\n\t\t\t\t\tn = 0;",
         "n = 0;\n\t\t\t\t\tpos = 0;", "pos = n - n;\n\t\t\t\t\tn = 0;"]
_FALSE = ["pos = n;\n\t\t\t\t\tend = 0;", "end = 0;\n\t\t\t\t\tpos = n;",
          "pos = n;\n\t\t\t\t\tend = n;", "end = n;\n\t\t\t\t\tpos = n;",
          "pos = 0;\n\t\t\t\t\tend = 0;"]
GT = [("a%d_%d" % (i, j), _arm(a, b))
      for i, a in enumerate(_TRUE) for j, b in enumerate(_FALSE)]


def _ax(name, default):
    v = os.environ.get('PCV29_' + name)
    return v.split('|') if v else default


AXES = {
    'order': _ax('ORDER', [''.join(p) for p in itertools.permutations('ipnmje')]),
    'g': _ax('G', ['(pos | n) | (pos & n)',
                   '((int)(pos | n)) | ((int)(pos & n))']),
    'gt': [(g[0], '%d' % i) for i, g in enumerate(GT)],
    'hash': _ax('HASH', ['n = 0;', 'n = pos;']),
    'nl': _ax('NL', ['end = 0;\n\t\t\tn = 0;', 'n = 0;\n\t\t\tend = 0;']),
    'tpos': _ax('TPOS', ['unsigned int']),
    'tn': _ax('TN', ['u32']),
}

TEMPLATE = """int process_config_vars(char *buf, u32 len, char *pick, const char *var)
{
%(decls)s

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
    d['decls'] = '\n'.join(DECLS[KEY[ch]] % c for ch in c['order'])
    d['gtb'] = GT[int(c['gt'])][1]
    return TEMPLATE % d
