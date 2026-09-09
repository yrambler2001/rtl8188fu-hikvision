#!/usr/bin/env python3
"""The DECL_UID oracle, as a table.

GCC appends `.` plus the declaration's DECL_UID to every file-scope-static and
function-local-static symbol, and DECL_UID counts *every* declaration the front
end creates, in source order.  The shipped module's `__func__.NNNN` /
`__FUNCTION__.NNNN` symbols are therefore an exact statement of how many
declarations the vendor's translation unit saw before each function - the only
thing in the binary that records declarations which emit no code.

This pairs ours against the shipped ones and prints the per-interval deficit,
which localises *where* in the source the missing declarations sit.

  docker exec fuv python3 /src/build/oem/uidgap.py [--obj /tmp/oem/ez_sc.o ...]

The accounting rules, measured with build/oem/uidat.sh against this exact
compiler (see FINDINGS-oem-catalogue.md section 11):

  function definition   2 + max(nparams, 1)   PARM_DECLs, then the
                                              FUNCTION_DECL, then the
                                              RESULT_DECL
  local variable        1
  struct / union def    nfields + 1
  enum definition       nvalues + 1
  typedef               1
  prototype             1 + max(nparams, 1)
  for / while loop      3                     artificial labels, created when
                                              the loop *ends*
  goto label            1                     at first mention
  a definition that
  follows a prototype   +1                    the merged-away duplicate
"""
import argparse, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from elf import ELF, OEM_FILES


def uniquified(e, names=None):
    """[(uid, kind, text)] for every __func__/__FUNCTION__ array."""
    out = []
    for s in e.syms:
        n = s['name']
        if not (n.startswith('__func__.') or n.startswith('__FUNCTION__.')):
            continue
        if s['shndx'] >= len(e.sh):
            continue
        sec = e.sh[s['shndx']]
        txt = e.d[sec['off'] + s['value']:
                  sec['off'] + s['value'] + 64].split(b'\0')[0].decode('utf-8', 'replace')
        if names is not None and txt not in names:
            continue
        out.append((int(n.rsplit('.', 1)[1]), n.split('.')[0], txt))
    out.sort()
    return out


def oem_names(e):
    names = set()
    for s in e.syms:
        if s['type'] != 2 or s['shndx'] >= len(e.sh):
            continue
        if e.sh[s['shndx']]['name'] != '.text':
            continue
        for lo, hi in OEM_FILES.values():
            if lo <= s['value'] < hi:
                names.add(s['name'])
    return names


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--shipped', default=os.environ.get('SHIPPED', '/orig/8188fu.ko'))
    ap.add_argument('--obj', action='append', default=[])
    a = ap.parse_args()
    objs = a.obj or ['/tmp/oem/ez_sc.o', '/tmp/oem/ez_wifi_config.o']

    ship = ELF(a.shipped)
    names = oem_names(ship)
    want = uniquified(ship, names)

    have = []
    for o in objs:
        have += uniquified(ELF(o))
    have.sort()

    hm = {(k, t): u for u, k, t in have}
    print('%-44s %8s %8s %6s %6s %6s' %
          ('function', 'vendor', 'ours', 'vgap', 'ogap', 'short'))
    total = {}
    prev_w = prev_o = None
    prev_file = None
    for u, k, t in want:
        mine = hm.get((k, t))
        f = 'ez_sc.c' if u < 75000 else 'ez_wifi_config.c'
        if f != prev_file:
            prev_w = prev_o = None
            prev_file = f
            print('--- %s' % f)
        if mine is None:
            print('%-44s %8d %8s  (absent)' % (k + ' ' + t, u, '-'))
            continue
        if prev_w is None:
            short = 0
            print('%-44s %8d %8d %6s %6s %6s' %
                  (k + ' ' + t, u, mine, '-', '-',
                   '%+d' % (u - mine) if u != mine else '0'))
            total[f] = total.get(f, 0) + (u - mine)
        else:
            vg, og = u - prev_w, mine - prev_o
            short = vg - og
            print('%-44s %8d %8d %6d %6d %6s' %
                  (k + ' ' + t, u, mine, vg, og, '%+d' % short if short else '0'))
            total[f] = total.get(f, 0) + short
        prev_w, prev_o = u, mine
    print()
    for f, n in sorted(total.items()):
        print('%-44s declarations short: %+d' % (f, n))
    print('%-44s declarations short: %+d' % ('TOTAL', sum(total.values())))
    return 0


if __name__ == '__main__':
    sys.exit(main())
