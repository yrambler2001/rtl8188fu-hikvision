#!/usr/bin/env python3
"""Exhaustive variant search for the OEM translation units.

Hand-guessing C shapes for the last few register-allocation residuals stops
paying after a few dozen tries.  This runs the search mechanically instead:
generate many semantically-equivalent spellings of one translation unit,
compile every one with the vendor's flags, and score each against the shipped
bytes.  A compile is about a second and the container has ten cores, so tens of
thousands of variants are practical.

  lab.py --unit ez_sc --dir build/oem/lab/run1 [--fn NAME] [-j 10]

Every `*.c` in --dir is one variant of --unit.  Output is one line per variant,
best first:

  <variant>   n=<differing words> d=<size delta>      # with --fn
  <variant>   tot=<n over all 46 OEM functions>       # without

Scores are cached in <dir>/.cache keyed by source SHA-256, so re-running after
adding variants only compiles the new ones.

Runs *inside* the build container - it needs the cross compiler and the kernel
tree.  The container's python3 is a minimal build (no json, shutil, concurrent
or multiprocessing), so this deliberately sticks to argparse/hashlib/os/re/
struct/subprocess/sys.
"""
import argparse, hashlib, os, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import oemdiff
from elf import oem_funcs

SRC = os.environ.get('SRC', '/src')
KSRC = os.environ.get('KSRC', '/build/linux-vendor')
SHIPPED = os.environ.get('SHIPPED', '/orig/8188fu.ko')
TOOLCHAIN = os.environ.get('TOOLCHAIN_BIN',
                           '/opt/gcc-6.5.0-vendor/arm-linux-gnueabi/bin')
GCC = os.path.join(TOOLCHAIN, 'arm-linux-gnueabi-gcc')
if not os.path.exists(GCC):
    GCC = 'arm-linux-gnueabi-gcc'

TIME = {'ez_sc': '20:43:27', 'ez_wifi_config': '20:43:30'}


def shlex_split(s):
    """Minimal shlex (the container python has no shlex either)."""
    out, cur, q = [], '', None
    i = 0
    while i < len(s):
        c = s[i]
        if q:
            if c == q:
                q = None
            else:
                cur += c
        elif c in '"\'':
            q = c
        elif c.isspace():
            if cur:
                out.append(cur); cur = ''
        else:
            cur += c
        i += 1
    if cur:
        out.append(cur)
    return out


def flags():
    out = subprocess.run(['sh', os.path.join(HERE, 'flags.sh')],
                         stdout=subprocess.PIPE, check=True).stdout.decode()
    return shlex_split(out)


def gcc_cmd(base, cfile, unit, obj, extra=()):
    return [GCC] + base + [
        '-Wno-builtin-macro-redefined',
        '-DKBUILD_BASENAME="%s"' % unit,
        '-DKBUILD_MODNAME="8188fu"',
        '-D__DATE__="Dec 25 2023"',
        '-D__TIME__="%s"' % TIME.get(unit, '20:43:27'),
    ] + list(extra) + ['-c', '-o', obj, cfile]


def score(ship, funcs, obj, focus=None):
    """{name: (differing words, size delta)} plus the total."""
    ours = oemdiff.View(obj)
    rows, _, _, _ = oemdiff.compare(ship, ours, funcs, focus, False)
    per, tot = {}, 0
    for name, fn, size, st, why in rows:
        if st == 'ABSENT':
            continue
        n = d = 0
        for part in why.replace(',', ' ').split():
            if part.startswith('n='):
                n = int(part[2:])
            elif part.startswith('d='):
                d = int(part[2:])
        per[name] = (n, d)
        tot += n
    return tot, per


def cache_load(path):
    if not os.path.exists(path):
        return None
    line = open(path).read().strip()
    if not line:
        return None
    if line.startswith('ERROR'):
        return ('error', line[6:])
    tot, rest = line.split('|', 1)
    per = {}
    for item in rest.split(';'):
        if not item:
            continue
        k, n, d = item.split(',')
        per[k] = (int(n), int(d))
    return (int(tot), per)


