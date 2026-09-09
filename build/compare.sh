#!/bin/bash
# Compare a freshly built 8188fu.ko against the shipped binary.
# usage: build/compare.sh <path-to-original-8188fu.ko> [path-to-built-8188fu.ko]
set -e
ORIG="$1"; NEW="${2:-./8188fu.ko}"
R=$(command -v arm-none-eabi-readelf || command -v readelf)
echo "=== size ==="
printf '  orig %10d\n  new  %10d\n' "$(stat -f%z "$ORIG" 2>/dev/null || stat -c%s "$ORIG")" \
                                    "$(stat -f%z "$NEW"  2>/dev/null || stat -c%s "$NEW")"
echo "=== vermagic ==="
for f in "$ORIG" "$NEW"; do printf '  %s\n' "$(strings -a "$f" | grep -aE '^vermagic=' | head -1)"; done
echo "=== ARM attributes ==="
diff <($R -A "$ORIG") <($R -A "$NEW") && echo "  IDENTICAL"
echo "=== compiled source files ==="
diff <($R -sW "$ORIG" | awk '$4=="FILE"{print $8}' | sort -u) \
     <($R -sW "$NEW"  | awk '$4=="FILE"{print $8}' | sort -u) || true
echo "=== function symbol coverage ==="
$R -sW "$ORIG" | awk '$4=="FUNC"{print $8}' | sort -u > /tmp/_o.txt
$R -sW "$NEW"  | awk '$4=="FUNC"{print $8}' | sort -u > /tmp/_n.txt
o=$(wc -l < /tmp/_o.txt); c=$(comm -12 /tmp/_o.txt /tmp/_n.txt | wc -l)
awk -v o="$o" -v c="$c" 'BEGIN{printf "  %d / %d  (%.1f%%)\n", c, o, c*100/o}'
