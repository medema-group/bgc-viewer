"""Type stubs for the Rust ``bgc_scanner`` extension (rust_extensions/src/lib.rs)."""

from os import PathLike

class ScannedRecord:
    byte_start: int
    byte_end: int
    record_id: str | None
    description: str | None
    organism: str | None
    feature_count: int
    region_count: int

class FileScan:
    version: str | None
    input_file: str | None
    records: list[ScannedRecord]

def scan_file(file_path: str | PathLike[str]) -> FileScan: ...
