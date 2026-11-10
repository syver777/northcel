//! Python binding: `northcel_vello.render_frame(bytes, out_path)` and
//! `northcel_vello.render_sequence(paths, out_dir)`.
//!
//! The Python reference stays the exact tier; this module renders NCIR v2 with
//! Vello/wgpu and reports per-frame receipts as JSON.

use pyo3::prelude::*;

fn stats_json(stats: &ncel_vello::FrameStats) -> String {
    serde_json::json!({
        "width": stats.width,
        "height": stats.height,
        "paints": stats.paints,
        "scene_ms": stats.scene_ms,
        "render_ms": stats.render_ms,
        "readback_ms": stats.readback_ms,
        "grain_ms": stats.grain_ms,
        "png_ms": stats.png_ms,
        "rgba_sha256": stats.rgba_sha256,
    })
    .to_string()
}

#[pyfunction]
fn render_frame(data: Vec<u8>, out: String) -> PyResult<String> {
    let n = ncel_vello::ncir::parse(&data).map_err(pyo3::exceptions::PyValueError::new_err)?;
    let mut gpu = ncel_vello::Gpu::new().map_err(pyo3::exceptions::PyRuntimeError::new_err)?;
    let stats = ncel_vello::render_one(&mut gpu, &n, std::path::Path::new(&out))
        .map_err(pyo3::exceptions::PyRuntimeError::new_err)?;
    Ok(stats_json(&stats))
}

#[pyfunction]
fn render_sequence(frames: Vec<String>, out_dir: String) -> PyResult<String> {
    let paths: Vec<std::path::PathBuf> = frames.iter().map(std::path::PathBuf::from).collect();
    let stats = ncel_vello::render_sequence(&paths, std::path::Path::new(&out_dir))
        .map_err(pyo3::exceptions::PyRuntimeError::new_err)?;
    let rows: Vec<String> = stats.iter().map(stats_json).collect();
    Ok(format!("[{}]", rows.join(",")))
}

#[pyfunction]
fn adapter() -> PyResult<String> {
    let gpu = ncel_vello::Gpu::new()
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e))?;
    Ok(gpu.adapter().to_string())
}

#[pymodule]
fn northcel_vello(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(render_frame, m)?)?;
    m.add_function(wrap_pyfunction!(render_sequence, m)?)?;
    m.add_function(wrap_pyfunction!(adapter, m)?)?;
    m.add("__version__", env!("CARGO_PKG_VERSION"))?;
    Ok(())
}
