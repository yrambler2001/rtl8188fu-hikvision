#!/usr/bin/env python3
"""Side-by-side, edit-distance-aligned disassembly of one function.

`run.sh --fn X -v` compares the two instruction streams *positionally*, so a
single inserted instruction makes every later line look different.  This
aligns them the way lab.py's `s` score does - Levenshtein over the words with
the register fields blanked - and prints the alignment, so what is actually
structurally different is one glance rather than an inference.

    docker exec fuv python3 /src/build/oem/align.py process_config_vars
    docker exec fuv python3 /src/build/oem/align.py ez_strsep --obj /tmp/x.o
"""
import argparse, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from elf import ELF
import oemdiff
import lab as _lab

SHIPPED = os.environ.get('SHIPPED', '/orig/8188fu.ko')
TOOLCHAIN = os.environ.get('TOOLCHAIN_BIN',
                           '/opt/gcc-6.5.0-vendor/arm-linux-gnueabi/bin')
OBJDUMP = os.path.join(TOOLCHAIN, 'arm-linux-gnueabi-objdump')
if not os.path.exists(OBJDUMP):
    OBJDUMP = 'arm-linux-gnueabi-objdump'


def find(path, name):
    e = ELF(path)
    for sy in e.syms:
        if sy['name'].split('.')[0] == name and sy['type'] == 2:
            sec = e.sh[sy['shndx']]
            return sy['value'], sy['size'], sec['addr'], sec['off'], e
    raise SystemExit('%s: no such function in %s' % (name, path))


def disasm(path, addr, size):
    out = subprocess.run(
        [OBJDUMP, '-d', '--start-address', hex(addr),
         '--stop-address', hex(addr + size), path],
        stdout=subprocess.PIPE).stdout.decode('utf-8', 'replace')
    rows = []
    for line in out.splitlines():
        parts = line.split('\t')
        if len(parts) < 2:
            continue
        try:
            a = int(parts[0].strip().rstrip(':'), 16)
        except ValueError:
            continue
        word = parts[1].strip()
        if len(word) != 8:
            continue
        txt = parts[2].strip() if len(parts) > 2 else ''
        rows.append((a - addr, int(word, 16), txt))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('func')
    ap.add_argument('--obj', default='/tmp/oem/ez_wifi_config.o')
    ap.add_argument('--shipped', default=SHIPPED)
    a = ap.parse_args()

    sa, ss, ssec, soff, _ = find(a.shipped, a.func)
    oa, os_, osec, ooff, _ = find(a.obj, a.func)
    S = disasm(a.shipped, sa, ss)
    O = disasm(a.obj, oa, os_)
    # Use the same normalisation lab.py's `s` uses: relocated words masked and
    # branch displacements dropped, so the score here matches the sweep's.
    sv, ov = oemdiff.View(a.shipped), oemdiff.View(a.obj)
    sb, sops = sv.norm(sa, ss)
    ob, oops = ov.norm(oa, os_)
    A = _lab._words(sb)
    B = _lab._words(ob)
    sopt = {o: '%s %s' % (k, t) for o, k, t in sops}
    oopt = {o: '%s %s' % (k, t) for o, k, t in oops}
    S = [(off, w, sopt.get(off, txt)) for off, w, txt in S]
    O = [(off, w, oopt.get(off, txt)) for off, w, txt in O]

    # Levenshtein with traceback
    n, m = len(A), len(B)
    d = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        d[i][0] = i
    for j in range(m + 1):
        d[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1,
                          d[i - 1][j - 1] + (0 if A[i - 1] == B[j - 1] else 1))
    i, j, path = n, m, []
    while i or j:
        if i and j and d[i][j] == d[i - 1][j - 1] + (0 if A[i - 1] == B[j - 1] else 1):
            path.append((i - 1, j - 1)); i -= 1; j -= 1
        elif i and d[i][j] == d[i - 1][j] + 1:
            path.append((i - 1, None)); i -= 1
        else:
            path.append((None, j - 1)); j -= 1
    path.reverse()

    print('%-52s | %s' % ('SHIPPED %s (%d bytes)' % (a.func, ss),
                          'OURS (%d bytes)' % os_))
    print('-' * 110)
    for si, oi in path:
        l = ('%4d %08x %s' % (S[si][0], S[si][1], S[si][2])) if si is not None else ''
        r = ('%4d %08x %s' % (O[oi][0], O[oi][1], O[oi][2])) if oi is not None else ''
        if si is None or oi is None:
            mark = '<<' if oi is None else '>>'
        elif A[si] != B[oi]:
            mark = '!!'
        elif S[si][1] != O[oi][1]:
            mark = ' r'
        else:
            mark = '  '
        print('%-52s %s %s' % (l[:52], mark, r))
    print('\nstructural distance s=%d over %d/%d instructions' % (d[n][m], n, m))
    return 0


if __name__ == '__main__':
    sys.exit(main())
