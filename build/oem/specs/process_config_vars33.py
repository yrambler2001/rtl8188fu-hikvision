# process_config_vars - stage 33: the sweep that closed it.
#
# The residual was three separate GCC 6.5.0 decisions, each of which needed a
# reference or a block-liveness device rather than a respelling.  This spec is
# the record of the axes that produced the byte-identical variant, so the
# result is reproducible:
#
#   * `mtype'  - `m' must be `_Bool' for the shipped cstore to survive
#     (tree-ssa-dom.c's `record_edge_info' boolean special case folds any
#     `int' spelling's PHI argument to 1), and the skip guard must then keep
#     an explicit BIT_AND or the `andeq r3,r7,#1' is lost.
#   * `tail'   - the shared `pos = 0' must be one statement in a block that
#     survives `remove_forwarder_block', and the barrier must come *after* it
#     so cross-jumping cannot take the guard-true arm's copy as well.
#   * `endref' - `end' needs more RTL references than `j' to be coloured
#     first, and the guard temp needs more than `buf'.
#
# Every combination below compiles; the winner is
#   mtype=bool, skip=and, tail=use_after, endref=2, gref=in_def
# which is `n=0 d=+0 s=0' against the shipped bytes.
UNIT = 'ez_wifi_config'
FUNC = 'process_config_vars'

MTYPE = {'bool': '_Bool m = 0;', 'int': 'int m = 0;'}
SKIP = {
    'and': 'int skip = (end == 0) & (m & 1);',
    'ifelse': None,          # `if (end) skip = 0; else skip = m & 1;'
}
TAIL = {
    'use_after': 'pos = 0;\n\t\t__asm__ __volatile__("" : "+r"(pos));',
    'barrier_before': '__asm__ __volatile__("");\n\t\tpos = 0;',
    'plain': 'pos = 0;',
}
ENDREF = [0, 1, 2, 3]
GREF = ['none', 'in_def', 'in_skip', 'in_hash', 'after_def']

AXES = {
    'mtype': sorted(MTYPE),
    'tail': sorted(TAIL),
    'endref': [str(x) for x in ENDREF],
    'gref': GREF,
}

# The generator for this one is build/oem/lab/, kept out of the tree; the
# winning combination is what os_dep/linux/ez_wifi_config.c now contains, and
# it is commented there.  This file records the axes and the verdict.
def render(c):
    raise SystemExit('process_config_vars33: record only - the winning '
                     'combination is in os_dep/linux/ez_wifi_config.c')
