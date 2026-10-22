use pyo3::exceptions::{PyIOError, PyValueError};
use pyo3::prelude::*;
use std::fs::File;
use std::io::{self, Read};
use std::path::{Path, PathBuf};

/// Size of the chunks read from the (decompressed) input stream.
const CHUNK_SIZE: usize = 4 * 1024 * 1024;

/// Longest object key worth capturing; every key the scanner acts on is shorter.
const MAX_KEY_LEN: usize = 32;

/// Longest string value captured for record metadata. Longer values are dropped
/// rather than kept, so a pathological file cannot balloon memory.
const MAX_VALUE_LEN: usize = 64 * 1024;

/// Python-style repr of an optional string, for ``__repr__``.
fn py_repr(value: &Option<String>) -> String {
    match value {
        Some(text) => format!("{:?}", text),
        None => "None".to_string(),
    }
}

/// One record of the top-level ``records`` array.
#[pyclass(get_all, frozen, module = "bgc_viewer.bgc_scanner")]
#[derive(Clone, Debug, Default)]
struct ScannedRecord {
    /// Offset of the record's opening ``{`` in the decompressed stream.
    byte_start: u64,
    /// Offset just past the record's closing ``}`` in the decompressed stream.
    byte_end: u64,
    /// The record's ``id``, when it is a string.
    record_id: Option<String>,
    /// The record's ``description``, when it is a string.
    description: Option<String>,
    /// First ``organism`` qualifier of the first ``source`` feature declaring one.
    organism: Option<String>,
    /// Number of elements in the record's ``features`` array.
    feature_count: u64,
    /// Length of the record's ``regions`` array when present, otherwise the
    /// number of features whose ``type`` is ``region``.
    region_count: u64,
}

#[pymethods]
impl ScannedRecord {
    fn __repr__(&self) -> String {
        format!(
            "ScannedRecord(record_id={}, byte_start={}, byte_end={})",
            py_repr(&self.record_id),
            self.byte_start,
            self.byte_end
        )
    }
}

/// Result of scanning one antiSMASH JSON file.
#[pyclass(get_all, frozen, module = "bgc_viewer.bgc_scanner")]
#[derive(Clone, Debug, Default)]
struct FileScan {
    /// Top-level ``version`` string, when present.
    version: Option<String>,
    /// Top-level ``input_file`` string, when present.
    input_file: Option<String>,
    /// The records of the top-level ``records`` array, in file order.
    records: Vec<ScannedRecord>,
}

#[pymethods]
impl FileScan {
    fn __repr__(&self) -> String {
        format!(
            "FileScan(version={}, input_file={}, records=<{} records>)",
            py_repr(&self.version),
            py_repr(&self.input_file),
            self.records.len()
        )
    }
}

/// Object keys the scanner reacts to. Everything else is ``Other``.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
enum Key {
    Other,
    Records,
    Version,
    InputFile,
    Id,
    Description,
    Features,
    Regions,
    Type,
    Qualifiers,
    Organism,
}

/// What a container is, derived from where it sits in the document.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
enum Role {
    Root,
    Records,
    Record,
    Features,
    Regions,
    Feature,
    Qualifiers,
    OrganismList,
    Other,
}

struct Frame {
    is_object: bool,
    role: Role,
    /// Key of the member currently being read (objects only).
    key: Key,
    /// Whether the next string in this object is a key.
    expecting_key: bool,
    /// Whether the next non-whitespace byte in this array starts an element.
    awaiting_element: bool,
    /// Number of elements seen (arrays only).
    elements: u64,
}

/// What the string currently being read is for.
#[derive(Clone, Copy, PartialEq, Eq)]
enum Capture {
    None,
    Key,
    Value(Role, Key),
}

#[derive(Default)]
struct FeatureState {
    is_region: bool,
    is_source: bool,
    organism: Option<String>,
}

#[derive(Default)]
struct RecordState {
    record: ScannedRecord,
    regions_len: Option<u64>,
    region_features: u64,
}

/// Incremental structural JSON scanner.
///
/// Only the document structure is tracked: strings are skipped with ``memchr``
/// and only the handful of keys and values needed for the records table are
/// captured. Byte offsets refer to the stream that is fed in, i.e. the
/// decompressed content for compressed files.
struct Scanner {
    stack: Vec<Frame>,
    offset: u64,
    in_string: bool,
    escape_pending: bool,
    capture: Capture,
    captured: Vec<u8>,
    capture_overflow: bool,
    root_closed: bool,
    record: Option<RecordState>,
    feature: Option<FeatureState>,
    result: FileScan,
}

