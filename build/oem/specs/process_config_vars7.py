# Variant spec for ez_wifi_config.c:process_config_vars - stage 7, switch vs
# if-chain.
#
# GCC compiles this four-case switch as an if-chain anyway (`cmp r1, #0x23 /
# beq`, `cmp r1, #0x5c / beq`, ...), so the shipped code does not say which the
# source was - but the two are not the same to the middle end.  `uncprop` has a
# dedicated path for switch edges (it records `index == case_value` on every
# single-valued one, which is what fixed `ez_set_new_sc`), and a `switch`
# statement survives as a GIMPLE_SWITCH until switch conversion while an
# if-chain is COND_EXPRs from the start.
#
# Crossed with the type family from stage 2 and the guard spellings, because
# the residual is that `n` is not live across the two calls here and is in the
# shipped build.
import os

UNIT = 'ez_wifi_config'
FUNC = 'process_config_vars'


def _ax(name, default):
    v = os.environ.get('PCV7_' + name)
    return v.split(',') if v else default


AXES = {
    'ty': _ax('TY', ['t0', 't1', 't2']),
    'sel': _ax('SEL', ['w0', 'w1', 'w2', 'w3']),
    'guard': _ax('GUARD', ['g0', 'g1']),
    'bot': _ax('BOT', ['b0', 'b1']),
}

TYPES = {
    't0': ('int', 'int', 'int', 'int', 'int'),
    't1': ('int', 's32', 'int', 'int', 'int'),
    't2': ('int', 's32', 's32', 'int', 'int'),
}

GUARDS = {'g0': 'n || pos', 'g1': 'pos || n'}

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
%(BRK2)s\t\t\t\t}
\t\t\t\tend++;
\t\t\t\tif (!m)
%(BRK3)s\t\t\t}
\t\t\tif (buf[i] != '\\t') {
\t\t\t\tif (j) {
\t\t\t\t\tint last = pick[j - 1];

\t\t\t\t\tm = (last == ' ' && buf[i] == ' ');
\t\t\t\t\tif (m)
%(BRK4)s\t\t\t\t}
\t\t\t\tpick[j++] = buf[i];
\t\t\t}
\t\t\tm = 1;
%(BRK1)s"""


def render(c):
    tpos, tn, tm, tj, tend = TYPES[c['ty']]
    b1 = c['bot'] == 'b1'
    if b1:
        BRK1 = '\t\t\tpos = 0;\n\t\t\tcontinue;\n'
        BRK2 = '\t\t\t\t\tpos = 0;\n\t\t\t\t\tcontinue;\n'
        BRK3 = '\t\t\t\t\t{ pos = 0; continue; }\n'
        BRK4 = '\t\t\t\t\t\t{ pos = 0; continue; }\n'
        BOT = ''
    else:
        BRK1 = '\t\t\tbreak;\n'
        BRK2 = '\t\t\t\t\tbreak;\n'
        BRK3 = '\t\t\t\t\tbreak;\n'
        BRK4 = '\t\t\t\t\t\tbreak;\n'
        BOT = '\t\tpos = 0;\n'
    default = DEFAULT % dict(BRK1=BRK1, BRK2=BRK2, BRK3=BRK3, BRK4=BRK4)

    sel = c['sel']
    if sel in ('w0', 'w1'):             # switch
        order = ("\t\tcase '#':\n\t\t\tn |= pos;\n\t\t\tpos = 1;\n\t\t\tcontinue;\n"
                 "\t\tcase '\\\\':\n\t\t\tn = 1;\n" + BRK1 +
                 "\t\tcase '\\n':\n\t\t\tend = pos | n;\n\t\t\tn |= pos;\n" + BRK1)
        if sel == 'w1':
            order = ("\t\tcase '\\\\':\n\t\t\tn = 1;\n" + BRK1 +
                     "\t\tcase '\\n':\n\t\t\tend = pos | n;\n\t\t\tn |= pos;\n" + BRK1 +
                     "\t\tcase '#':\n\t\t\tn |= pos;\n\t\t\tpos = 1;\n\t\t\tcontinue;\n")
        body = ('\t\tswitch (buf[i]) {\n' + order +
                '\t\tdefault: {\n' + default + '\t\t}\n\t\t}\n')
    else:                               # if-chain
        cont = '\t\t\tcontinue;\n'
        blocks = [
            ("\t\tif (buf[i] == '#') {\n\t\t\tn |= pos;\n\t\t\tpos = 1;\n" + cont + '\t\t}\n'),
            ("\t\telse if (buf[i] == '\\\\') {\n\t\t\tn = 1;\n" +
             (BRK1 if b1 else '\t\t\tpos = 0;\n' + cont) + '\t\t}\n'),
            ("\t\telse if (buf[i] == '\\n') {\n\t\t\tend = pos | n;\n\t\t\tn |= pos;\n" +
             (BRK1 if b1 else '\t\t\tpos = 0;\n' + cont) + '\t\t}\n'),
        ]
        tail = ('\t\telse {\n' +
                default.replace('\t\t\tbreak;\n', '\t\t\tpos = 0;\n\t\t\tcontinue;\n')
                       .replace('\t\t\t\t\tbreak;\n', '\t\t\t\t\tpos = 0;\n\t\t\t\t\tcontinue;\n')
                       .replace('\t\t\t\t\t\tbreak;\n',
                                '\t\t\t\t\t\t{ pos = 0; continue; }\n') +
                '\t\t}\n')
        if sel == 'w3':                 # no else, early continues
            blocks = [b.replace('\t\telse if', '\t\tif') for b in blocks]
            tail = tail.replace('\t\telse {\n', '\t\t{\n')
        body = ''.join(blocks) + tail
        return TEMPLATE % dict(tpos=tpos, tn=tn, tm=tm, tj=tj, tend=tend,
                               guard=GUARDS[c['guard']], body=body, bot='')
    return TEMPLATE % dict(tpos=tpos, tn=tn, tm=tm, tj=tj, tend=tend,
                           guard=GUARDS[c['guard']], body=body, bot=BOT)


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

%(body)s%(bot)s\t}

\treturn j;
}
"""
