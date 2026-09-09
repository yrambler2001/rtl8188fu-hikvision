#!/usr/bin/env python3
"""Per-function scoreboard for the two reconstructed OEM translation units.

The whole point is a seconds-long loop: compile *only* ez_sc.c and
ez_wifi_config.c into object files, then ask, function by function, "is this
byte-identical to what the vendor shipped?".  No link, no 158-file build.

Comparison is relocation-aware, because an object file cannot be compared to a
linked module byte for byte:

  * bytes covered by a relocation are masked out of the byte compare and
    compared *symbolically* instead - (offset-in-function, reloc type, target
    symbol name, addend), where a section-relative addend into .rodata.str1.1
    is resolved to the actual string;
  * B/BL/BLX words are compared by their relocation (in our .o every call is a
    relocation; in the shipped module intra-.text calls were already resolved
    by the assembler, so those are compared as "branch to <name>" using the
    shipped symbol table);
  * everything else must match exactly.

usage:
  build/oem/oemdiff.py --shipped <8188fu.ko> --obj <ez_sc.o> [--obj <..>] [--fn NAME]
  build/oem/oemdiff.py --shipped <8188fu.ko> --catalogue          # dump the catalogue
"""
import sys, os, re, struct, bisect, argparse

UNIQ = re.compile(r'\.\d+$')   # GCC's local-symbol uniquifier: __func__.71055

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from elf import ELF, STB, STT, OEM_FILES, oem_funcs

R_ARM = {2: 'ABS32', 3: 'REL32', 28: 'CALL', 29: 'JUMP24', 40: 'V4BX',
         43: 'PREL31', 44: 'MOVW_ABS_NC', 45: 'MOVT_ABS', 0: 'NONE',
         1: 'PC24', 5: 'ABS16', 8: 'ABS8', 42: 'TARGET2'}


class View:
    """A .text-bearing ELF plus symbol/relocation indexes."""

    def __init__(self, path):
        self.e = ELF(path)
        e = self.e
        self.text = e.byname['.text']
        self.data = e.d
        # address -> function symbol (for resolving assembler-resolved branches)
        self.faddr = {}
        for s in e.syms:
            if s['type'] == 2 and s['shndx'] < len(e.sh) and e.sh[s['shndx']]['name'] == '.text':
                self.faddr.setdefault(s['value'], s['name'])
        # relocations against .text, keyed by offset
        self.rel = {}
        for off, si, ty in e.relocs('.text'):
            self.rel[off] = (si, ty)
        # per-section symbol lists for addend resolution
        self.secsyms = {}
        for s in e.syms:
            if s['shndx'] >= len(e.sh) or s['type'] in (3, 4) or s['name'] in ('$a', '$d', '$t', ''):
                continue
            self.secsyms.setdefault(e.sh[s['shndx']]['name'], []).append(
                (s['value'], s['size'], s['name']))
        for v in self.secsyms.values():
            v.sort()

    def cstr(self, sec, off):
        s = self.e.byname.get(sec)
        if not s or off >= s['size']:
            return None
        d = self.e.d
        end = d.index(b'\0', s['off'] + off)
        return d[s['off'] + off:end]

    def sym_at(self, sec, off):
        lst = self.secsyms.get(sec)
        if not lst:
            return None
        i = bisect.bisect_right(lst, (off, 1 << 30, '\xff')) - 1
        while i >= 0:
            v, sz, nm = lst[i]
            if v <= off and (off < v + sz or sz == 0):
                return nm + ('+%d' % (off - v) if off != v else '')
            i -= 1
        return None

    def target(self, si, addend):
        """Symbolic name of relocation <si> with in-place addend.

        The trailing .NNNN of a GCC local-symbol uniquifier is stripped: it
        tracks the translation unit's total DECL count, not the code."""
        s = self.e.syms[si]
        nm = UNIQ.sub('', s['name'])
        if s['type'] == 3 or not nm:                       # section symbol
            sec = self.e.sh[s['shndx']]['name'] if s['shndx'] < len(self.e.sh) else '?'
            if sec.startswith('.rodata.str'):
                v = self.cstr(sec, addend)
                if v is not None:
                    return 'STR:' + repr(v.decode('utf-8', 'replace'))
            r = self.sym_at(sec, addend)
            return UNIQ.sub('', r) if r else '%s+0x%x' % (sec, addend)
        return nm + ('+%d' % addend if addend else '')

    def bytes_at(self, addr, size):
        o = self.text['off'] + addr
        return self.data[o:o + size]

    def norm(self, addr, size):
        """(masked bytes, [(off, kind, target)]) for one function."""
        b = bytearray(self.bytes_at(addr, size))
        ops = []
        for i in range(0, size, 4):
            w = struct.unpack_from('<I', b, i)[0]
            off = addr + i
            if off in self.rel:
                si, ty = self.rel[off]
                tn = R_ARM.get(ty, str(ty))
                if tn in ('CALL', 'JUMP24', 'PC24'):
                    ops.append((i, tn, self.e.syms[si]['name']))
                    struct.pack_into('<I', b, i, w & 0xff000000)
                else:
                    t = self.target(si, w)
                    if self.e.syms[si]['type'] == 3 and t.startswith(
                            self.faddr.get(addr, '\0')):
                        t = '.+%d' % (w - addr)    # switch table entry
                    ops.append((i, tn, t))
                    struct.pack_into('<I', b, i, 0)
            elif ((w >> 25) & 7) == 0b101:                   # B/BL, already resolved
                disp = w & 0xffffff
                if disp & 0x800000:
                    disp -= 0x1000000
                tgt = off + 8 + disp * 4
                if addr <= tgt < addr + size:      # branch inside this function
                    nm = '.+%d' % (tgt - addr)
                else:
                    nm = self.faddr.get(tgt, 'text+0x%x' % tgt)
                ops.append((i, 'BL' if (w >> 24) & 1 else 'B', nm))
                struct.pack_into('<I', b, i, w & 0xff000000)
        return bytes(b), ops


