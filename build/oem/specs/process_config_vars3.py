# Variant spec for ez_wifi_config.c:process_config_vars - stage 3, structure.
#
# What the shipped register allocation needs is one more value live across the
# strlen/memcmp calls.  Reading the shipped code off the disassembly says
# exactly which: `n` is in r6, a callee-saved register, and the default case
# never writes it - its value simply survives to the next iteration.  Ours
# rematerialises `n = 0` after the calls instead (`mov r2, #0`), so `n` never
# crosses them, IRA has eleven call-crossing allocnos instead of twelve, it
# spills two instead of three, `pick` keeps a register instead of the stack,
# and `pos` has to be split across two - which is the two extra instructions.
#
# Ours can rematerialise because VRP proves `n == 0` at the switch, from the
# loop guard.  GCC 6's register_edge_assert_for_1 only propagates
# `(a | b) == 0` down to `a == 0` and `b == 0` when each operand
# `has_single_use`, so how many times `n` and `pos` are read around the guard
# decides whether that assertion is made at all.  These axes vary exactly
# that: the guard's spelling, the inner test, and how each switch case reads
# the two flags - crossed with the type family stage 2 found.
import os

UNIT = 'ez_wifi_config'
FUNC = 'process_config_vars'


def _ax(name, default):
    v = os.environ.get('PCV3_' + name)
    return v.split(',') if v else default


AXES = {
    'ty': _ax('TY', ['t0', 't1', 't2', 't3', 't4']),
    'guard': _ax('GUARD', ['g0', 'g1', 'g2', 'g3', 'g4', 'g5', 'g6']),
    'inner': _ax('INNER', ['i0', 'i1', 'i2']),
    'hash': _ax('HASH', ['h0', 'h1', 'h2', 'h3']),
    'nl': _ax('NL', ['n0', 'n1', 'n2', 'n3']),
    'bot': _ax('BOT', ['b0', 'b1']),
}

# (pos, n, m, j, end); a typedef of `int` is a distinct tree node to uncprop
TYPES = {
    't0': ('int', 'int', 'int', 'int', 'int'),
    't1': ('int', 's32', 'int', 'int', 'int'),
    't2': ('int', 's32', 's32', 'int', 'int'),
    't3': ('int', 'long', 'int', 'int', 'int'),
    't4': ('int', 's32', 's32', 's32', 's32'),
    't5': ('s32', 'int', 'int', 'int', 'int'),
    't6': ('int', 'int', 's32', 's32', 's32'),
}

GUARDS = {
    'g0': "\t\tif (n || pos) {\n",
    'g1': "\t\tif (pos || n) {\n",
    'g2': "\t\tif (n | pos) {\n",
    'g3': "\t\tif (pos | n) {\n",
    'g4': "\t\tif ((n | pos) != 0) {\n",
    'g5': "\t\tif (n != 0 || pos != 0) {\n",
    'g6': "\t\tif (!!n | !!pos) {\n",
}

INNER = {
    'i0': ("\t\t\t\tif (n) {\n"
           "\t\t\t\t\tn = 0;\n\t\t\t\t\tpos = 0;\n"
           "\t\t\t\t} else {\n"
           "\t\t\t\t\tpos = 0;\n\t\t\t\t\tend = 0;\n"
           "\t\t\t\t}\n"),
    'i1': ("\t\t\t\tif (!n) {\n"
           "\t\t\t\t\tpos = 0;\n\t\t\t\t\tend = 0;\n"
           "\t\t\t\t} else {\n"
           "\t\t\t\t\tn = 0;\n\t\t\t\t\tpos = 0;\n"
           "\t\t\t\t}\n"),
    'i2': ("\t\t\t\tpos = 0;\n"
           "\t\t\t\tif (n)\n\t\t\t\t\tn = 0;\n"
           "\t\t\t\telse\n\t\t\t\t\tend = 0;\n"),
}

HASH = {
    'h0': "\t\t\tn |= pos;\n\t\t\tpos = 1;\n\t\t\tcontinue;\n",
    'h1': "\t\t\tn = n | pos;\n\t\t\tpos = 1;\n\t\t\tcontinue;\n",
    'h2': "\t\t\tn = pos | n;\n\t\t\tpos = 1;\n\t\t\tcontinue;\n",
    'h3': "\t\t\tn = pos;\n\t\t\tpos = 1;\n\t\t\tcontinue;\n",
}

NL = {
    'n0': "\t\t\tend = pos | n;\n\t\t\tn |= pos;\n\t\t\tbreak;\n",
    'n1': "\t\t\tend = n | pos;\n\t\t\tn |= pos;\n\t\t\tbreak;\n",
    'n2': "\t\t\tn |= pos;\n\t\t\tend = n;\n\t\t\tbreak;\n",
    'n3': "\t\t\tend = pos | n;\n\t\t\tn = end;\n\t\t\tbreak;\n",
}

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

%(guard)s\t\t\tif (buf[i] == '\\n') {
%(inner)s\t\t\t}
\t\t\tcontinue;
\t\t}

\t\tswitch (buf[i]) {
\t\tcase '#':
%(hash)s\t\tcase '\\\\':
\t\t\tn = 1;
\t\t\tbreak;
\t\tcase '\\n':
%(nl)s\t\tdefault: {
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
\t\t\t\t\tbreak;
\t\t\t\t}
\t\t\t\tend++;
\t\t\t\tif (!m)
\t\t\t\t\tbreak;
\t\t\t}
\t\t\tif (buf[i] != '\\t') {
\t\t\t\tif (j) {
\t\t\t\t\tint last = pick[j - 1];

\t\t\t\t\tm = (last == ' ' && buf[i] == ' ');
\t\t\t\t\tif (m)
\t\t\t\t\t\tbreak;
\t\t\t\t}
\t\t\t\tpick[j++] = buf[i];
\t\t\t}
\t\t\tm = 1;
\t\t\tbreak;
\t\t}
\t\t}
%(bot)s\t}

\treturn j;
}
"""

BOT = {
    'b0': "\t\tpos = 0;\n",
    'b1': "\t\tif (pos)\n\t\t\tpos = 0;\n",
}


def render(c):
    tpos, tn, tm, tj, tend = TYPES[c['ty']]
    return TEMPLATE % {
        'tpos': tpos, 'tn': tn, 'tm': tm, 'tj': tj, 'tend': tend,
        'guard': GUARDS[c['guard']], 'inner': INNER[c['inner']],
        'hash': HASH[c['hash']], 'nl': NL[c['nl']], 'bot': BOT[c['bot']],
    }