#[derive(Debug)]
enum ScanError {
    Io(io::Error),
    Malformed(String),
}

impl From<io::Error> for ScanError {
    fn from(error: io::Error) -> Self {
        ScanError::Io(error)
    }
}

fn classify_key(role: Role, key: &[u8]) -> Key {
    match (role, key) {
        (Role::Root, b"records") => Key::Records,
        (Role::Root, b"version") => Key::Version,
        (Role::Root, b"input_file") => Key::InputFile,
        (Role::Record, b"id") => Key::Id,
        (Role::Record, b"description") => Key::Description,
        (Role::Record, b"features") => Key::Features,
        (Role::Record, b"regions") => Key::Regions,
        (Role::Feature, b"type") => Key::Type,
        (Role::Feature, b"qualifiers") => Key::Qualifiers,
        (Role::Qualifiers, b"organism") => Key::Organism,
        _ => Key::Other,
    }
}

/// Whether keys of an object with this role are worth capturing.
fn captures_keys(role: Role) -> bool {
    matches!(
        role,
        Role::Root | Role::Record | Role::Feature | Role::Qualifiers
    )
}

/// Whether a string value under ``(role, key)`` is worth capturing.
fn captures_value(role: Role, key: Key) -> bool {
    matches!(
        (role, key),
        (Role::Root, Key::Version)
            | (Role::Root, Key::InputFile)
            | (Role::Record, Key::Id)
            | (Role::Record, Key::Description)
            | (Role::Feature, Key::Type)
            | (Role::Qualifiers, Key::Organism)
            | (Role::OrganismList, _)
    )
}

/// Decode the raw bytes between a string's quotes.
fn decode_string(raw: &[u8]) -> Option<String> {
    if !raw.contains(&b'\\') {
        return String::from_utf8(raw.to_vec()).ok();
    }
    let mut quoted = Vec::with_capacity(raw.len() + 2);
    quoted.push(b'"');
    quoted.extend_from_slice(raw);
    quoted.push(b'"');
    serde_json::from_slice(&quoted).ok()
}

impl Scanner {
    fn new() -> Self {
        Scanner {
            stack: Vec::new(),
            offset: 0,
            in_string: false,
            escape_pending: false,
            capture: Capture::None,
            captured: Vec::new(),
            capture_overflow: false,
            root_closed: false,
            record: None,
            feature: None,
            result: FileScan::default(),
        }
    }

    fn malformed(&self, position: u64, message: &str) -> ScanError {
        ScanError::Malformed(format!("{} at byte {}", message, position))
    }

    fn feed(&mut self, chunk: &[u8]) -> Result<(), ScanError> {
        let mut i = 0;
        let len = chunk.len();
        while i < len {
            if self.in_string {
                i = self.scan_string(chunk, i);
                continue;
            }
            let byte = chunk[i];
            let position = self.offset + i as u64;
            i += 1;

            if byte.is_ascii_whitespace() {
                continue;
            }

            // Element counting: the first non-separator byte after ``[`` or
            // ``,`` starts an element of the enclosing array.
            if let Some(top) = self.stack.last_mut() {
                if !top.is_object {
                    match byte {
                        b',' => {
                            top.awaiting_element = true;
                            continue;
                        }
                        b']' => {}
                        _ => {
                            if top.awaiting_element {
                                top.awaiting_element = false;
                                top.elements += 1;
                            }
                        }
                    }
                }
            }

            match byte {
                b'"' => self.start_string(),
                b'{' => self.open(true, position)?,
                b'[' => self.open(false, position)?,
                b'}' => self.close(true, position)?,
                b']' => self.close(false, position)?,
                b',' => {
                    if let Some(top) = self.stack.last_mut() {
                        if top.is_object {
                            top.expecting_key = true;
                            top.key = Key::Other;
                        }
                    }
                }
                // ``:`` and scalar bytes carry no structure.
                _ => {}
            }
        }
        self.offset += len as u64;
        Ok(())
    }

