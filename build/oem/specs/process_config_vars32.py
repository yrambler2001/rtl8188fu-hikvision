# process_config_vars - stage 32: the block-layout axis.
#
# Section 17 established that giving the guard a type `gimple_can_coalesce_p`
# refuses stops `uncprop`, and that the whole register cascade then matches the
# shipped code.  What is left is *layout*, and the mechanism is now read out of
# GCC 6.5.0's `reorder_basic_blocks_simple` (bb-reorder.c:2302):
#
#   * at -Os it does not sort; it walks the block chain, collecting for each
#     block its single successor edge, or (fallthrough, taken) for a condjump;
#   * it then makes each edge a fallthrough if both ends are still free chain
#     endpoints, first come first served;
#   * the chains are emitted in the order of their *start* blocks.
#
# So the loop tail (`i++`) is given to the earliest single-successor
# predecessor of it in block-chain order.  In the shipped build that is the
# shared `pos = 0` block; in the int-cast build it is the guard-true arm, which
# sits in the chain that starts at the loop body and therefore lands early.
#
# These axes are the ones that can move which block that is: the shape of the
# guard-true arm (whether it ends in a block at all), the shape of the arms
# whose `pos = 0` copy needs a *new* edge block, and the declaration order,
# which decides the order of the copies inside each edge block and therefore
# what cross-jumping can merge.
UNIT = 'ez_wifi_config'
FUNC = 'process_config_vars'

GUARD = {
    'plain': '(pos | n) | (pos & n)',
    'icast': '((int)(pos | n)) | ((int)(pos & n))',
}

# guard-true arm: the '\n' handling inside `if (pos|n)`
GARM = {
    # both arms assign pos from n (the shipped cascade)
    'ifelse': """\t\t\tif (buf[i] == '\\n') {
\t\t\t\tif (n) {
\t\t\t\t\tn = 0;
\t\t\t\t\tpos = n;
\t\t\t\t} else {
\t\t\t\t\tpos = n;
\t\t\t\t\tend = 0;
\t\t\t\t}
\t\t\t}
\t\t\tcontinue;""",
    # the same, arms swapped
    'swapped': """\t\t\tif (buf[i] == '\\n') {
\t\t\t\tif (!n) {
\t\t\t\t\tpos = n;
\t\t\t\t\tend = 0;
\t\t\t\t} else {
\t\t\t\t\tn = 0;
\t\t\t\t\tpos = n;
\t\t\t\t}
\t\t\t}
\t\t\tcontinue;""",
    # early continue, so the arm is not nested
    'early': """\t\t\tif (buf[i] != '\\n')
\t\t\t\tcontinue;
\t\t\tif (n) {
\t\t\t\tn = 0;
\t\t\t\tpos = n;
\t\t\t} else {
\t\t\t\tpos = n;
\t\t\t\tend = 0;
\t\t\t}
\t\t\tcontinue;""",
    # constants instead of the n copies
    'zero': """\t\t\tif (buf[i] == '\\n') {
\t\t\t\tif (n) {
\t\t\t\t\tn = 0;
\t\t\t\t\tpos = 0;
\t\t\t\t} else {
\t\t\t\t\tpos = 0;
\t\t\t\t\tend = 0;
\t\t\t\t}
\t\t\t}
\t\t\tcontinue;""",
}

# the `!m` arm inside the default case
NOM = {
    'block': """\t\t\t\tend++;
\t\t\t\tif (!m) {
\t\t\t\t\tpos = 0;
\t\t\t\t\tcontinue;
\t\t\t\t}""",
    'inv': """\t\t\t\tend++;
\t\t\t\tif (m == 0) {
\t\t\t\t\tpos = 0;
\t\t\t\t\tcontinue;
\t\t\t\t}""",
    'else': """\t\t\t\tend++;
\t\t\t\tif (m) {
\t\t\t\t} else {
\t\t\t\t\tpos = 0;
\t\t\t\t\tcontinue;
\t\t\t\t}""",
}

# the trailing space test
SPC = {
    'plain': """\t\t\tif (j) {
\t\t\t\tint last = pick[j - 1];

\t\t\t\tm = (last == ' ' && buf[i] == ' ');
\t\t\t\tif (m) {
\t\t\t\t\tpos = 0;
\t\t\t\t\tcontinue;
\t\t\t\t}
\t\t\t}""",
    'nolast': """\t\t\tif (j) {
\t\t\t\tm = (pick[j - 1] == ' ' && buf[i] == ' ');
\t\t\t\tif (m) {
\t\t\t\t\tpos = 0;
\t\t\t\t\tcontinue;
\t\t\t\t}
\t\t\t}""",
}

DECLS = {
    'pnmej': ['unsigned int pos = 0;', 'u32 n = 0;', 'int m = 0;', 'int end = 0;', 'int j = 0;'],
    'npmej': ['u32 n = 0;', 'unsigned int pos = 0;', 'int m = 0;', 'int end = 0;', 'int j = 0;'],
    'pnemj': ['unsigned int pos = 0;', 'u32 n = 0;', 'int end = 0;', 'int m = 0;', 'int j = 0;'],
    'jpnme': ['int j = 0;', 'unsigned int pos = 0;', 'u32 n = 0;', 'int m = 0;', 'int end = 0;'],
    'pnmje': ['unsigned int pos = 0;', 'u32 n = 0;', 'int m = 0;', 'int j = 0;', 'int end = 0;'],
    'epnmj': ['int end = 0;', 'unsigned int pos = 0;', 'u32 n = 0;', 'int m = 0;', 'int j = 0;'],
    'mpnej': ['int m = 0;', 'unsigned int pos = 0;', 'u32 n = 0;', 'int end = 0;', 'int j = 0;'],
    'pmnej': ['unsigned int pos = 0;', 'int m = 0;', 'u32 n = 0;', 'int end = 0;', 'int j = 0;'],
}

TEMPLATE = """int process_config_vars(char *buf, u32 len, char *pick, const char *var)
{
\tu32 i;
%(decls)s

\tfor (i = 0; i < len; i++) {
\t\tif (buf[i] == '\\r')
\t\t\tcontinue;

\t\tif (%(guard)s) {
%(garm)s
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
\t\t\tend = 0;
\t\t\tn = 0;
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
%(nom)s
\t\t\t}
\t\t\tif (buf[i] != '\\t') {
%(spc)s
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

AXES = {
    'guard': sorted(GUARD),
    'garm': sorted(GARM),
    'nom': sorted(NOM),
    'spc': sorted(SPC),
    'decl': sorted(DECLS),
}


def render(c):
    return TEMPLATE % {
        'decls': '\n'.join('\t' + d for d in DECLS[c['decl']]),
        'guard': GUARD[c['guard']],
        'garm': GARM[c['garm']],
        'nom': NOM[c['nom']],
        'spc': SPC[c['spc']],
    }
