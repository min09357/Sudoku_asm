#!/usr/bin/env python3
"""Remove specific huge pages from the hugetlb pool by physical address.

The kernel offers no way to say "dissolve *this* physical huge page" -- writing
to nr_hugepages only shrinks the pool by a count and the kernel picks which free
page to dissolve. This tool works around that:

  1. occupy every free huge page of the affected node via mmap(MAP_HUGETLB)
  2. munmap only the targets, so they become the *only* free pages on that node
  3. shrink nr_hugepages by the number of targets -- the kernel now has no
     choice but to dissolve exactly those pages
  4. release the rest; the pool target is already lowered, so they come back as
     free pages while the targets stay gone

Everything up to step 3 is validated first, so any failure leaves the system
untouched. The change does not survive a reboot.

Usage:
    sudo ./dissolve_hugepages.py 0x002000000000,0x004000000000
"""

import argparse
import ctypes
import ctypes.util
import os
import struct
import sys

PAGE_SIZE = os.sysconf("SC_PAGESIZE")
PAGEMAP_PRESENT = 1 << 63
PAGEMAP_PFN_MASK = (1 << 55) - 1

PROT_READ = 0x1
PROT_WRITE = 0x2
MAP_PRIVATE = 0x02
MAP_ANONYMOUS = 0x20
MAP_POPULATE = 0x8000
MAP_HUGETLB = 0x40000
MAP_HUGE_SHIFT = 26
MAP_FAILED = ctypes.c_void_p(-1).value

SYS_set_mempolicy = 238  # x86_64
MPOL_DEFAULT = 0
MPOL_BIND = 2

NODE_SYSFS = "/sys/devices/system/node"
MEM_SYSFS = "/sys/devices/system/memory"


def human(size):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:g}{unit}"
        size /= 1024


def read_int(path):
    with open(path) as f:
        return int(f.read().strip())


def hugepage_dir(node, size):
    return f"{NODE_SYSFS}/node{node}/hugepages/hugepages-{size // 1024}kB"


def counters(node, size):
    d = hugepage_dir(node, size)
    return {name: read_int(f"{d}/{name}")
            for name in ("nr_hugepages", "free_hugepages", "surplus_hugepages")}


def numa_node_of(paddr):
    """Resolve a physical address to its NUMA node via the memory block sysfs."""
    block = int(open(f"{MEM_SYSFS}/block_size_bytes").read().strip(), 16)
    path = f"{MEM_SYSFS}/memory{paddr // block}"
    for entry in os.listdir(path):
        if entry.startswith("node") and entry[4:].isdigit():
            return int(entry[4:])
    raise LookupError(f"no NUMA node owns 0x{paddr:012x}")