def compare(ship, ours, funcs, want=None, verbose=False):
    ok = bad = miss = 0
    rows = []
    for name, addr, size, fn in funcs:
        if want and want != name:
            continue
        if name not in ours.faddr.values():
            rows.append((name, fn, size, 'ABSENT', ''))
            miss += 1
            continue
        oaddr = [a for a, n in ours.faddr.items() if n == name][0]
        osz = [s['size'] for s in ours.e.syms if s['name'] == name and s['type'] == 2][0]
        sb, sops = ship.norm(addr, size)
        ob, oops = ours.norm(oaddr, osz)
        if osz != size:
            rows.append((name, fn, size, 'SIZE %+d' % (osz - size),
                         'n=%d,d=%+d' % (worddist(sb, ob, sops, oops), osz - size)))
            bad += 1
            if verbose:
                dump(ship, ours, name, addr, size, oaddr, osz)
            continue
        if sb == ob and sops == oops:
            rows.append((name, fn, size, 'OK', 'n=0,d=+0'))
            ok += 1
            continue
        d = next((i for i in range(size) if sb[i] != ob[i]), None)
        why = 'bytes@%d' % d if d is not None else 'reloc'
        if d is None:
            for a, bb in zip(sops, oops):
                if a != bb:
                    why = 'reloc@%d %s != %s' % (a[0], a[2], bb[2])
                    break
        why = 'n=%d,d=+0 %s' % (worddist(sb, ob, sops, oops), why)
        rows.append((name, fn, size, 'DIFF', why))
        bad += 1
        if verbose:
            dump(ship, ours, name, addr, size, oaddr, osz)
    return rows, ok, bad, miss


def worddist(sb, ob, sops, oops):
    """Number of 4-byte words that differ, counting operand kind/target too."""
    so = {o: (k, t) for o, k, t in sops}
    oo = {o: (k, t) for o, k, t in oops}
    n = 0
    for i in range(0, max(len(sb), len(ob)), 4):
        a = sb[i:i + 4] if i < len(sb) else None
        b = ob[i:i + 4] if i < len(ob) else None
        if a != b or so.get(i) != oo.get(i):
            n += 1
    return n


