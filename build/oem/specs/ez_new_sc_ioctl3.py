# Variant spec for ez_sc.c:ez_new_sc_ioctl - stage 3, duplicated blocks.
#
# The rule that closed `ez_scan_device_ioctl_handle` and `ez_strsep`: at `-Os`
# a block the shipped code reaches from two places is evidence of duplicated
# source that cross-jumping merged, not of a `goto`.  This function has one
# error block reached from a single test - so the question is whether the
# vendor wrote *two* tests, each with its own copy of the printk and the
# `return -1`, and cross-jumping merged them.
#
# That also changes the allocno graph, which is where the residual is: `rq` and
# `is_null` both prefer r1 at weight 2000 and cancel, and `rq`'s uncontested
# weight-125 preference for r2 - from the `add r2, rq, #16` that sets up the
# third argument - decides.  Two tests means two conditions, and a different
# CFG for IRA to price.
UNIT = 'ez_sc'
FUNC = 'ez_new_sc_ioctl'

AXES = {
    'shape': ['s0', 's1', 's2', 's3', 's4', 's5', 's6', 's7'],
    'ty': ['int', 'u32', 's32', 'long'],
}

ERR = ('\t\tprintk("ez_new_sc_ioctl input param is NULL!\\n");\n'
       '\t\treturn -1;\n')
ERR1 = ('\t\t\tprintk("ez_new_sc_ioctl input param is NULL!\\n");\n'
        '\t\t\treturn -1;\n')


def render(c):
    s, ty = c['shape'], c['ty']
    head = 'int ez_new_sc_ioctl(struct net_device *dev, struct ifreq *rq, int cmd)\n{\n'
    if s == 's0':                       # baseline
        b = ('\tstruct iwreq *wrq = (struct iwreq *)rq;\n'
             '\t%s is_null = (dev == NULL || rq == NULL);\n\n' % ty +
             '\tif (is_null) {\n' + ERR + '\t}\n\n'
             '\treturn ez_set_new_sc(dev, is_null, &wrq->u.data);\n')
    elif s == 's1':                     # two tests, each with its own copy
        b = ('\tstruct iwreq *wrq = (struct iwreq *)rq;\n'
             '\t%s is_null = (dev == NULL || rq == NULL);\n\n' % ty +
             '\tif (dev == NULL) {\n' + ERR + '\t}\n'
             '\tif (rq == NULL) {\n' + ERR + '\t}\n\n'
             '\treturn ez_set_new_sc(dev, is_null, &wrq->u.data);\n')
    elif s == 's2':                     # two tests, the flag set in each
        b = ('\tstruct iwreq *wrq = (struct iwreq *)rq;\n'
             '\t%s is_null = 0;\n\n' % ty +
             '\tif (dev == NULL) {\n\t\tis_null = 1;\n' + ERR + '\t}\n'
             '\tif (rq == NULL) {\n\t\tis_null = 1;\n' + ERR + '\t}\n\n'
             '\treturn ez_set_new_sc(dev, is_null, &wrq->u.data);\n')
    elif s == 's3':                     # nested test, duplicated body
        b = ('\tstruct iwreq *wrq = (struct iwreq *)rq;\n'
             '\t%s is_null = (dev == NULL || rq == NULL);\n\n' % ty +
             '\tif (dev != NULL) {\n'
             '\t\tif (rq == NULL) {\n' + ERR1 + '\t\t}\n'
             '\t} else {\n' + ERR1 + '\t}\n\n'
             '\treturn ez_set_new_sc(dev, is_null, &wrq->u.data);\n')
    elif s == 's4':                     # the good path is the nested one
        b = ('\tstruct iwreq *wrq = (struct iwreq *)rq;\n'
             '\t%s is_null = (dev == NULL || rq == NULL);\n\n' % ty +
             '\tif (dev && rq)\n'
             '\t\treturn ez_set_new_sc(dev, is_null, &wrq->u.data);\n\n'
             + ERR.replace('\t\t', '\t'))
    elif s == 's5':                     # flag first, pointer after the test
        b = ('\t%s is_null = (dev == NULL || rq == NULL);\n'
             '\tstruct iwreq *wrq;\n\n' % ty +
             '\tif (is_null) {\n' + ERR + '\t}\n\n'
             '\twrq = (struct iwreq *)rq;\n'
             '\treturn ez_set_new_sc(dev, is_null, &wrq->u.data);\n')
    elif s == 's6':                     # two tests and no combined flag
        b = ('\tstruct iwreq *wrq = (struct iwreq *)rq;\n'
             '\t%s is_null = (rq == NULL);\n\n' % ty +
             '\tif (dev == NULL) {\n' + ERR + '\t}\n'
             '\tif (is_null) {\n' + ERR + '\t}\n\n'
             '\treturn ez_set_new_sc(dev, is_null, &wrq->u.data);\n')
    else:                               # s7: goto to a shared error block
        b = ('\tstruct iwreq *wrq = (struct iwreq *)rq;\n'
             '\t%s is_null = (dev == NULL || rq == NULL);\n\n' % ty +
             '\tif (dev == NULL)\n\t\tgoto err;\n'
             '\tif (rq == NULL)\n\t\tgoto err;\n\n'
             '\treturn ez_set_new_sc(dev, is_null, &wrq->u.data);\n\n'
             'err:\n' + ERR.replace('\t\t', '\t'))
    return head + b + '}\n'
