# Variant spec for ez_wifi_config.c:process_config_vars - stage 6, duplicated
# blocks.
#
# Duplicating the shared tail is what closed `ez_scan_device_ioctl_handle`:
# at `-Os` block layout is source order, so two copies that cross-jumping
# merges reach the same layout as one `goto` - by a different expression graph,
# and that is what the register allocator sees.
#
# The default case of this switch has two such joins.  The
# `if (buf[i] != '\t') { ... } m = 1;` tail is reached both from the "found the
# variable name" arm and from the fall-through of the other one, and the
# `pos = 0` after the switch is reached from every `break`.  These variants
# write each of them out per path instead.
import os

UNIT = 'ez_wifi_config'
FUNC = 'process_config_vars'


def _ax(name, default):
    v = os.environ.get('PCV6_' + name)
    return v.split(',') if v else default


AXES = {
    'ty': _ax('TY', ['t0', 't1', 't2']),
    'tail': _ax('TAIL', ['u0', 'u1', 'u2']),
    'bot': _ax('BOT', ['b0', 'b1']),
}

TYPES = {
    't0': ('int', 'int', 'int', 'int', 'int'),
    't1': ('int', 's32', 'int', 'int', 'int'),
    't2': ('int', 's32', 's32', 'int', 'int'),
}

# the block both arms of the default case fall into
TAIL_BLOCK = """\t\t\tif (buf[i] != '\\t') {
\t\t\t\tif (j) {
\t\t\t\t\tint last = pick[j - 1];

\t\t\t\t\tm = (last == ' ' && buf[i] == ' ');
\t\t\t\t\tif (m)
%(BRK)s\t\t\t\t}
\t\t\t\tpick[j++] = buf[i];
\t\t\t}
\t\t\tm = 1;
%(BRK)s"""


def render(c):
    tpos, tn, tm, tj, tend = TYPES[c['ty']]
    brk = ('\t\t\tpos = 0;\n\t\t\tcontinue;\n' if c['bot'] == 'b1'
           else '\t\t\tbreak;\n')
    brk_in = ('\t\t\t\t\t\t{ pos = 0; continue; }\n' if c['bot'] == 'b1'
              else '\t\t\t\t\t\tbreak;\n')
    brk_sk = ('\t\t\t\t\tpos = 0;\n\t\t\t\t\tcontinue;\n' if c['bot'] == 'b1'
              else '\t\t\t\t\tbreak;\n')
    brk_nm = ('\t\t\t\t\t{ pos = 0; continue; }\n' if c['bot'] == 'b1'
              else '\t\t\t\t\tbreak;\n')
    tailblk = TAIL_BLOCK.replace('%(BRK)s', '@B@').replace('@B@\t\t\t\t}',
                                                           brk_in + '\t\t\t\t}')
    tailblk = tailblk.replace('@B@', brk)
    bot = '' if c['bot'] == 'b1' else '\t\tpos = 0;\n'

    if c['tail'] == 'u0':               # shared tail (baseline)
        default = ("""\t\tdefault: {
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
""" + brk_sk + """\t\t\t\t}
\t\t\t\tend++;
\t\t\t\tif (!m)
""" + brk_nm + """\t\t\t}
""" + tailblk + "\t\t}\n")
    elif c['tail'] == 'u1':             # tail duplicated into both arms
        default = ("""\t\tdefault: {
\t\t\tsize_t vlen = strlen(var);
\t\t\tint cmp = memcmp(&buf[i], var, vlen);

\t\t\tif (!end && !cmp) {
\t\t\t\tend = vlen;
\t\t\t\tj = 0;
\t\t\t\ti += end;
""" + tailblk.replace('\t\t\t', '\t\t\t\t').replace('\t\t\t\t\t\t\t', '\t\t\t\t\t\t') + """\t\t\t}
\t\t\t{
\t\t\t\tint skip;

\t\t\t\tif (end)
\t\t\t\t\tskip = 0;
\t\t\t\telse
\t\t\t\t\tskip = m & 1;
\t\t\t\tif (skip) {
\t\t\t\t\tend = 0;
\t\t\t\t\tm = 0;
""" + brk_sk + """\t\t\t\t}
\t\t\t\tend++;
\t\t\t\tif (!m)
""" + brk_nm + """\t\t\t}
""" + tailblk + "\t\t}\n")
    else:                               # u2: early continue instead of else
        default = ("""\t\tdefault: {
\t\t\tsize_t vlen = strlen(var);
\t\t\tint cmp = memcmp(&buf[i], var, vlen);
\t\t\tint skip;

\t\t\tif (!end && !cmp) {
\t\t\t\tend = vlen;
\t\t\t\tj = 0;
\t\t\t\ti += end;
\t\t\t\tgoto emit;
\t\t\t}
\t\t\tif (end)
\t\t\t\tskip = 0;
\t\t\telse
\t\t\t\tskip = m & 1;
\t\t\tif (skip) {
\t\t\t\tend = 0;
\t\t\t\tm = 0;
""" + brk_sk.replace('\t\t\t\t\t', '\t\t\t\t') + """\t\t\t}
\t\t\tend++;
\t\t\tif (!m)
""" + brk_nm.replace('\t\t\t\t\t', '\t\t\t\t') + """emit:
""" + tailblk + "\t\t}\n")

    return """int process_config_vars(char *buf, u32 len, char *pick, const char *var)
{
\tu32 i;
\t%s pos = 0;
\t%s n = 0;
\t%s m = 0;
\t%s j = 0;
\t%s end = 0;

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

\t\tswitch (buf[i]) {
\t\tcase '#':
\t\t\tn |= pos;
\t\t\tpos = 1;
\t\t\tcontinue;
\t\tcase '\\\\':
\t\t\tn = 1;
""" % (tpos, tn, tm, tj, tend) + brk + """\t\tcase '\\n':
\t\t\tend = pos | n;
\t\t\tn |= pos;
""" + brk + default + "\t\t}\n" + bot + """\t}

\treturn j;
}
"""
