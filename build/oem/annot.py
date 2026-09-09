#!/usr/bin/env python3
"""Filter for `objdump -d -r`: resolve section-relative R_ARM_ABS32 addends in
literal pools to the string / symbol they point at.  Reads the listing on stdin.

  objdump -d -r ... | build/oem/annot.py <the same ELF>
"""
import sys, os, re, bisect
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from elf import ELF

e = ELF(sys.argv[1])
secsyms = {}
for s in e.syms:
    if s['shndx'] >= len(e.sh) or s['type'] in (3, 4) or s['name'] in ('$a', '$d', '$t', ''):
        continue
    secsyms.setdefault(e.sh[s['shndx']]['name'], []).append((s['value'], s['size'], s['name']))
for v in secsyms.values():
    v.sort()

def sym_at(sec, off):
    lst = secsyms.get(sec)
    if not lst:
        return None
    i = bisect.bisect_right(lst, (off, 1 << 30, '\xff')) - 1
    while i >= 0:
        v, sz, nm = lst[i]
        if v <= off and (off < v + sz or sz == 0):
            return nm + ('+%d' % (off - v) if off != v else '')
        i -= 1
    return None

def resolve(sec, addend):
    s = e.byname.get(sec)
    if sec.startswith('.rodata.str') and s and addend < s['size']:
        end = e.d.index(b'\0', s['off'] + addend)
        return '"%s"' % e.d[s['off'] + addend:end].decode('utf-8', 'replace') \
                          .replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')
    return sym_at(sec, addend) or '%s+0x%x' % (sec, addend)

word = re.compile(r'^\s*([0-9a-f]+):\s+([0-9a-f]{8})\s+\.word\s+0x([0-9a-f]+)')
rel = re.compile(r'^\s*([0-9a-f]+):\s+(R_ARM_\w+)\s+(\S+)')
seen = {}
for line in sys.stdin:
    line = line.rstrip('\n')
    m = word.match(line)
    if m:
        seen[int(m.group(1), 16)] = int(m.group(3), 16)
    m = rel.match(line)
    if m and m.group(3).startswith('.') and int(m.group(1), 16) in seen:
        line += '   ; ' + resolve(m.group(3), seen[int(m.group(1), 16)])
    print(line)
