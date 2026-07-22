#!/usr/bin/env bash
# Print the physical addresses of the huge pages present in the system.
#   ./Hugepages.sh              all huge page sizes
#   ./Hugepages.sh 1024         only 1GB pages
#   ./Hugepages.sh 1024 -p      also list per-process hugetlb mappings

cd "$(dirname "$0")" || exit 1

args=()
if [[ -n "$1" && "$1" != -* ]]; then
    args+=(-s "$1")
    shift
fi

sudo python3 ./show_hugepages.py "${args[@]}" "$@"
