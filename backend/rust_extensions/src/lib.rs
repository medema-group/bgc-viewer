use pyo3::prelude::*;
use std::fs::File;
use std::io::{BufReader, Read};
use std::path::PathBuf;

/// Find JSON record boundaries in AntiSMASH output files.
/// 
/// This function scans a JSON file to find the byte positions of individual
/// records within the "records" array. It's optimized for speed and handles
/// large files (2GB+) efficiently.
/// 
/// Args:
///     file_path: Path to the JSON file to scan
/// 
/// Returns:
///     List of tuples (start_byte, end_byte) for each record
#[pyfunction]
fn scan_records(file_path: PathBuf) -> PyResult<Vec<(u64, u64)>> {
    let file = File::open(&file_path)
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(
            format!("Failed to open file: {}", e)
        ))?;
    
    let mut reader = BufReader::with_capacity(8 * 1024 * 1024, file); // 8MB buffer
    let mut content = Vec::new();
    reader.read_to_end(&mut content)
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(
            format!("Failed to read file: {}", e)
        ))?;
    
    // Find the "records" array
    let records_pattern = b"\"records\"";
    let records_pos = content.windows(records_pattern.len())
        .position(|window| window == records_pattern)
        .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>(
            "Could not find 'records' array in JSON file"
        ))?;
    
    // Find the opening bracket of the records array
    let array_start = content[records_pos..]
        .iter()
        .position(|&b| b == b'[')
        .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>(
            "Could not find opening bracket for 'records' array"
        ))?;
    
    let start_pos = records_pos + array_start + 1;
    
    // Scan for record boundaries
    let mut positions = Vec::new();
    let mut pos = start_pos;
    let mut brace_depth = 0;
    let mut record_start: Option<usize> = None;
    let mut in_string = false;
    let mut escape_next = false;
    
    while pos < content.len() {
        let byte = content[pos];
        
        if escape_next {
            escape_next = false;
            pos += 1;
            continue;
        }
        
        if byte == b'\\' {
            escape_next = true;
            pos += 1;
            continue;
        }
        
        if byte == b'"' {
            in_string = !in_string;
            pos += 1;
            continue;
        }
        
        if in_string {
            pos += 1;
            continue;
        }
        
        match byte {
            b'{' => {
                if brace_depth == 0 {
                    record_start = Some(pos);
                }
                brace_depth += 1;
            }
            b'}' => {
                brace_depth -= 1;
                if brace_depth == 0 {
                    if let Some(start) = record_start {
                        positions.push((start as u64, (pos + 1) as u64));
                        record_start = None;
                    }
                }
            }
            b']' if brace_depth == 0 => {
                break;
            }
            _ => {}
        }
        
        pos += 1;
    }
    
    Ok(positions)
}

/// A Python module implemented in Rust for fast JSON record scanning.
#[pymodule]
fn bgc_scanner(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(scan_records, m)?)?;
    Ok(())
}