def virt_to_phys(pagemap, vaddr):
    raw = os.pread(pagemap, 8, (vaddr // PAGE_SIZE) * 8)
    if len(raw) != 8:
        return None
    entry = struct.unpack("<Q", raw)[0]
    if not entry & PAGEMAP_PRESENT:
        return None
    return (entry & PAGEMAP_PFN_MASK) * PAGE_SIZE + (vaddr % PAGE_SIZE)


class Libc:
    """mmap/munmap plus set_mempolicy, which glibc does not export."""

    def __init__(self):
        self.lib = ctypes.CDLL(ctypes.util.find_library("c"), use_errno=True)
        self.lib.mmap.restype = ctypes.c_void_p
        self.lib.mmap.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int,
                                  ctypes.c_int, ctypes.c_int, ctypes.c_long]
        self.lib.munmap.restype = ctypes.c_int
        self.lib.munmap.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
        self.lib.syscall.restype = ctypes.c_long

    def map_hugepage(self, size):
        flags = (MAP_PRIVATE | MAP_ANONYMOUS | MAP_POPULATE | MAP_HUGETLB |
                 (size.bit_length() - 1) << MAP_HUGE_SHIFT)
        ctypes.set_errno(0)
        addr = self.lib.mmap(None, size, PROT_READ | PROT_WRITE, flags, -1, 0)
        if addr is None or addr == MAP_FAILED:
            return None
        return addr

    def unmap(self, addr, size):
        return self.lib.munmap(ctypes.c_void_p(addr), size)

    def bind_node(self, node):
        if node >= 64:
            raise ValueError(f"node {node} out of range for a single-word mask")
        mask = ctypes.c_ulong(1 << node)
        ctypes.set_errno(0)
        rc = self.lib.syscall(ctypes.c_long(SYS_set_mempolicy),
                             ctypes.c_int(MPOL_BIND), ctypes.byref(mask),
                             ctypes.c_ulong(64))
        if rc != 0:
            raise OSError(ctypes.get_errno(),
                          f"set_mempolicy(MPOL_BIND, node{node}) failed")

    def unbind(self):
        self.lib.syscall(ctypes.c_long(SYS_set_mempolicy),
                        ctypes.c_int(MPOL_DEFAULT), None, ctypes.c_ulong(0))


def occupy_node(libc, pagemap, node, size, expected):
    """mmap every free huge page of one node; returns [(vaddr, paddr), ...]."""
    libc.bind_node(node)
    held = []
    # The cap only guards against an unexpected runaway; the loop normally ends
    # when the pool is exhausted and mmap fails.
    for _ in range(expected + 4):
        vaddr = libc.map_hugepage(size)
        if vaddr is None:
            break
        paddr = virt_to_phys(pagemap, vaddr)
        if paddr is None:
            libc.unmap(vaddr, size)
            raise RuntimeError("huge page not present in pagemap after "
                               "MAP_POPULATE (is this really root?)")
        held.append((vaddr, paddr))
    return held


def main():
    parser = argparse.ArgumentParser(
        description="Dissolve specific huge pages by physical address")
    parser.add_argument("addresses",
                        help="comma separated huge page physical addresses, "
                             "e.g. 0x002000000000,0x004000000000")
    parser.add_argument("-s", "--size", type=int, default=1024,
                        help="huge page size in MB (default: 1024)")
    parser.add_argument("-n", "--dry-run", action="store_true",
                        help="identify the targets but leave the pool alone")
    args = parser.parse_args()

    if os.geteuid() != 0:
        print("[-] must run as root (pagemap and sysfs writes are privileged)",
              file=sys.stderr)
        return 1

    size = args.size * 1024 * 1024
    if not os.path.isdir(f"/sys/kernel/mm/hugepages/hugepages-{size // 1024}kB"):
        print(f"[-] kernel does not support {human(size)} huge pages",
              file=sys.stderr)
        return 1

    targets = []
    for token in args.addresses.split(","):
        token = token.strip()
        if not token:
            continue
        paddr = int(token, 0)
        if paddr % size:
            print(f"[-] 0x{paddr:012x} is not {human(size)} aligned",
                  file=sys.stderr)
            return 1
        targets.append(paddr)
    if not targets:
        print("[-] no addresses given", file=sys.stderr)
        return 1

    # Group the targets by the node that owns them; that decides which per-node
    # nr_hugepages has to shrink.
    by_node = {}
    for paddr in targets:
        by_node.setdefault(numa_node_of(paddr), []).append(paddr)

    print("[+] targets")
    for node in sorted(by_node):
        for paddr in sorted(by_node[node]):
            print(f"    0x{paddr:012x}  {human(size):>5}  node={node}")

    before = {}
    for node in sorted(by_node):
        before[node] = counters(node, size)
        if before[node]["surplus_hugepages"]:
            print(f"[-] node{node} has surplus huge pages; refusing to touch "
                  "the pool", file=sys.stderr)
            return 1

    libc = Libc()
    pagemap = os.open("/proc/self/pagemap", os.O_RDONLY)
    held = {}
    try:
        # Occupy every node first, then validate, so that a failure on the
        # second node cannot leave the first one already modified.
        for node in sorted(by_node):
            free = before[node]["free_hugepages"]
            print(f"[+] occupying {free} free huge page(s) on node{node} "
                  f"({human(free * size)} to fault in, this takes a while)")
            held[node] = occupy_node(libc, pagemap, node, size, free)
            print(f"    held {len(held[node])}")

        for node in sorted(by_node):
            owned = {paddr for _, paddr in held[node]}
            missing = [p for p in by_node[node] if p not in owned]
            if missing:
                print("[-] could not take hold of: " +
                      ", ".join(f"0x{p:012x}" for p in missing) +
                      "\n    (wrong address, or another process is using it)",
                      file=sys.stderr)
                return 1
            for _, paddr in held[node]:
                if numa_node_of(paddr) != node:
                    print(f"[-] got a page from node{numa_node_of(paddr)} while "
                          f"bound to node{node}; aborting", file=sys.stderr)
                    return 1

        if args.dry_run:
            print("[+] dry run: pool left untouched")
            return 0

        # Release the targets on every node before writing anything, so that a
        # bad free count on the second node cannot leave the first one shrunk.
        released = {}
        for node in sorted(by_node):
            wanted = set(by_node[node])
            released[node] = [(v, p) for v, p in held[node] if p in wanted]
            for vaddr, _ in released[node]:
                libc.unmap(vaddr, size)
            held[node] = [(v, p) for v, p in held[node] if p not in wanted]

        for node in sorted(by_node):
            # The targets must now be the only free pages on this node,
            # otherwise the kernel could dissolve something else.
            free = read_int(f"{hugepage_dir(node, size)}/free_hugepages")
            if free != len(released[node]):
                print(f"[-] node{node}: expected {len(released[node])} free "
                      f"huge page(s) but found {free}; aborting before the pool "
                      "is modified", file=sys.stderr)
                return 1

        for node in sorted(by_node):
            target_nr = before[node]["nr_hugepages"] - len(released[node])
            with open(f"{hugepage_dir(node, size)}/nr_hugepages", "w") as f:
                f.write(str(target_nr))
            actual = read_int(f"{hugepage_dir(node, size)}/nr_hugepages")
            if actual != target_nr:
                print(f"[-] node{node}: nr_hugepages is {actual}, expected "
                      f"{target_nr}", file=sys.stderr)
                return 1
            print(f"[+] node{node}: dissolved {len(released[node])} page(s), "
                  f"nr_hugepages {before[node]['nr_hugepages']} -> {actual}")
    finally:
        for mappings in held.values():
            for vaddr, _ in mappings:
                libc.unmap(vaddr, size)
        libc.unbind()
        os.close(pagemap)

    print("[+] result")
    for node in sorted(by_node):
        c = counters(node, size)
        print(f"    node{node}: total={c['nr_hugepages']} "
              f"free={c['free_hugepages']}")
    print("[!] not persistent -- a reboot restores the boot time pool")

    return 0


if __name__ == "__main__":
    sys.exit(main())
