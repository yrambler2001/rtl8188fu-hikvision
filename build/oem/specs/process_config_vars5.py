# Variant spec for ez_wifi_config.c:process_config_vars - stage 5, the shared
# tail.
#
# What closed `ez_scan_device_ioctl_handle` was the realisation that at `-Os` a
# shared tail in the shipped code is evidence of *duplicated source*, not of a
# `goto`: block layout is source order, so two copies that cross-jumping merges
# and one `goto` to a common label produce the same final layout - but not the
# same expression graph on the way there.
#
# This function has the same shape.  The shipped code reaches `mov r2, #0`
# (`pos = 0`) from every `break` path of the switch and `add r8, r8, #1` (the
# loop increment) from every `continue` path.  Ours writes `pos = 0` once,
# after the switch.  These variants write it at the end of each break path
# instead - six of them, four inside the default case - and let cross-jumping
# put it back together, crossed with the type family from stage 2.
import os

UNIT = 'ez_wifi_config'
FUNC = 'process_config_vars'


def _ax(name, default):
    v = os.environ.get('PCV5_' + name)
    return v.split(',') if v else default


AXES = {
    'ty': _ax('TY', ['t0', 't1', 't2', 't3']),
    'dup': _ax('DUP', ['d0', 'd1', 'd2']),
    'guard': _ax('GUARD', ['g0', 'g1']),
}

# (pos, n, m, j, end)
TYPES = {
    't0': ('int', 'int', 'int', 'int', 'int'),
    't1': ('int', 's32', 'int', 'int', 'int'),
    't2': ('int', 's32', 's32', 'int', 'int'),
    't3': ('int', 'long', 'int', 'int', 'int'),
}

GUARDS = {
    'g0': "\t\tif (n || pos) {\n",
    'g1': "\t\tif (pos || n) {\n",
}

HEAD = """int process_config_vars(char *buf, u32 len, char *pick, const char *var)
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

%(guard)s\t\t\tif (buf[i] == '\\n') {
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

\t\tswitch (buf[i]) {
\t\tcase '#':
\t\t\tn |= pos;
\t\t\tpos = 1;
\t\t\tcontinue;
\t\tcase '\\\\':
\t\t\tn = 1;
%(B1)s\t\tcase '\\n':
\t\t\tend = pos | n;
\t\t\tn |= pos;
%(B1)s\t\tdefault: {
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
%(B4)s\t\t\t\t}
\t\t\t\tend++;
\t\t\t\tif (!m)
%(B4b)s\t\t\t}
\t\t\tif (buf[i] != '\\t') {
\t\t\t\tif (j) {
\t\t\t\t\tint last = pick[j - 1];

\t\t\t\t\tm = (last == ' ' && buf[i] == ' ');
\t\t\t\t\tif (m)
%(B5)s\t\t\t\t}
\t\t\t\tpick[j++] = buf[i];
\t\t\t}
\t\t\tm = 1;
%(B3)s\t\t}
\t\t}
%(TAIL)s\t}

\treturn j;
}
"""


def render(c):
    tpos, tn, tm, tj, tend = TYPES[c['ty']]
    dup = c['dup']
    if dup == 'd0':                       # one `pos = 0` after the switch
        d = dict(B1='\t\t\tbreak;\n', B3='\t\t\tbreak;\n',
                 B4='\t\t\t\t\tbreak;\n', B4b='\t\t\t\t\tbreak;\n',
                 B5='\t\t\t\t\t\tbreak;\n', TAIL='\t\tpos = 0;\n')
    elif dup == 'd1':                     # duplicated on the two simple cases
        d = dict(B1='\t\t\tpos = 0;\n\t\t\tcontinue;\n', B3='\t\t\tbreak;\n',
                 B4='\t\t\t\t\tbreak;\n', B4b='\t\t\t\t\tbreak;\n',
                 B5='\t\t\t\t\t\tbreak;\n', TAIL='\t\tpos = 0;\n')
    else:                                 # d2: every break path carries it
        d = dict(B1='\t\t\tpos = 0;\n\t\t\tcontinue;\n',
                 B3='\t\t\tpos = 0;\n\t\t\tcontinue;\n',
                 B4='\t\t\t\t\tpos = 0;\n\t\t\t\t\tcontinue;\n',
                 B4b='\t\t\t\t\t{\n\t\t\t\t\t\tpos = 0;\n\t\t\t\t\t\tcontinue;\n\t\t\t\t\t}\n',
                 B5='\t\t\t\t\t\t{\n\t\t\t\t\t\t\tpos = 0;\n\t\t\t\t\t\t\tcontinue;\n\t\t\t\t\t\t}\n',
                 TAIL='')
    d.update(tpos=tpos, tn=tn, tm=tm, tj=tj, tend=tend,
             guard=GUARDS[c['guard']])
    return HEAD % d