    /// Consume string bytes from ``chunk[i..]``; returns the next index to scan.
    fn scan_string(&mut self, chunk: &[u8], mut i: usize) -> usize {
        let len = chunk.len();
        if self.escape_pending {
            self.escape_pending = false;
            self.capture_bytes(&chunk[i..i + 1]);
            return i + 1;
        }
        match memchr::memchr2(b'"', b'\\', &chunk[i..]) {
            None => {
                self.capture_bytes(&chunk[i..]);
                len
            }
            Some(found) => {
                let at = i + found;
                self.capture_bytes(&chunk[i..at]);
                if chunk[at] == b'\\' {
                    self.capture_bytes(&chunk[at..at + 1]);
                    i = at + 1;
                    if i < len {
                        self.capture_bytes(&chunk[i..i + 1]);
                        i + 1
                    } else {
                        self.escape_pending = true;
                        i
                    }
                } else {
                    self.in_string = false;
                    self.end_string();
                    at + 1
                }
            }
        }
    }

    fn capture_bytes(&mut self, bytes: &[u8]) {
        if self.capture == Capture::None || self.capture_overflow || bytes.is_empty() {
            return;
        }
        let limit = if self.capture == Capture::Key {
            MAX_KEY_LEN
        } else {
            MAX_VALUE_LEN
        };
        if self.captured.len() + bytes.len() > limit {
            self.capture_overflow = true;
            self.captured.clear();
        } else {
            self.captured.extend_from_slice(bytes);
        }
    }

    fn start_string(&mut self) {
        self.in_string = true;
        self.captured.clear();
        self.capture_overflow = false;
        self.capture = match self.stack.last() {
            Some(top) if top.is_object && top.expecting_key => {
                if captures_keys(top.role) {
                    Capture::Key
                } else {
                    Capture::None
                }
            }
            Some(top) if captures_value(top.role, top.key) => Capture::Value(top.role, top.key),
            _ => Capture::None,
        };
    }

    fn end_string(&mut self) {
        let capture = std::mem::replace(&mut self.capture, Capture::None);
        let Some(top) = self.stack.last_mut() else {
            return;
        };
        if top.is_object && top.expecting_key {
            top.expecting_key = false;
            top.key = if capture == Capture::Key && !self.capture_overflow {
                classify_key(top.role, &self.captured)
            } else {
                Key::Other
            };
            return;
        }
        let Capture::Value(role, key) = capture else {
            return;
        };
        if self.capture_overflow {
            return;
        }
        let Some(value) = decode_string(&self.captured) else {
            return;
        };
        match (role, key) {
            (Role::Root, Key::Version) => self.result.version = Some(value),
            (Role::Root, Key::InputFile) => self.result.input_file = Some(value),
            (Role::Record, Key::Id) => {
                if let Some(record) = self.record.as_mut() {
                    record.record.record_id = Some(value);
                }
            }
            (Role::Record, Key::Description) => {
                if let Some(record) = self.record.as_mut() {
                    record.record.description = Some(value);
                }
            }
            (Role::Feature, Key::Type) => {
                if let Some(feature) = self.feature.as_mut() {
                    feature.is_region = value == "region";
                    feature.is_source = value == "source";
                }
            }
            (Role::Qualifiers, Key::Organism) | (Role::OrganismList, _) => {
                if let Some(feature) = self.feature.as_mut() {
                    if feature.organism.is_none() {
                        feature.organism = Some(value);
                    }
                }
            }
            _ => {}
        }
    }

    fn open(&mut self, is_object: bool, position: u64) -> Result<(), ScanError> {
        let role = match self.stack.last() {
            None => {
                if self.root_closed {
                    return Err(self.malformed(position, "Unexpected content after JSON document"));
                }
                if is_object {
                    Role::Root
                } else {
                    Role::Other
                }
            }
            Some(parent) => {
                if parent.is_object && parent.expecting_key {
                    return Err(self.malformed(position, "Expected object key"));
                }
                match (parent.role, parent.key, is_object) {
                    (Role::Root, Key::Records, false) => Role::Records,
                    (Role::Records, _, true) => Role::Record,
                    (Role::Record, Key::Features, false) => Role::Features,
                    (Role::Record, Key::Regions, false) => Role::Regions,
                    (Role::Features, _, true) => Role::Feature,
                    (Role::Feature, Key::Qualifiers, true) => Role::Qualifiers,
                    (Role::Qualifiers, Key::Organism, false) => Role::OrganismList,
                    _ => Role::Other,
                }
            }
        };
        match role {
            Role::Record => {
                self.record = Some(RecordState {
                    record: ScannedRecord {
                        byte_start: position,
                        ..ScannedRecord::default()
                    },
                    ..RecordState::default()
                });
            }
            Role::Feature => self.feature = Some(FeatureState::default()),
            _ => {}
        }
        self.stack.push(Frame {
            is_object,
            role,
            key: Key::Other,
            expecting_key: is_object,
            awaiting_element: !is_object,
            elements: 0,
        });
        Ok(())
    }

