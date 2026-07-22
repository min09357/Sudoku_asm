#!/usr/bin/env python3
"""Report where the system's huge pages live in physical address space.

Two independent views are produced:

1. Physical view  - scans /proc/kpageflags at huge-page-aligned PFNs over every
                    "System RAM" range in /proc/iomem and reports each hugetlb
                    page (both free pool pages and pages currently mapped).
2. Process view   - walks /proc/<pid>/smaps for hugetlb VMAs and translates the
                    virtual addresses through /proc/<pid>/pagemap.

Both views need CAP_SYS_ADMIN, so run this as root (see Hugepages.sh).
"""

import argparse
import os
import re
import struct
import sys

KPF_BUDDY = 3
KPF_COMPOUND_HEAD = 15
KPF_HUGE = 17
KPF_THP = 22

PAGE_SIZE = os.sysconf("SC_PAGESIZE")
PAGEMAP_PRESENT = 1 << 63
PAGEMAP_PFN_MASK = (1 << 55) - 1


def human(size):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:g}{unit}"
        size /= 1024


def hugepage_sizes():
    """Huge page sizes (in bytes) supported by this kernel, largest first."""
    base = "/sys/kernel/mm/hugepages"
    sizes = []
    for entry in os.listdir(base):
        m = re.fullmatch(r"hugepages-(\d+)kB", entry)
        if m:
            sizes.append(int(m.group(1)) * 1024)
    return sorted(sizes, reverse=True)


def pool_status():
    """Per-size pool counters exported under /sys/kernel/mm/hugepages."""
    base = "/sys/kernel/mm/hugepages"
    status = {}
    for size in hugepage_sizes():
        d = f"{base}/hugepages-{size // 1024}kB"
        counters = {}
        for name in ("nr_hugepages", "free_hugepages", "resv_hugepages",
                     "surplus_hugepages"):
            try:
                with open(f"{d}/{name}") as f:
                    counters[name] = int(f.read())
            except OSError:
                counters[name] = -1
        status[size] = counters
    return status


def system_ram_ranges():
    """(start, end) physical byte ranges backed by RAM; end is exclusive."""
    ranges = []
    with open("/proc/iomem") as f:
        for line in f:
            addr, _, name = line.partition(":")
            if name.strip() != "System RAM":
                continue
            start, _, end = addr.strip().partition("-")
            start, end = int(start, 16), int(end, 16) + 1
            if end > start:
                ranges.append((start, end))
    if ranges and all(start == 0 and end == 1 for start, end in ranges):
        # /proc/iomem is zeroed out for unprivileged readers
        raise PermissionError("/proc/iomem is masked; run as root")
    return ranges


def scan_physical(sizes, ranges):
    """Find hugetlb head pages by probing kpageflags at aligned PFNs."""
    found = []
    seen = set()
    flags = os.open("/proc/kpageflags", os.O_RDONLY)
    counts = os.open("/proc/kpagecount", os.O_RDONLY)
    try:
        # Larger sizes are scanned first so that a 1GB head page is not
        # reported a second time by the 2MB-aligned pass.
        for size in sizes:
            for start, end in ranges:
                addr = (start + size - 1) & ~(size - 1)
                while addr + size <= end:
                    pfn = addr // PAGE_SIZE
                    if pfn in seen:
                        addr += size
                        continue
                    raw = os.pread(flags, 8, pfn * 8)
                    if len(raw) == 8:
                        bits = struct.unpack("<Q", raw)[0]
                        if bits & (1 << KPF_HUGE) and \
                           bits & (1 << KPF_COMPOUND_HEAD):
                            cnt_raw = os.pread(counts, 8, pfn * 8)
                            refcount = struct.unpack("<Q", cnt_raw)[0] \
                                if len(cnt_raw) == 8 else -1
                            found.append({
                                "paddr": addr,
                                "size": size,
                                "refcount": refcount,
                                "thp": bool(bits & (1 << KPF_THP)),
                                "buddy": bool(bits & (1 << KPF_BUDDY)),
                            })
                            seen.add(pfn)
                    addr += size
    finally:
        os.close(flags)
        os.close(counts)
    found.sort(key=lambda p: p["paddr"])
    return found


def numa_node_of(paddr):
    """Best-effort NUMA node lookup via the memory block sysfs layout."""
    try:
        with open("/sys/devices/system/memory/block_size_bytes") as f:
            block = int(f.read().strip(), 16)
    except OSError:
        return None
    block_id = paddr // block
    path = f"/sys/devices/system/memory/memory{block_id}"
    try:
        for entry in os.listdir(path):
            m = re.fullmatch(r"node(\d+)", entry)
            if m:
                return int(m.group(1))
    except OSError:
        pass
    return None


