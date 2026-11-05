"""
Tests for the Rust ``bgc_scanner`` extension that indexes record byte ranges.
"""

import bz2
import gzip
import json

import pytest

from bgc_viewer import bgc_scanner


def _write(path, text):
    """Write ``text`` to ``path``, compressing by extension; returns the raw bytes."""
    raw = text.encode("utf-8")
    if path.name.endswith(".gz"):
        path.write_bytes(gzip.compress(raw))
    elif path.name.endswith(".bz2"):
        path.write_bytes(bz2.compress(raw))
    else:
        path.write_bytes(raw)
    return raw


def _assert_ranges_match(scan, raw, records):
    assert len(scan.records) == len(records)
    for scanned, record in zip(scan.records, records):
        assert json.loads(raw[scanned.byte_start : scanned.byte_end]) == record


@pytest.mark.parametrize("name", ["data.json", "data.json.gz", "data.json.bz2"])
def test_scans_plain_and_compressed_files(temp_dir, sample_antismash_data, name):
    """Byte ranges refer to the decompressed content for every format."""
    raw = _write(temp_dir / name, json.dumps(sample_antismash_data, indent=2))

    scan = bgc_scanner.scan_file(temp_dir / name)

    assert scan.version == "1.0"
    assert scan.input_file == "test_sample.json"
    _assert_ranges_match(scan, raw, sample_antismash_data["records"])
    first = scan.records[0]
    assert first.record_id == "test_record_1"
    assert first.description == "Test record 1"
    assert first.organism == "Streptomyces coelicolor"
    assert first.feature_count == 6
    assert first.region_count == 1


def test_braces_and_escapes_inside_strings(temp_dir):
    """Brackets, quotes, and backslashes inside strings are not structure."""
    records = [
        {
            "id": 'weird "id" {[',
            "description": "back\\slash \\\" } ] é ☃",
            "features": [{"type": "misc", "qualifiers": {"note": ["}}]]{{["]}}],
        },
        {"id": "second", "features": []},
    ]
    data = {"records": records}
    raw = _write(temp_dir / "data.json", json.dumps(data))

    scan = bgc_scanner.scan_file(temp_dir / "data.json")

    _assert_ranges_match(scan, raw, records)
    assert scan.records[0].record_id == 'weird "id" {['
    assert scan.records[0].description == records[0]["description"]
    assert scan.records[1].feature_count == 0


def test_only_top_level_keys_are_used(temp_dir):
    """Nested ``records``/``version`` keys do not confuse the scanner."""
    data = {
        "schema": {"records": [{"id": "decoy"}], "version": "decoy"},
        "records": [
            {
                "id": "real",
                "annotations": {"id": "decoy", "features": [1, 2, 3]},
                "features": [
                    {"type": "CDS", "qualifiers": {"organism": ["not a source"]}},
                    {"type": "source", "qualifiers": {"organism": ["E. coli", "x"]}},
                    {"qualifiers": {"organism": ["after source"]}, "type": "source"},
                ],
            }
        ],
        "version": "8.0",
    }
    raw = _write(temp_dir / "data.json", json.dumps(data))

    scan = bgc_scanner.scan_file(temp_dir / "data.json")

    assert scan.version == "8.0"
    _assert_ranges_match(scan, raw, data["records"])
    record = scan.records[0]
    assert record.record_id == "real"
    assert record.feature_count == 3
    assert record.organism == "E. coli"


def test_organism_qualifier_before_type(temp_dir):
    """A source feature is recognized whatever its key order."""
    data = {
        "records": [
            {"features": [{"qualifiers": {"organism": ["Late type"]}, "type": "source"}]}
        ]
    }
    _write(temp_dir / "data.json", json.dumps(data))

    record = bgc_scanner.scan_file(temp_dir / "data.json").records[0]

    assert record.organism == "Late type"
    assert record.record_id is None
    assert record.description is None


def test_regions_array_takes_precedence(temp_dir):
    data = {
        "records": [
            {
                "id": "r",
                "regions": [{}, {}, {}],
                "features": [{"type": "region"}, 42, "x"],
            }
        ]
    }
    _write(temp_dir / "data.json", json.dumps(data))

    record = bgc_scanner.scan_file(temp_dir / "data.json").records[0]

    assert record.region_count == 3
    assert record.feature_count == 3


def test_escape_across_chunk_boundary(temp_dir):
    """An escape split over two read chunks is still skipped correctly."""
    chunk_size = 4 * 1024 * 1024
    prefix = '{"records": [{"id": "big", "seq": "'
    # Place the backslash as the very last byte of the first chunk.
    padding = "a" * (chunk_size - len(prefix) - 1)
    text = prefix + padding + '\\"}"}, {"id": "next"}]}'
    raw = _write(temp_dir / "data.json", text)
    assert raw[chunk_size - 1 : chunk_size + 1] == b'\\"'

    scan = bgc_scanner.scan_file(temp_dir / "data.json")

    _assert_ranges_match(scan, raw, json.loads(text)["records"])


def test_missing_records_array(temp_dir):
    _write(temp_dir / "data.json", '{"version": "1"}')

    scan = bgc_scanner.scan_file(temp_dir / "data.json")

    assert scan.records == []
    assert scan.version == "1"


@pytest.mark.parametrize(
    "text",
    ['{"records": [{"id": "x"}', '{"records": [{"id": "x}]}', '{"records": ]}'],
)
def test_malformed_json_raises_value_error(temp_dir, text):
    _write(temp_dir / "data.json", text)

    with pytest.raises(ValueError, match="Malformed JSON"):
        bgc_scanner.scan_file(temp_dir / "data.json")


def test_missing_file_raises_os_error(temp_dir):
    with pytest.raises(OSError):
        bgc_scanner.scan_file(temp_dir / "missing.json")


def test_corrupt_gzip_raises_os_error(temp_dir):
    (temp_dir / "data.json.gz").write_bytes(b"not gzip at all")

    with pytest.raises(OSError):
        bgc_scanner.scan_file(temp_dir / "data.json.gz")