    fn close(&mut self, is_object: bool, position: u64) -> Result<(), ScanError> {
        let frame = match self.stack.pop() {
            Some(frame) if frame.is_object == is_object => frame,
            _ => return Err(self.malformed(position, "Unbalanced brackets")),
        };
        match frame.role {
            Role::Record => {
                if let Some(mut state) = self.record.take() {
                    state.record.byte_end = position + 1;
                    state.record.region_count =
                        state.regions_len.unwrap_or(state.region_features);
                    self.result.records.push(state.record);
                }
            }
            Role::Features => {
                if let Some(record) = self.record.as_mut() {
                    record.record.feature_count = frame.elements;
                }
            }
            Role::Regions => {
                if let Some(record) = self.record.as_mut() {
                    record.regions_len = Some(frame.elements);
                }
            }
            Role::Feature => {
                if let (Some(feature), Some(record)) = (self.feature.take(), self.record.as_mut())
                {
                    if feature.is_region {
                        record.region_features += 1;
                    }
                    if feature.is_source && record.record.organism.is_none() {
                        record.record.organism = feature.organism;
                    }
                }
            }
            _ => {}
        }
        if self.stack.is_empty() {
            self.root_closed = true;
        }
        Ok(())
    }

    fn finish(self) -> Result<FileScan, ScanError> {
        if self.in_string || !self.stack.is_empty() {
            return Err(ScanError::Malformed(format!(
                "Unexpected end of JSON at byte {}",
                self.offset
            )));
        }
        Ok(self.result)
    }
}

/// Open ``path`` and wrap it in a decompressor chosen by its extension.
fn open_stream(path: &Path) -> io::Result<Box<dyn Read>> {
    let file = File::open(path)?;
    let name = path.to_string_lossy();
    Ok(if name.ends_with(".gz") {
        Box::new(flate2::read::MultiGzDecoder::new(io::BufReader::new(file)))
    } else if name.ends_with(".bz2") {
        Box::new(bzip2::read::MultiBzDecoder::new(io::BufReader::new(file)))
    } else {
        Box::new(file)
    })
}

fn scan_path(path: &Path) -> Result<FileScan, ScanError> {
    let mut stream = open_stream(path)?;
    let mut scanner = Scanner::new();
    let mut chunk = vec![0u8; CHUNK_SIZE];
    loop {
        let read = match stream.read(&mut chunk) {
            Ok(0) => break,
            Ok(read) => read,
            Err(error) if error.kind() == io::ErrorKind::Interrupted => continue,
            Err(error) => return Err(error.into()),
        };
        scanner.feed(&chunk[..read])?;
    }
    scanner.finish()
}

/// Scan an antiSMASH JSON file in a single streaming pass.
///
/// ``.json.gz`` and ``.json.bz2`` files are decompressed on the fly; byte
/// offsets always refer to the decompressed content. The GIL is released while
/// scanning so several files can be scanned from Python threads in parallel.
///
/// Args:
///     file_path: Path to the JSON file to scan
///
/// Returns:
///     FileScan with the top-level version/input_file and one ScannedRecord
///     per element of the top-level ``records`` array
///
/// Raises:
///     OSError: the file cannot be read or decompressed
///     ValueError: the file is not structurally valid JSON
#[pyfunction]
fn scan_file(py: Python<'_>, file_path: PathBuf) -> PyResult<FileScan> {
    py.allow_threads(|| scan_path(&file_path))
        .map_err(|error| match error {
            ScanError::Io(error) => PyIOError::new_err(format!(
                "Failed to read {}: {}",
                file_path.display(),
                error
            )),
            ScanError::Malformed(message) => PyValueError::new_err(format!(
                "Malformed JSON in {}: {}",
                file_path.display(),
                message
            )),
        })
}

/// Fast record-boundary scanning for antiSMASH JSON files, implemented in Rust.
#[pymodule]
fn bgc_scanner(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(scan_file, m)?)?;
    m.add_class::<FileScan>()?;
    m.add_class::<ScannedRecord>()?;
    Ok(())
}
