# Variant spec for ez_sc.c:ez_new_sc_ioctl - stage 4, the flag's home.
#
# Seven instructions, all present, two registers swapped: the shipped build
# leaves `rq` in r1 and puts the null-check flag in r3 (`add r2, r1, #16 /
# mov r1, r3`), ours copies `rq` to r2 first and computes the flag into r1.
#
# IRA's dump gives the whole tie: `pref0 is_null <- hr1 @2000` from the
# outgoing argument copy, `pref1 rq <- hr1 @2000` from the incoming parameter
# copy, and `pref2 rq <- hr2 @125` from the `add r2, rq, #16` that sets up the
# third argument.  The two @2000s cancel because the allocnos conflict; the
# @125 does not, so `rq` takes r2.
#
# The lever has to be the allocno graph, so these variants change which
# pseudos exist: the flag written into the `cmd` parameter (which arrives in
# r2 and so has its own preference), into `dev`, kept in a second variable, or
# the pointer given a name that is live before the branch.
UNIT = 'ez_sc'
FUNC = 'ez_new_sc_ioctl'

AXES = {
    'shape': ['a%d' % i for i in range(10)],
    'ty': ['int', 'u32', 's32'],
}

ERR = ('\t\tprintk("ez_new_sc_ioctl input param is NULL!\\n");\n'
       '\t\treturn -1;\n')
HEAD = 'int ez_new_sc_ioctl(struct net_device *dev, struct ifreq *rq, int cmd)\n{\n'


def render(c):
    a, ty = c['shape'], c['ty']
    W = '\tstruct iwreq *wrq = (struct iwreq *)rq;\n'
    if a == 'a0':                        # baseline
        b = (W + '\t%s is_null = (dev == NULL || rq == NULL);\n\n' % ty +
             '\tif (is_null) {\n' + ERR + '\t}\n\n'
             '\treturn ez_set_new_sc(dev, is_null, &wrq->u.data);\n')
    elif a == 'a1':                      # the flag lives in `cmd`
        b = (W + '\n\tcmd = (dev == NULL || rq == NULL);\n'
             '\tif (cmd) {\n' + ERR + '\t}\n\n'
             '\treturn ez_set_new_sc(dev, cmd, &wrq->u.data);\n')
    elif a == 'a2':                      # `cmd` set only on the good path
        b = (W + '\n\tif (dev == NULL || rq == NULL) {\n' + ERR + '\t}\n\n'
             '\tcmd = 0;\n'
             '\treturn ez_set_new_sc(dev, cmd, &wrq->u.data);\n')
    elif a == 'a3':                      # flag in a second variable
        b = (W + '\t%s is_null = (dev == NULL || rq == NULL);\n'
             '\t%s arg;\n\n' % (ty, ty) +
             '\tif (is_null) {\n' + ERR + '\t}\n\n'
             '\targ = is_null;\n'
             '\treturn ez_set_new_sc(dev, arg, &wrq->u.data);\n')
    elif a == 'a4':                      # the iw_point named before the branch
        b = (W + '\tstruct iw_point *iwp = &wrq->u.data;\n'
             '\t%s is_null = (dev == NULL || rq == NULL);\n\n' % ty +
             '\tif (is_null) {\n' + ERR + '\t}\n\n'
             '\treturn ez_set_new_sc(dev, is_null, iwp);\n')
    elif a == 'a5':                      # rq reused as the iwreq pointer
        b = ('\t%s is_null = (dev == NULL || rq == NULL);\n\n' % ty +
             '\tif (is_null) {\n' + ERR + '\t}\n\n'
             '\treturn ez_set_new_sc(dev, is_null,\n'
             '\t\t\t      &((struct iwreq *)rq)->u.data);\n')
    elif a == 'a6':                      # flag computed from wrq
        b = (W + '\t%s is_null = (dev == NULL || wrq == NULL);\n\n' % ty +
             '\tif (is_null) {\n' + ERR + '\t}\n\n'
             '\treturn ez_set_new_sc(dev, is_null, &wrq->u.data);\n')
    elif a == 'a7':                      # the pointer cast after the test
        b = ('\t%s is_null = (dev == NULL || rq == NULL);\n'
             '\tstruct iwreq *wrq;\n\n' % ty +
             '\tif (is_null) {\n' + ERR + '\t}\n\n'
             '\twrq = (struct iwreq *)rq;\n'
             '\treturn ez_set_new_sc(dev, is_null, &wrq->u.data);\n')
    elif a == 'a8':                      # flag stored back into cmd, tested there
        b = (W + '\n\tcmd = (dev == NULL);\n'
             '\tcmd |= (rq == NULL);\n'
             '\tif (cmd) {\n' + ERR + '\t}\n\n'
             '\treturn ez_set_new_sc(dev, cmd, &wrq->u.data);\n')
    else:                                # a9: the flag is the return value
        b = (W + '\t%s ret = (dev == NULL || rq == NULL);\n\n' % ty +
             '\tif (ret) {\n' + ERR + '\t}\n\n'
             '\tret = ez_set_new_sc(dev, ret, &wrq->u.data);\n'
             '\treturn ret;\n')
    return HEAD + b + '}\n'
