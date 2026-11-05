#!/usr/bin/env python3
"""Benchmark the Rust record scanner on antiSMASH JSON files.

Usage:
    python benchmark_scanner.py FILE [FILE ...]

Accepts .json, .json.gz, and .json.bz2 files. Throughput is reported against
the decompressed size, which is what the scanner walks.
"""

import sys
import time
from pathlib import Path

from bgc_viewer import bgc_scanner

for path in map(Path, sys.argv[1:]):
    start = time.perf_counter()
    scan = bgc_scanner.scan_file(path)
    elapsed = time.perf_counter() - start

    scanned_bytes = scan.records[-1].byte_end if scan.records else 0
    print(f"{path.name}: {len(scan.records)} records in {elapsed:.3f}s")
    print(f"  on-disk size:      {path.stat().st_size / 1e6:.1f} MB")
    print(f"  throughput:        {scanned_bytes / 1e6 / elapsed:.0f} MB/s (decompressed)")
    for record in scan.records[:3]:
        print(
            f"  {record.record_id}: bytes {record.byte_start}-{record.byte_end}, "
            f"{record.feature_count} features, {record.region_count} regions, "
            f"organism={record.organism!r}"
        )
