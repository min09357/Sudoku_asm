#!/usr/bin/env bash
# Find which combination of refresh-domain functions is a bank direction.
#
# DecomposeUsingRefreshes flags every function that appears in the expansion of
# a channel/rank function. When the reversed basis is not aligned with the
# hardware basis, more functions get flagged than there are domain bits: a rank
# function such as (f_a XOR f_b) makes both f_a and f_b light up.
#
# Given N flagged functions and D domain bits, exactly (N - D) independent
# combinations of the flagged functions leave the refresh domain unchanged.
# This script drives watch_refreshes in check mode over every k-subset of the
# flagged set (k = 2, then 3, ...) and reports which ones do.
#
#   coarse avg ~= tREFI/2  -> domain changes  -> not a bank direction
#   coarse avg ~= tREFI    -> domain unchanged -> the XOR is a bank direction
#
#   ./Find_rank_function.sh <node> [k]      # k defaults to 2

cd "$(dirname "$0")" || exit 1

NODE_ID=${1:-0}
SUBSET_SIZE=${2:-2}

if [[ "$NODE_ID" == "0" ]]; then
    ALL="0x40 0x100 0x4000 0x80000 0x100000 0x200000 0x1000000040"
    # Functions DecomposeUsingRefreshes flagged as tREFI/2.
    FLAGGED="0x40 0x100 0x4000 0x1000000040"
    ROW="0xfffc70000"
    COL="0xbe80"
    DRAM_ARGS="-p 75 -t ddr4 -n 4 -s 32 -r 2 -w 4"
else
    echo "Node $NODE_ID is not configured. Add its functions and DRAM_ARGS above."
    exit 1
fi

OUTDIR="rank_search_node${NODE_ID}"
mkdir -p "$OUTDIR"

# Emit every k-subset of the flagged functions, one per line, comma separated.
subsets() {
    python3 -c '
import itertools, sys
items = sys.argv[2:]
for c in itertools.combinations(items, int(sys.argv[1])):
    print(",".join(c))
' "$SUBSET_SIZE" $FLAGGED
}

echo "[+] node $NODE_ID, ${SUBSET_SIZE}-subsets of: $FLAGGED"
echo

IDX=0
while read -r DIFF; do
    IDX=$((IDX + 1))

    # same = every function not in diff
    SAME=""
    for f in $ALL; do
        [[ ",$DIFF," == *",$f,"* ]] && continue
        SAME="${SAME:+$SAME,}$f"
    done

    PREFIX="$OUTDIR/pair${IDX}"
    echo "[$IDX] diff: $DIFF"

    sudo numactl -N "$NODE_ID" -m "$NODE_ID" ./watch_refreshes \
        -o "$PREFIX" -m check $DRAM_ARGS \
        -S "$SAME" -D "$DIFF" -R "$ROW" -C "$COL" -l >/dev/null 2>&1

    # Only the coarse oracle carries the domain signal; the fine log is ignored.
    python3 ./summarize_check.py "$PREFIX.check.refresh.coarse.log"
    echo
done < <(subsets)

echo "[+] logs in $OUTDIR/"
