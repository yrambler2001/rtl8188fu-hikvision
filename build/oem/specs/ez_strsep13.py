# ez_strsep - stage 13: the delimiter arm, and the four ways to stop TER.
#
# The residual was the last four words of the delimiter path.  GCC 6.5.0's
# tree-ssa-ter.c sinks `q + 1' to its single use - past `*q = 0' - and
# auto-inc-dec.c's backwards scan then folds the pair into `strb rX, [q], #1',
# which leaves the rest-pointer in q's own register so cross-jumping cannot
# merge this `*stringp' store with the end-of-string one.
#
# `ssa_is_replaceable_p' + `ter_is_replaceable_p' + `find_replaceable_in_bb'
# leave exactly four source-level levers, and this spec is all of them:
#
#   use2      a second immediate use of the value      (every spelling folds)
#   volatile  volatile operands on the *use* statement (works - the qualifier
#             does not survive to the output, because cross-jumping merges the
#             store with the non-volatile one)
#   phi/bb    a use that is a PHI, or in another block (works, but only with a
#             label in the middle of the loop body; a plain `goto out' after
#             the loop puts the shared epilogue at the end of the function)
#
# Section 18 of FINDINGS-oem-catalogue.md has the full derivation, including
# the -fdbg-cnt=auto_inc_dec:2 experiment that separates the two passes.
UNIT = 'ez_wifi_config'
FUNC = 'ez_strsep'

# how the rest-pointer is computed and stored in the delimiter arm
DELIM = [
    # the shipped shape: computed first, stored through a TER-opaque lvalue
    ('vol', "\t\t\tr = q + 1;\n\t\t\t*q = '\\0';\n"
            "\t\t\t*(char * volatile *)stringp = r;\n"),
    # baseline: TER sinks the add and auto-inc-dec folds it
    ('plain', "\t\t\t*q = '\\0';\n\t\t\t*stringp = q + 1;\n"),
    # temporary first, but a single non-volatile use - TER sinks it anyway
    ('tmp', "\t\t\tr = q + 1;\n\t\t\t*q = '\\0';\n\t\t\t*stringp = r;\n"),
    # second use via the NUL store's address - forwprop folds it back to *q
    ('back', "\t\t\tr = q + 1;\n\t\t\tr[-1] = '\\0';\n\t\t\t*stringp = r;\n"),
    # second use via a duplicate store - DSE removes one of them
    ('dbl', "\t\t\tr = q + 1;\n\t\t\t*stringp = r;\n\t\t\t*q = '\\0';\n"
            "\t\t\t*stringp = r;\n"),
    # store first - four instructions become five
    ('spfirst', "\t\t\t*stringp = q + 1;\n\t\t\t*q = '\\0';\n"),
]

# how the escape arm is written: two ifs (duplicated source, section 19) or one
ESC = [
    ('two', "\t\tif (c == esc) {\n"
            "\t\t\tif (q[1] == esc) {\n\t\t\t\tmemmove(q, q + 1, strlen(q));\n"
            "\t\t\t\tp = q + 1;\n\t\t\t\tcontinue;\n\t\t\t}\n"
            "\t\t\tif (q[1] == delim) {\n\t\t\t\tmemmove(q, q + 1, strlen(q));\n"
            "\t\t\t\tp = q + 1;\n\t\t\t\tcontinue;\n\t\t\t}\n\t\t}\n"),
    ('one', "\t\tif (c == esc && (q[1] == esc || q[1] == delim)) {\n"
            "\t\t\tmemmove(q, q + 1, strlen(q));\n"
            "\t\t\tp = q + 1;\n\t\t\tcontinue;\n\t\t}\n"),
]

AXES = {
    'delim': [(n, str(i)) for i, (n, _) in enumerate(DELIM)],
    'esc': [(n, str(i)) for i, (n, _) in enumerate(ESC)],
}

TEMPLATE = """char *ez_strsep(char **stringp, char delim, char esc)
{
\tchar *s = *stringp;
\tchar *p, *q, *r;
\tchar c;

\tif (s == NULL)
\t\treturn s;

\tif (*s == '\\0')
\t\treturn NULL;

\tp = s;
\tfor (;;) {
\t\tq = p;
\t\tc = *q;
\t\tif (c == '\\0') {
\t\t\t*stringp = NULL;
\t\t\treturn s;
\t\t}
%(esc)s\t\tif (c == delim) {
%(delim)s\t\t\treturn s;
\t\t}
\t\tp = q + 1;
\t}
}
"""


def render(c):
    return TEMPLATE % {'esc': ESC[int(c['esc'])][1],
                       'delim': DELIM[int(c['delim'])][1]}
