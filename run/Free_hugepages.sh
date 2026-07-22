#!/usr/bin/env bash
# Remove specific huge pages from the hugetlb pool by physical address.
#   ./Free_hugepages.sh 0x002000000000,0x004000000000
#   ./Free_hugepages.sh 0x002000000000,0x004000000000 -n     # dry run
#
# Not persistent: a reboot restores the boot time pool.

cd "$(dirname "$0")" || exit 1

if [[ -z "$1" ]]; then
    echo "No argument !!!"
    echo "Usage: $0 <paddr>[,<paddr>...] [-n] [-s <MB>]"
    echo "Run ./Hugepages.sh 1024 first to find the addresses."
    exit 1
fi

sudo python3 ./free_hugepages.py "$@"
