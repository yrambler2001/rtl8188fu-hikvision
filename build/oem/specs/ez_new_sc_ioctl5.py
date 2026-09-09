# ez_new_sc_ioctl - stage 5, driven by IRA's own numbers rather than by guesses.
#
# `-fira-verbose=9` on our object prints exactly two allocnos and three
# preferences:
#
#	pref0:a0(r124 is_null)<-hr1@2000
#	pref1:a1(r116 rq)<-hr1@2000
#	pref2:a1(r116 rq)<-hr2@125
#	Popping a1(r116) -- assign reg 2 ; Popping a0(r124) -- assign reg 1
#
# The two 2000s are the incoming-parameter copy for `rq` and the outgoing
# second argument for `is_null`; they conflict and cancel in
# `assign_hard_reg`'s conflict costs, so `rq`'s weak weight-125 preference for
# r2 - which comes from `add r2, rq, #16` writing the hard argument register
# directly - decides, and `rq` moves to r2 while `is_null` takes r1.  The
# shipped build has it the other way round: `rq` stays in r1 and `is_null`
# lands in r3 with a `mov r1, r3` before the tail call.
#
# So the axes worth sweeping are the ones that can remove or outweigh that
# weight-125 preference: how the third argument's address is written, whether
# it goes through a named local, the type of the flag, and how the guard is
# spelled.
UNIT = 'ez_sc'
FUNC = 'ez_new_sc_ioctl'

ARG3 = [
    ('wrq', '\tstruct iwreq *wrq = (struct iwreq *)rq;\n', '&wrq->u.data'),
    ('inline', '', '&((struct iwreq *)rq)->u.data'),
    ('u', '\tstruct iwreq *wrq = (struct iwreq *)rq;\n', '&(wrq->u).data'),
    ('local', '\tstruct iwreq *wrq = (struct iwreq *)rq;\n\tstruct iw_point *pt;\n', 'pt'),
    ('cast', '', '(struct iw_point *)((char *)rq + 16)'),
]
FLAG = ['int', 'u32', 'unsigned int', 'char', 'u8', '_Bool', 'long']
COND = [
    ('or', '(dev == NULL || rq == NULL)'),
    ('bang', '(!dev || !rq)'),
    ('bor', '(dev == NULL) | (rq == NULL)'),
    ('rev', '(rq == NULL || dev == NULL)'),
]

AXES = {
    'a3': [(a[0], '%d' % i) for i, a in enumerate(ARG3)],
    'flag': FLAG,
    'cond': [(c[0], '%d' % i) for i, c in enumerate(COND)],
    'order': ['flag_first', 'decl_first'],
}


def render(c):
    name, decl, expr = ARG3[int(c['a3'])]
    cond = COND[int(c['cond'])][1]
    flagdecl = '\t%s is_null = %s;\n' % (c['flag'], cond)
    if name == 'local':
        pre = decl + flagdecl + '\n\tpt = &wrq->u.data;\n'
    elif c['order'] == 'flag_first':
        pre = flagdecl + decl
    else:
        pre = decl + flagdecl
    if name == 'local' and c['order'] == 'flag_first':
        return None
    return ('int ez_new_sc_ioctl(struct net_device *dev, struct ifreq *rq, int cmd)\n{\n'
            + pre +
            '\n\tif (is_null) {\n'
            '\t\tprintk("ez_new_sc_ioctl input param is NULL!\\n");\n'
            '\t\treturn -1;\n\t}\n\n'
            '\treturn ez_set_new_sc(dev, is_null, %s);\n}\n' % expr)