def cache_store(path, res):
    if res[0] == 'error':
        open(path, 'w').write('ERROR ' + res[1].replace('\n', ' ')[:400])
        return
    tot, per = res
    open(path, 'w').write('%d|%s' % (
        tot, ';'.join('%s,%d,%d' % (k, v[0], v[1]) for k, v in sorted(per.items()))))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--unit', required=True, choices=['ez_sc', 'ez_wifi_config'])
    ap.add_argument('--dir', required=True, help='directory of *.c variants')
    ap.add_argument('--fn', help='rank by this function only')
    ap.add_argument('-j', '--jobs', type=int, default=os.cpu_count() or 4)
    ap.add_argument('--shipped', default=SHIPPED)
    ap.add_argument('--top', type=int, default=40)
    ap.add_argument('--keep', action='store_true', help='keep the .o files')
    ap.add_argument('--extra', action='append', default=[])
    ap.add_argument('--quiet', action='store_true')
    a = ap.parse_args()

    base = flags()
    d = a.dir if os.path.isabs(a.dir) else os.path.join(SRC, a.dir)
    variants = sorted(f for f in os.listdir(d) if f.endswith('.c'))
    if not variants:
        sys.stderr.write('no variants in %s\n' % d)
        return 1
    cachedir = os.path.join(d, '.cache')
    objdir = os.path.join(d, 'obj')
    for p in (cachedir, objdir):
        if not os.path.isdir(p):
            os.makedirs(p)

    ship = oemdiff.View(a.shipped)
    funcs = oem_funcs(ship.e)

    todo = []
    results = {}
    for v in variants:
        path = os.path.join(d, v)
        h = hashlib.sha256(open(path, 'rb').read()
                           + (' '.join(a.extra)).encode()).hexdigest()[:16]
        cf = os.path.join(cachedir, h)
        got = cache_load(cf)
        if got is not None:
            results[v] = got
        else:
            todo.append((v, path, cf, os.path.join(objdir, v[:-2] + '.o')))

    t0 = time.time()
    running = []          # (proc, v, cf, obj)
    i = 0
    done = 0
    while i < len(todo) or running:
        while i < len(todo) and len(running) < a.jobs:
            v, path, cf, obj = todo[i]; i += 1
            p = subprocess.Popen(gcc_cmd(base, path, a.unit, obj, a.extra),
                                 cwd=KSRC, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.PIPE)
            running.append((p, v, cf, obj))
        time.sleep(0.01)
        still = []
        for p, v, cf, obj in running:
            if p.poll() is None:
                still.append((p, v, cf, obj))
                continue
            err = p.stderr.read().decode('utf-8', 'replace')
            if p.returncode != 0:
                res = ('error', ' | '.join(
                    [l for l in err.splitlines() if 'error' in l][:3]) or 'compile failed')
            else:
                res = score(ship, funcs, obj, a.fn)
                if not a.keep and os.path.exists(obj):
                    os.unlink(obj)
            cache_store(cf, res)
            results[v] = res
            done += 1
            if not a.quiet and done % 50 == 0:
                sys.stderr.write('  %d/%d  %.1fs\n' % (done, len(todo), time.time() - t0))
        running = still

    rows = []
    for v in variants:
        res = results[v]
        if res[0] == 'error':
            rows.append((10 ** 9, 0, v, 'ERROR ' + res[1]))
            continue
        tot, per = res
        if a.fn:
            n, dd = per.get(a.fn, (10 ** 8, 0))
            rows.append((n, dd, v, 'n=%d d=%+d' % (n, dd)))
        else:
            bad = [k for k, (n, dd) in per.items() if n]
            rows.append((tot, 0, v, 'tot=%d  bad=%s' % (tot, ','.join(sorted(bad)) or '-')))
    rows.sort(key=lambda r: (r[0], abs(r[1]), r[2]))
    for n, dd, v, txt in rows[:a.top]:
        print('%-46s %s' % (v, txt))
    if len(rows) > a.top:
        print('... %d more' % (len(rows) - a.top))
    print('\nbest: %s  %s   (%d variants, %d compiled, %.1fs)' %
          (rows[0][2], rows[0][3], len(rows), len(todo), time.time() - t0))
    return 0


if __name__ == '__main__':
    sys.exit(main())
