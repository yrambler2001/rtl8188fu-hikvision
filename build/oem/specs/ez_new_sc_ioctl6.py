# ez_new_sc_ioctl - stage 6: shapes that change the CFG, not just the spelling.
#
# The residual is one IRA decision: `rq` and `is_null` both want r1 at weight
# 2000 and cancel in the conflict costs, so `rq`'s weight-125 preference for
# r2 - created by `process_reg_shuffles` because `rq` *dies* in
# `add r2, rq, #16`, whose output is the hard argument register - decides, and
# `rq` moves to r2.  The shipped build leaves `rq` in r1 and puts `is_null` in
# r3.  So the axes here are the ones that can change which registers those two
# allocnos want, or the block the add lands in: guard-clause versus if/else,
# where the address is formed, and whether the flag is recomputed.
UNIT = 'ez_sc'
FUNC = 'ez_new_sc_ioctl'

SHAPES = [
    # guard clause, flag reused as the second argument (the current shape)
    ('guard', """int ez_new_sc_ioctl(struct net_device *dev, struct ifreq *rq, int cmd)
{
\tstruct iwreq *wrq = (struct iwreq *)rq;
\tint is_null = (dev == NULL || rq == NULL);

\tif (is_null) {
\t\tprintk("ez_new_sc_ioctl input param is NULL!\\n");
\t\treturn -1;
\t}

\treturn ez_set_new_sc(dev, is_null, &wrq->u.data);
}
"""),
    ('ifelse', """int ez_new_sc_ioctl(struct net_device *dev, struct ifreq *rq, int cmd)
{
\tstruct iwreq *wrq = (struct iwreq *)rq;
\tint is_null = (dev == NULL || rq == NULL);

\tif (!is_null)
\t\treturn ez_set_new_sc(dev, is_null, &wrq->u.data);

\tprintk("ez_new_sc_ioctl input param is NULL!\\n");
\treturn -1;
}
"""),
    ('ret', """int ez_new_sc_ioctl(struct net_device *dev, struct ifreq *rq, int cmd)
{
\tstruct iwreq *wrq = (struct iwreq *)rq;
\tint is_null = (dev == NULL || rq == NULL);
\tint ret;

\tif (is_null) {
\t\tprintk("ez_new_sc_ioctl input param is NULL!\\n");
\t\tret = -1;
\t} else {
\t\tret = ez_set_new_sc(dev, is_null, &wrq->u.data);
\t}

\treturn ret;
}
"""),
    ('goto', """int ez_new_sc_ioctl(struct net_device *dev, struct ifreq *rq, int cmd)
{
\tstruct iwreq *wrq = (struct iwreq *)rq;
\tint is_null = (dev == NULL || rq == NULL);

\tif (is_null)
\t\tgoto bad;

\treturn ez_set_new_sc(dev, is_null, &wrq->u.data);

bad:
\tprintk("ez_new_sc_ioctl input param is NULL!\\n");
\treturn -1;
}
"""),
    ('pt_late', """int ez_new_sc_ioctl(struct net_device *dev, struct ifreq *rq, int cmd)
{
\tstruct iwreq *wrq = (struct iwreq *)rq;
\tint is_null = (dev == NULL || rq == NULL);
\tstruct iw_point *pt;

\tif (is_null) {
\t\tprintk("ez_new_sc_ioctl input param is NULL!\\n");
\t\treturn -1;
\t}

\tpt = &wrq->u.data;
\treturn ez_set_new_sc(dev, is_null, pt);
}
"""),
    ('pt_early', """int ez_new_sc_ioctl(struct net_device *dev, struct ifreq *rq, int cmd)
{
\tstruct iwreq *wrq = (struct iwreq *)rq;
\tstruct iw_point *pt = &wrq->u.data;
\tint is_null = (dev == NULL || rq == NULL);

\tif (is_null) {
\t\tprintk("ez_new_sc_ioctl input param is NULL!\\n");
\t\treturn -1;
\t}

\treturn ez_set_new_sc(dev, is_null, pt);
}
"""),
    ('zero', """int ez_new_sc_ioctl(struct net_device *dev, struct ifreq *rq, int cmd)
{
\tstruct iwreq *wrq = (struct iwreq *)rq;
\tint is_null = (dev == NULL || rq == NULL);

\tif (is_null) {
\t\tprintk("ez_new_sc_ioctl input param is NULL!\\n");
\t\treturn -1;
\t}

\treturn ez_set_new_sc(dev, 0, &wrq->u.data);
}
"""),
    ('recheck', """int ez_new_sc_ioctl(struct net_device *dev, struct ifreq *rq, int cmd)
{
\tstruct iwreq *wrq = (struct iwreq *)rq;
\tint is_null = (dev == NULL || rq == NULL);

\tif (is_null != 0) {
\t\tprintk("ez_new_sc_ioctl input param is NULL!\\n");
\t\treturn -1;
\t}

\treturn ez_set_new_sc(dev, is_null, &wrq->u.data);
}
"""),
    ('static_helper', """static int ez_new_sc_null(struct net_device *dev, struct ifreq *rq)
{
\treturn dev == NULL || rq == NULL;
}

int ez_new_sc_ioctl(struct net_device *dev, struct ifreq *rq, int cmd)
{
\tstruct iwreq *wrq = (struct iwreq *)rq;
\tint is_null = ez_new_sc_null(dev, rq);

\tif (is_null) {
\t\tprintk("ez_new_sc_ioctl input param is NULL!\\n");
\t\treturn -1;
\t}

\treturn ez_set_new_sc(dev, is_null, &wrq->u.data);
}
"""),
    ('wrq_null', """int ez_new_sc_ioctl(struct net_device *dev, struct ifreq *rq, int cmd)
{
\tstruct iwreq *wrq = (struct iwreq *)rq;
\tint is_null = (dev == NULL || wrq == NULL);

\tif (is_null) {
\t\tprintk("ez_new_sc_ioctl input param is NULL!\\n");
\t\treturn -1;
\t}

\treturn ez_set_new_sc(dev, is_null, &wrq->u.data);
}
"""),
]

AXES = {'shape': [(s[0], '%d' % i) for i, s in enumerate(SHAPES)]}


def render(c):
    return SHAPES[int(c['shape'])][1]