def dump(ship, ours, name, addr, size, oaddr, osz):
    sb, sops = ship.norm(addr, size)
    ob, oops = ours.norm(oaddr, osz)
    so = {o: (k, t) for o, k, t in sops}
    oo = {o: (k, t) for o, k, t in oops}
    print('--- %s   shipped %d bytes @%08x   ours %d bytes' % (name, size, addr, osz))
    for i in range(0, max(size, osz), 4):
        a = struct.unpack_from('<I', ship.bytes_at(addr, size), i)[0] if i < size else None
        b = struct.unpack_from('<I', ours.bytes_at(oaddr, osz), i)[0] if i < osz else None
        sa = '%08x %-28s' % (a, ('%s %s' % so[i]) if i in so else '') if a is not None else ' ' * 37
        sbb = '%08x %-28s' % (b, ('%s %s' % oo[i]) if i in oo else '') if b is not None else ''
        same = (i < size and i < osz and sb[i:i + 4] == ob[i:i + 4] and so.get(i) == oo.get(i))
        print('  %+4d %s %s %s' % (i, sa, '  ' if same else '!!', sbb))


def catalogue(ship):
    funcs = oem_funcs(ship.e)
    print('# %d OEM functions' % len(funcs))
    for name, addr, size, fn in funcs:
        _, ops = ship.norm(addr, size)
        calls = sorted({t for o, k, t in ops if k in ('BL', 'B', 'CALL', 'JUMP24')})
        strs = [t[4:] for o, k, t in ops if t.startswith('STR:')]
        objs = sorted({t for o, k, t in ops if not t.startswith('STR:')
                       and k not in ('BL', 'B', 'CALL', 'JUMP24')})
        print('\n## %s  [%s]  %08x  %d bytes' % (name, fn, addr, size))
        if calls:
            print('   calls:  ' + ', '.join(calls))
        if objs:
            print('   refs:   ' + ', '.join(objs))
        for s in strs:
            print('   str:    ' + s)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--shipped', required=True)
    ap.add_argument('--obj', action='append', default=[])
    ap.add_argument('--fn')
    ap.add_argument('--also', action='append', default=[],
                    help='also score this (public) function, by name')
    ap.add_argument('--catalogue', action='store_true')
    ap.add_argument('-v', '--verbose', action='store_true')
    ap.add_argument('--score', action='store_true',
                    help='compact machine-readable score: NAME dsize nwords')
    a = ap.parse_args()

    ship = View(a.shipped)
    if a.catalogue:
        catalogue(ship)
        return 0

    funcs = oem_funcs(ship.e)
    for n in a.also:
        for sym in ship.e.syms:
            if sym['name'] == n and sym['type'] == 2:
                funcs.append((n, sym['value'], sym['size'], '(public)'))
                break
    total = sum(s for _, _, s, _ in funcs)
    allrows = []
    ok = bad = miss = 0
    okbytes = 0
    for o in a.obj:
        ours = View(o)
        rows, o_, b_, m_ = compare(ship, ours, funcs, a.fn, a.verbose)
        for r in rows:
            if r[3] == 'ABSENT':
                continue
            allrows.append(r)
        ok += o_; bad += b_; miss += m_
    seen = {r[0] for r in allrows}
    for name, addr, size, fn in funcs:
        if name not in seen and not a.fn:
            allrows.append((name, fn, size, 'ABSENT', ''))
    order = {n: i for i, (n, _, _, _) in enumerate(funcs)}
    allrows.sort(key=lambda r: order.get(r[0], 999))
    if a.score:
        for name, fn, size, st, why in allrows:
            print('SCORE %s %s' % (name, why if why.startswith('n=') else 'n=?'))
        return 0
    for name, fn, size, st, why in allrows:
        if st == 'OK':
            okbytes += size
        print('%-6s %-44s %-18s %5d  %s' % (st, name, fn, size, why))
    print('\n%d/%d functions byte-identical, %d/%d bytes' %
          (sum(1 for r in allrows if r[3] == 'OK'), len(funcs), okbytes, total))
    return 0


if __name__ == '__main__':
    sys.exit(main())
