# Variant spec for ez_sc.c:ez_new_sc_ioctl, second pass: structural shapes.
#
# The first pass (ez_new_sc_ioctl.py, 1280 variants over type / condition
# spelling / declaration order / test form) moved nothing: every one scored
# n=5.  This pass varies the *structure* instead - PHI vs conditional
# expression, recomputed vs cached boolean, if/else vs early return, extra
# live locals, the pointer reached through different casts - because the
# residual is an IRA preference tie and only the allocno graph can break it.
UNIT = 'ez_sc'
FUNC = 'ez_new_sc_ioctl'

HDR = 'int ez_new_sc_ioctl(struct net_device *dev, struct ifreq *rq, int cmd)\n{\n'
ERR = ('\t\tprintk("ez_new_sc_ioctl input param is NULL!\\n");\n')

AXES = {
    'ty': ['int', 'u32', 'u8', 'char', 'long'],
    'shape': ['s%02d' % i for i in range(18)],
    'ptr': ['p0', 'p1', 'p2', 'p3'],
}


def ptr_decl(p):
    return {
        'p0': ('\tstruct iwreq *wrq = (struct iwreq *)rq;\n', '&wrq->u.data'),
        'p1': ('', '&((struct iwreq *)rq)->u.data'),
        'p2': ('\tstruct iwreq *wrq;\n', '&wrq->u.data'),
        'p3': ('\tstruct iwreq *wrq = (struct iwreq *)rq;\n', '(struct iw_point *)&wrq->u'),
    }[p]


