#!/usr/bin/env python3
"""Generate the cross product of semantically-neutral spellings of one OEM
function, as complete translation units ready for lab.py.

Hand-written C shapes stop paying after a few dozen tries.  A spec expresses
one function as a template with orthogonal axes - declaration order, local
types, explicit temporary vs recomputation, if/else vs early return, operand
order in commutative expressions, comparison direction, short-circuit order,
loop form, switch vs if-chain, cached base pointer vs repeated dereference,
extra used and unused locals, statement order where independent - and this
enumerates every combination, splicing each into a real copy of the unit.

  build/oem/gen.py --spec build/oem/specs/<name>.py --out build/oem/lab/<run>
  docker exec fuv python3 /src/build/oem/lab.py \
      --unit <unit> --dir build/oem/lab/<run> --fn <function>

A spec module defines:

  UNIT   'ez_sc' | 'ez_wifi_config'      which translation unit to patch
  FUNC   'ez_new_sc_ioctl'               which function to replace
  AXES   {'name': [alternative, ...]}    orthogonal choices; a value may be a
                                         string or a (label, string) pair
  render(c) -> str                       the function text for one choice dict
  SKIP   (optional) render() may return None to drop a combination

Runs on the host (full python); lab.py does the compiling in the container.
"""
import argparse, hashlib, itertools, os, re, sys


def load_spec(path):
    ns = {'__file__': path, '__name__': 'spec'}
    exec(compile(open(path).read(), path, 'exec'), ns)
    return ns


def find_function(text, name):
    """Return (start, end) of the whole definition of `name` in `text`.

    The OEM sources are formatted kernel-style: a definition starts at column
    zero and ends at a `}` at column zero.
    """
    pat = re.compile(r'^[A-Za-z_][A-Za-z_0-9 \t\*]*\b%s\s*\(' % re.escape(name), re.M)
    m = pat.search(text)
    if not m:
        raise SystemExit('gen.py: %s not found' % name)
    start = m.start()
    end = text.index('\n}\n', start) + 3
    return start, end


def axis_items(vals):
    for v in vals:
        if isinstance(v, tuple):
            yield v
        else:
            yield (v, v)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--spec', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--root', default=os.path.join(
        os.path.dirname(os.path.abspath(__file__)), '..', '..'))
    ap.add_argument('--limit', type=int, default=200000)
    ap.add_argument('--clean', action='store_true')
    a = ap.parse_args()

    spec = load_spec(a.spec)
    unit, func, axes = spec['UNIT'], spec['FUNC'], spec['AXES']
    src = os.path.join(a.root, 'os_dep', 'linux', unit + '.c')
    text = open(src).read()
    start, end = find_function(text, func)
    head, tail = text[:start], text[end:]

    if not os.path.isdir(a.out):
        os.makedirs(a.out)
    if a.clean:
        for f in os.listdir(a.out):
            if f.endswith('.c'):
                os.unlink(os.path.join(a.out, f))

    names = list(axes)
    pools = [list(axis_items(axes[n])) for n in names]
    seen = {}
    n = 0
    for combo in itertools.product(*pools):
        choice = {nm: val for nm, (lab, val) in zip(names, combo)}
        labels = {nm: lab for nm, (lab, val) in zip(names, combo)}
        body = spec['render'](choice)
        if body is None:
            continue
        whole = head + body + tail
        h = hashlib.sha256(whole.encode()).hexdigest()[:12]
        if h in seen:
            continue
        seen[h] = True
        tag = '-'.join(str(labels[nm]) for nm in names)
        tag = re.sub(r'[^A-Za-z0-9_.-]', '_', tag)[:110]
        open(os.path.join(a.out, '%05d_%s.c' % (n, tag)), 'w').write(whole)
        n += 1
        if n >= a.limit:
            break
    print('%s: %d distinct variants of %s in %s' % (
        os.path.basename(a.spec), n, func, a.out))
    return 0


if __name__ == '__main__':
    sys.exit(main())