def hugetlb_vmas(pid):
    """Hugetlb VMAs of one process: (start, end, kernel page size, name)."""
    vmas = []
    start = end = None
    name = ""
    try:
        with open(f"/proc/{pid}/smaps") as f:
            for line in f:
                m = re.match(r"^([0-9a-f]+)-([0-9a-f]+) \S+ \S+ \S+ \S+\s*(.*)$",
                             line)
                if m:
                    start, end = int(m.group(1), 16), int(m.group(2), 16)
                    name = m.group(3).strip()
                    continue
                if line.startswith("KernelPageSize:") and start is not None:
                    ps = int(line.split()[1]) * 1024
                    if ps > PAGE_SIZE:
                        vmas.append((start, end, ps, name))
    except (OSError, ValueError):
        pass
    return vmas


def virt_to_phys(pagemap, vaddr):
    raw = os.pread(pagemap, 8, (vaddr // PAGE_SIZE) * 8)
    if len(raw) != 8:
        return None
    entry = struct.unpack("<Q", raw)[0]
    if not entry & PAGEMAP_PRESENT:
        return None
    return (entry & PAGEMAP_PFN_MASK) * PAGE_SIZE + (vaddr % PAGE_SIZE)


def scan_processes():
    """Map every hugetlb VMA of every process to its physical addresses."""
    results = []
    for pid in sorted(p for p in os.listdir("/proc") if p.isdigit()):
        vmas = hugetlb_vmas(pid)
        if not vmas:
            continue
        try:
            with open(f"/proc/{pid}/comm") as f:
                comm = f.read().strip()
        except OSError:
            comm = "?"
        try:
            fd = os.open(f"/proc/{pid}/pagemap", os.O_RDONLY)
        except OSError:
            continue
        try:
            for start, end, ps, name in vmas:
                for vaddr in range(start, end, ps):
                    paddr = virt_to_phys(fd, vaddr)
                    results.append({
                        "pid": int(pid), "comm": comm, "vaddr": vaddr,
                        "paddr": paddr, "size": ps, "name": name,
                    })
        finally:
            os.close(fd)
    return results


def main():
    parser = argparse.ArgumentParser(
        description="Show the physical addresses of the system's huge pages")
    parser.add_argument("-s", "--size", type=int, default=0,
                        help="only report this huge page size in MB (e.g. 1024)")
    parser.add_argument("-p", "--processes", action="store_true",
                        help="also list hugetlb mappings per process")
    parser.add_argument("-q", "--quiet", action="store_true",
                        help="print only the physical address list")
    args = parser.parse_args()

    if os.geteuid() != 0:
        print("[-] must run as root (kpageflags/pagemap are privileged)",
              file=sys.stderr)
        return 1

    sizes = hugepage_sizes()
    if args.size:
        sizes = [s for s in sizes if s == args.size * 1024 * 1024]
        if not sizes:
            print(f"[-] no such huge page size: {args.size}MB", file=sys.stderr)
            return 1

    if not args.quiet:
        print("[+] huge page pool")
        status = pool_status()
        for size in sizes:
            c = status[size]
            print(f"    {human(size):>5}: total={c['nr_hugepages']} "
                  f"free={c['free_hugepages']} resv={c['resv_hugepages']} "
                  f"surplus={c['surplus_hugepages']}")

    ranges = system_ram_ranges()
    pages = scan_physical(sizes, ranges)

    # Number the pages per size, in ascending physical address order, so that
    # the same page keeps the same index across both views.
    index_of = {}
    next_index = {}
    for page in pages:
        idx = next_index.get(page["size"], 0)
        page["index"] = idx
        index_of[page["paddr"]] = idx
        next_index[page["size"]] = idx + 1

    if not args.quiet:
        print(f"[+] physical layout ({len(pages)} huge pages found)")
    for page in pages:
        node = numa_node_of(page["paddr"])
        node_str = f" node={node}" if node is not None else ""
        state = "in-use" if page["refcount"] > 0 else "free"
        print(f"    #{page['index']:<5} "
              f"0x{page['paddr']:012x}-0x{page['paddr'] + page['size'] - 1:012x}"
              f"  pfn=0x{page['paddr'] // PAGE_SIZE:09x}"
              f"  {human(page['size']):>5}  {state:<6}"
              f"  refcount={page['refcount']}{node_str}")

    if args.processes:
        mappings = scan_processes()
        if not args.quiet:
            print(f"[+] process mappings ({len(mappings)} huge pages mapped)")
        for m in mappings:
            if m["paddr"] is None:
                paddr, index = "unmapped", "?"
            else:
                head = m["paddr"] & ~(m["size"] - 1)
                paddr = f"0x{m['paddr']:012x}"
                index = index_of.get(head, "?")
            print(f"    #{index:<5} pid={m['pid']:<7} {m['comm']:<16} "
                  f"va=0x{m['vaddr']:012x} pa={paddr} "
                  f"{human(m['size']):>5} {m['name']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
