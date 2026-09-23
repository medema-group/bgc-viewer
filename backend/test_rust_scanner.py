#!/usr/bin/env python3
"""Test the Rust extension for scanning JSON records."""

import time
from pathlib import Path
from bgc_viewer import bgc_scanner

test_file = Path("../data/NC_003888.3.json")

print(f"Testing Rust extension with: {test_file}")
print(f"File size: {test_file.stat().st_size / 1024 / 1024:.1f} MB\n")

# Benchmark the Rust scanner
print("=" * 80)
print("Rust bgc_scanner.scan_records()")
print("=" * 80)

start = time.time()
positions = bgc_scanner.scan_records(str(test_file))
elapsed = time.time() - start

print(f"Time: {elapsed:.3f}s")
print(f"Records found: {len(positions)}")
print(f"Throughput: {test_file.stat().st_size / 1024 / 1024 / elapsed:.1f} MB/s")
print(f"\nFirst 3 record positions:")
for i, (start_pos, end_pos) in enumerate(positions[:3]):
    print(f"  Record {i+1}: {start_pos} - {end_pos} ({end_pos - start_pos} bytes)")

# Verify the positions are correct
print("\n" + "=" * 80)
print("Verification")
print("=" * 80)

import json

with open(test_file, 'rb') as f:
    content = f.read()

for i, (start, end) in enumerate(positions[:3]):
    record_bytes = content[start:end]
    try:
        record = json.loads(record_bytes.decode('utf-8'))
        record_id = record.get('id', 'NO ID')
        feature_count = len(record.get('features', []))
        print(f"Record {i+1}: ✓ Valid JSON - ID: {record_id}, {feature_count} features")
    except Exception as e:
        print(f"Record {i+1}: ✗ Failed - {e}")

# Compare with Python implementation
print("\n" + "=" * 80)
print("Comparison with Python implementation")
print("=" * 80)

start_py = time.time()
records_pos = content.find(b'"records"')
bracket_pos = content.find(b'[', records_pos)
pos = bracket_pos + 1
brace_depth = 0
record_start = None
in_string = False
escape_next = False
py_positions = []

for i in range(pos, len(content)):
    byte = content[i:i+1]
    
    if escape_next:
        escape_next = False
        continue
    
    if byte == b'\\':
        escape_next = True
        continue
    
    if byte == b'"':
        in_string = not in_string
        continue
    
    if in_string:
        continue
    
    if byte == b'{':
        if brace_depth == 0:
            record_start = i
        brace_depth += 1
    elif byte == b'}':
        brace_depth -= 1
        if brace_depth == 0 and record_start is not None:
            record_end = i + 1
            py_positions.append((record_start, record_end))
            record_start = None
    elif byte == b']' and brace_depth == 0:
        break

elapsed_py = time.time() - start_py

print(f"Python time: {elapsed_py:.3f}s")
print(f"Rust time:   {elapsed:.3f}s")
print(f"Speedup:     {elapsed_py / elapsed:.1f}x faster")
print(f"\nPython throughput: {test_file.stat().st_size / 1024 / 1024 / elapsed_py:.1f} MB/s")
print(f"Rust throughput:   {test_file.stat().st_size / 1024 / 1024 / elapsed:.1f} MB/s")