def render(c):
    ty, shape, p = c['ty'], c['shape'], c['ptr']
    pd, arg = ptr_decl(p)
    assign = '\twrq = (struct iwreq *)rq;\n' if p == 'p2' else ''
    call = '\treturn ez_set_new_sc(dev, %%s, %s);\n' % arg

    if shape == 's00':      # baseline
        b = (pd + '\t%s is_null = (dev == NULL || rq == NULL);\n\n' % ty +
             '\tif (is_null) {\n' + ERR + '\t\treturn -1;\n\t}\n\n' + assign +
             call % 'is_null')
    elif shape == 's01':    # PHI form: initialise then set in an if
        b = (pd + '\t%s is_null = 0;\n\n' % ty +
             '\tif (dev == NULL || rq == NULL)\n\t\tis_null = 1;\n\n'
             '\tif (is_null) {\n' + ERR + '\t\treturn -1;\n\t}\n\n' + assign +
             call % 'is_null')
    elif shape == 's02':    # recompute the boolean at the call
        b = (pd + '\n\tif (dev == NULL || rq == NULL) {\n' + ERR +
             '\t\treturn -1;\n\t}\n\n' + assign +
             call % '(dev == NULL || rq == NULL)')
    elif shape == 's03':    # if/else, single return
        b = (pd + '\t%s is_null = (dev == NULL || rq == NULL);\n'
             '\t%s ret;\n\n' % (ty, ty) +
             '\tif (is_null) {\n' + ERR + '\t\tret = -1;\n\t} else {\n' + assign.replace('\t', '\t\t') +
             '\t\tret = ez_set_new_sc(dev, is_null, %s);\n\t}\n\n' % arg +
             '\treturn ret;\n')
    elif shape == 's04':    # goto to a shared error tail
        b = (pd + '\t%s is_null = (dev == NULL || rq == NULL);\n\n' % ty +
             '\tif (is_null)\n\t\tgoto err;\n\n' + assign + call % 'is_null' +
             '\nerr:\n' + ERR.replace('\t\t', '\t') + '\treturn -1;\n')
    elif shape == 's05':    # boolean written through a second local
        b = (pd + '\t%s is_null = (dev == NULL || rq == NULL);\n'
             '\t%s zero = is_null;\n\n' % (ty, ty) +
             '\tif (is_null) {\n' + ERR + '\t\treturn -1;\n\t}\n\n' + assign +
             call % 'zero')
    elif shape == 's06':    # test the pointers, pass the flag
        b = (pd + '\t%s is_null = (dev == NULL || rq == NULL);\n\n' % ty +
             '\tif (!dev || !rq) {\n' + ERR + '\t\treturn -1;\n\t}\n\n' + assign +
             call % 'is_null')
    elif shape == 's07':    # flag computed after the pointer is used
        b = (pd + '\t%s is_null;\n\n' % ty + assign +
             '\tis_null = (dev == NULL || rq == NULL);\n'
             '\tif (is_null) {\n' + ERR + '\t\treturn -1;\n\t}\n\n' +
             call % 'is_null')
    elif shape == 's08':    # ternary
        b = (pd + '\t%s is_null = (dev == NULL || rq == NULL) ? 1 : 0;\n\n' % ty +
             '\tif (is_null) {\n' + ERR + '\t\treturn -1;\n\t}\n\n' + assign +
             call % 'is_null')
    elif shape == 's09':    # extra live local used in the call
        b = (pd + '\t%s is_null = (dev == NULL || rq == NULL);\n'
             '\tstruct net_device *nd = dev;\n\n' % ty +
             '\tif (is_null) {\n' + ERR + '\t\treturn -1;\n\t}\n\n' + assign +
             '\treturn ez_set_new_sc(nd, is_null, %s);\n' % arg)
    elif shape == 's10':    # the iw_point in its own local, declared first
        b = ('\tstruct iwreq *wrq = (struct iwreq *)rq;\n'
             '\tstruct iw_point *iwp = &wrq->u.data;\n'
             '\t%s is_null = (dev == NULL || rq == NULL);\n\n' % ty +
             '\tif (is_null) {\n' + ERR + '\t\treturn -1;\n\t}\n\n' +
             '\treturn ez_set_new_sc(dev, is_null, iwp);\n')
    elif shape == 's11':    # the iw_point assigned after the test
        b = ('\tstruct iwreq *wrq = (struct iwreq *)rq;\n'
             '\tstruct iw_point *iwp;\n'
             '\t%s is_null = (dev == NULL || rq == NULL);\n\n' % ty +
             '\tif (is_null) {\n' + ERR + '\t\treturn -1;\n\t}\n\n'
             '\tiwp = &wrq->u.data;\n'
             '\treturn ez_set_new_sc(dev, is_null, iwp);\n')
    elif shape == 's12':    # boolean via bitwise or of the two tests
        b = (pd + '\t%s is_null = ((dev == NULL) | (rq == NULL));\n\n' % ty +
             '\tif (is_null) {\n' + ERR + '\t\treturn -1;\n\t}\n\n' + assign +
             call % 'is_null')
    elif shape == 's13':    # cmd is touched, so its allocno exists
        b = (pd + '\t%s is_null = (dev == NULL || rq == NULL);\n\n' % ty +
             '\tif (is_null) {\n' + ERR + '\t\treturn -1;\n\t}\n\n' + assign +
             call % 'is_null' + '\t(void)cmd;\n')
    elif shape == 's14':    # error path prints and falls to a shared return
        b = (pd + '\t%s is_null = (dev == NULL || rq == NULL);\n\n' % ty +
             '\tif (!is_null)\n' + assign +
             '\t\treturn ez_set_new_sc(dev, is_null, %s);\n\n' % arg +
             ERR.replace('\t\t', '\t') + '\treturn -1;\n')
    elif shape == 's15':    # cast the flag at the call
        b = (pd + '\t%s is_null = (dev == NULL || rq == NULL);\n\n' % ty +
             '\tif (is_null) {\n' + ERR + '\t\treturn -1;\n\t}\n\n' + assign +
             call % '(int)is_null')
    elif shape == 's16':    # the pointer taken from a second cast local
        b = ('\tstruct iwreq *wrq = (struct iwreq *)rq;\n'
             '\tstruct ifreq *r2 = rq;\n'
             '\t%s is_null = (dev == NULL || r2 == NULL);\n\n' % ty +
             '\tif (is_null) {\n' + ERR + '\t\treturn -1;\n\t}\n\n' +
             '\treturn ez_set_new_sc(dev, is_null, &wrq->u.data);\n')
    else:                   # s17: control - deliberately different, to prove
        b = (pd + '\t%s is_null = (dev == NULL || rq == NULL);\n\n' % ty +
             '\tif (is_null) {\n' + ERR + '\t\treturn -1;\n\t}\n\n' + assign +
             '\treturn ez_set_new_sc(dev, cmd, %s);\n' % arg)
    if p == 'p2' and shape in ('s03', 's14'):
        return None         # wrq would be used uninitialised in one arm
    return HDR + b + '}\n'
