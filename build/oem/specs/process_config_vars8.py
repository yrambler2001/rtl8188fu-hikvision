# Variant spec for ez_wifi_config.c:process_config_vars - stage 8.
#
# Stage 7 found two things that help: the selector written as an if-chain
# rather than a `switch`, and `pos = 0` written on each path that falls out of
# it rather than once afterwards.  Together they take the instruction edit
# distance from 21 to 13.  This sweeps that shape against the full type cross
# product - a typedef of `int` is a distinct node to uncprop and to
# gimple_can_coalesce_p (section 15), so `int`, `s32`, `u32` and `long` are
# four different types here even though three of them are the same 32-bit
# integer.
import os

UNIT = 'ez_wifi_config'
FUNC = 'process_config_vars'


def _ax(name, default):
    v = os.environ.get('PCV8_' + name)
    return v.split(',') if v else default


W = ['int', 's32', 'u32', 'long']

AXES = {
    'tpos': _ax('TPOS', ['int', 'unsigned int']),
    'tn': _ax('TN', W),
    'tm': _ax('TM', W),
    'tj': _ax('TJ', W),
    'tend': _ax('TEND', W),
    'sel': _ax('SEL', ['w2', 'w3']),
    'guard': _ax('GUARD', ['n || pos']),
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

%(body)s\t}

\treturn j;
}
"""


def render(c):
    els = '\t\telse ' if c['sel'] == 'w2' else '\t\t'
    body = ("\t\tif (buf[i] == '#') {\n\t\t\tn |= pos;\n\t\t\tpos = 1;\n"
            "\t\t\tcontinue;\n\t\t}\n")
    body += (els + "if (buf[i] == '\\\\') {\n\t\t\tn = 1;\n\t\t\tpos = 0;\n"
             "\t\t\tcontinue;\n\t\t}\n")
    body += (els + "if (buf[i] == '\\n') {\n\t\t\tend = pos | n;\n"
             "\t\t\tn |= pos;\n\t\t\tpos = 0;\n\t\t\tcontinue;\n\t\t}\n")
    body += ('\t\telse {\n' if c['sel'] == 'w2' else '\t\t{\n') + DEFAULT + '\t\t}\n'
    d = dict(c)
    d['body'] = body
    return TEMPLATE % d
