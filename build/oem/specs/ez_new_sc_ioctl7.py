# ez_new_sc_ioctl - stage 7: devices that add an RTL *reference* to `is_null`
# without adding an instruction.
#
# The requirement is exact (section 21): IRA colours in the order
# `push_allocnos_to_stack` unwinds `bucket_allocno_compare_func`'s sort, whose
# first key is ALLOCNO_FREQ, which at -Os is exactly 1000 x the number of RTL
# references.  `rq` has three and `is_null` two, so `rq` is coloured first and
# its weight-125 shuffle preference takes r2.  `is_null` must carry *more*
# references than `rq` - equality is not enough.
#
# Every ordinary-C spelling is folded away (VRP proves the range is [0,1]),
# so this sweep is over reference *devices*: empty inline asm in several
# constraint and placement forms, a local register variable, and the few
# remaining C shapes that might survive VRP.
UNIT = 'ez_sc'
FUNC = 'ez_new_sc_ioctl'

HEAD = """int ez_new_sc_ioctl(struct net_device *dev, struct ifreq *rq, int cmd)
{
\tstruct iwreq *wrq = (struct iwreq *)rq;
%s
\tif (is_null) {
\t\tprintk("ez_new_sc_ioctl input param is NULL!\\n");
\t\treturn -1;
\t}
%s
\treturn ez_set_new_sc(dev, is_null, &wrq->u.data);
}
"""

DECL = '\tint is_null = (dev == NULL || rq == NULL);\n'

SHAPES = [
    # ---- inline-asm reference devices, two references, before the guard ----
    ('asm2_pre_r', HEAD % (DECL +
        '\t__asm__ __volatile__("" :: "r"(is_null));\n'
        '\t__asm__ __volatile__("" :: "r"(is_null));\n', '')),
    ('asm2_post_r', HEAD % (DECL, '\n'
        '\t__asm__ __volatile__("" :: "r"(is_null));\n'
        '\t__asm__ __volatile__("" :: "r"(is_null));\n')),
    ('asm1x2_pre_r', HEAD % (DECL +
        '\t__asm__ __volatile__("" :: "r"(is_null), "r"(is_null));\n', '')),
    ('asm1x2_post_r', HEAD % (DECL, '\n'
        '\t__asm__ __volatile__("" :: "r"(is_null), "r"(is_null));\n')),
    ('asm2_pre_nv', HEAD % (DECL +
        '\t__asm__("" :: "r"(is_null));\n'
        '\t__asm__("" :: "r"(is_null));\n', '')),
    ('asm2_pre_g', HEAD % (DECL +
        '\t__asm__ __volatile__("" :: "g"(is_null));\n'
        '\t__asm__ __volatile__("" :: "g"(is_null));\n', '')),
    ('asm2_split', HEAD % (DECL +
        '\t__asm__ __volatile__("" :: "r"(is_null));\n', '\n'
        '\t__asm__ __volatile__("" :: "r"(is_null));\n')),
    ('asm1_pre_r', HEAD % (DECL +
        '\t__asm__ __volatile__("" :: "r"(is_null));\n', '')),
    ('asm3_pre_r', HEAD % (DECL +
        '\t__asm__ __volatile__("" :: "r"(is_null));\n'
        '\t__asm__ __volatile__("" :: "r"(is_null));\n'
        '\t__asm__ __volatile__("" :: "r"(is_null));\n', '')),
    ('asm_inout', HEAD % (DECL +
        '\t__asm__ __volatile__("" : "+r"(is_null));\n', '')),
    # ---- move rq's death instead: a reference to rq after the address add ----
    ('asm_rq_post', HEAD % (DECL, '\n'
        '\t__asm__ __volatile__("" :: "r"(rq));\n')),
    # ---- local register variables ----
    ('lreg_r3', """int ez_new_sc_ioctl(struct net_device *dev, struct ifreq *rq, int cmd)
{
\tstruct iwreq *wrq = (struct iwreq *)rq;
\tregister int is_null __asm__("r3") = (dev == NULL || rq == NULL);

\tif (is_null) {
\t\tprintk("ez_new_sc_ioctl input param is NULL!\\n");
\t\treturn -1;
\t}

\treturn ez_set_new_sc(dev, is_null, &wrq->u.data);
}
"""),
    # ---- C shapes that might survive VRP ----
    # the branch tests a *different* expression from the value that is passed
    ('dup_cond', """int ez_new_sc_ioctl(struct net_device *dev, struct ifreq *rq, int cmd)
{
\tstruct iwreq *wrq = (struct iwreq *)rq;
\tint is_null = (dev == NULL || rq == NULL);

\tif (dev == NULL || rq == NULL) {
\t\tprintk("ez_new_sc_ioctl input param is NULL!\\n");
\t\treturn -1;
\t}

\treturn ez_set_new_sc(dev, is_null, &wrq->u.data);
}
"""),
    ('dup_cond_and', """int ez_new_sc_ioctl(struct net_device *dev, struct ifreq *rq, int cmd)
{
\tstruct iwreq *wrq = (struct iwreq *)rq;
\tint is_null = (dev == NULL || rq == NULL);

\tif (!(dev != NULL && rq != NULL)) {
\t\tprintk("ez_new_sc_ioctl input param is NULL!\\n");
\t\treturn -1;
\t}

\treturn ez_set_new_sc(dev, is_null, &wrq->u.data);
}
"""),
    # a use in the cold arm: printk with the flag as an argument
    ('printk_flag', """int ez_new_sc_ioctl(struct net_device *dev, struct ifreq *rq, int cmd)
{
\tstruct iwreq *wrq = (struct iwreq *)rq;
\tint is_null = (dev == NULL || rq == NULL);

\tif (is_null) {
\t\tprintk("ez_new_sc_ioctl input param is NULL!\\n", is_null);
\t\treturn -1;
\t}

\treturn ez_set_new_sc(dev, is_null, &wrq->u.data);
}
"""),
]

AXES = {'shape': [(s[0], '%d' % i) for i, s in enumerate(SHAPES)]}


def render(c):
    return SHAPES[int(c['shape'])][1]
