# Variant spec for ez_sc.c:ez_new_sc_ioctl.
#
# The shipped code is seven instructions:
#
#   cmp r1,#0 / cmpne r0,#0 / moveq r3,#1 / movne r3,#0 / beq err
#   add r2,r1,#16 / mov r1,r3 / b ez_set_new_sc
#
# ours differs only in which register holds the null-check boolean: we copy
# `rq` into r2 first and compute the boolean into r1.  IRA's dump says the
# `add r2, rq, #16` gives `rq` an uncontested weight-125 preference for r2
# that breaks the tie between the two weight-2000 preferences for r1.  Sweep
# every spelling of the boolean, the pointer and the call that keeps the same
# semantics, looking for one that does not create that preference.
UNIT = 'ez_sc'
FUNC = 'ez_new_sc_ioctl'

AXES = {
    # type of the null-check flag
    'ty': ['int', 'u32', 's32', 'u8', 'char', 'long', 'unsigned int', 'short'],
    # how the flag is spelt
    'cond': [
        ('a', '(dev == NULL || rq == NULL)'),
        ('b', '(rq == NULL || dev == NULL)'),
        ('c', '(!dev || !rq)'),
        ('d', '(!rq || !dev)'),
        ('e', '!(dev && rq)'),
        ('f', '!(rq && dev)'),
        ('g', '(dev == NULL) || (rq == NULL)'),
        ('h', '((dev == NULL) | (rq == NULL))'),
    ],
    # declaration order of wrq and the flag, and how the iw_point is reached
    'shape': ['wrq_first', 'flag_first', 'inline_cast', 'iwp_local', 'iwp_late'],
    # how the flag is tested
    'test': [('t0', 'is_null'), ('t1', 'is_null != 0'), ('t2', 'is_null == 1'),
             ('t3', '0 != is_null')],
}


def render(c):
    ty, cond, shape, test = c['ty'], c['cond'], c['shape'], c['test']
    err = ('\t\tprintk("ez_new_sc_ioctl input param is NULL!\\n");\n'
           '\t\treturn -1;\n')
    if shape == 'wrq_first':
        decl = ('\tstruct iwreq *wrq = (struct iwreq *)rq;\n'
                '\t%s is_null = %s;\n' % (ty, cond))
        arg = '&wrq->u.data'
    elif shape == 'flag_first':
        decl = ('\t%s is_null = %s;\n'
                '\tstruct iwreq *wrq = (struct iwreq *)rq;\n' % (ty, cond))
        arg = '&wrq->u.data'
    elif shape == 'inline_cast':
        decl = '\t%s is_null = %s;\n' % (ty, cond)
        arg = '&((struct iwreq *)rq)->u.data'
    elif shape == 'iwp_local':
        decl = ('\tstruct iwreq *wrq = (struct iwreq *)rq;\n'
                '\tstruct iw_point *iwp = &wrq->u.data;\n'
                '\t%s is_null = %s;\n' % (ty, cond))
        arg = 'iwp'
    else:   # iwp_late
        decl = ('\tstruct iwreq *wrq = (struct iwreq *)rq;\n'
                '\t%s is_null = %s;\n'
                '\tstruct iw_point *iwp;\n' % (ty, cond))
        arg = 'iwp'
    body = ''
    if shape == 'iwp_late':
        body = '\tiwp = &wrq->u.data;\n'
    return ('int ez_new_sc_ioctl(struct net_device *dev, struct ifreq *rq, int cmd)\n'
            '{\n'
            + decl +
            '\n'
            '\tif (%s) {\n' % test
            + err +
            '\t}\n'
            '\n'
            + body +
            '\treturn ez_set_new_sc(dev, is_null, %s);\n' % arg +
            '}\n')
