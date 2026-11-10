//! ncel-vello -- Phase 4 NorthCel Vello backend prototype.
//!
//! Renders one flattened NorthCel paint-list fixture with Vello on wgpu.
//! Timings include adapter/device/renderer init, scene build, each GPU render,
//! readback and PNG encode. `--repeat N` renders the same frame N times and
//! compares the raw RGBA buffers.

mod fixture;
mod render;

use fixture::Fixture;
use render::{RenderConfig, render_fixture};
use std::path::PathBuf;

const DEFAULT_FIXTURE: &str = "fixtures/skyline_1080.paintlist.json";
const DEFAULT_OUT: &str = "out/vello_1080_f0000.png";

fn main() {
    if let Err(err) = run() {
        eprintln!("ncel-vello: {err}");
        std::process::exit(1);
    }
}

fn run() -> Result<(), String> {
    // NCIR v2 backend (tools 0.7): one frame or a directory of frames.
    let argv: Vec<String> = std::env::args().skip(1).collect();
    if let Some(pos) = argv.iter().position(|a| a == "--ncir") {
        let input = argv.get(pos + 1).ok_or("--ncir needs a path")?;
        let out = argv
            .iter()
            .position(|a| a == "--out")
            .and_then(|i| argv.get(i + 1))
            .map(PathBuf::from)
            .unwrap_or_else(|| PathBuf::from("out/ncir.png"));
        let stats = ncel_vello::render_file(&PathBuf::from(input), &out)?;
        println!(
            "{{\"ncir\": {}, \"width\": {}, \"height\": {}, \"paints\": {}, \"sha256\": \"{}\"}}",
            serde_json::json!(input),
            stats.width,
            stats.height,
            stats.paints,
            stats.rgba_sha256
        );
        return Ok(());
    }
    if let Some(pos) = argv.iter().position(|a| a == "--ncir-dir") {
        let input = argv.get(pos + 1).ok_or("--ncir-dir needs a directory")?;
        let out = argv
            .iter()
            .position(|a| a == "--out-dir")
            .and_then(|i| argv.get(i + 1))
            .map(PathBuf::from)
            .unwrap_or_else(|| PathBuf::from("out/ncir"));
        let mut files: Vec<PathBuf> = std::fs::read_dir(input)
            .map_err(|e| format!("cannot read {input}: {e}"))?
            .filter_map(|e| e.ok().map(|e| e.path()))
            .filter(|p| p.extension().map(|x| x == "ncir").unwrap_or(false))
            .collect();
        files.sort();
        let started = std::time::Instant::now();
        let stats = ncel_vello::render_sequence(&files, &out)?;
        let total_ms = started.elapsed().as_secs_f64() * 1000.0;
        println!(
            "{{\"ncir_dir\": {}, \"frames\": {}, \"total_ms\": {:.1}}}",
            serde_json::json!(input),
            stats.len(),
            total_ms
        );
        return Ok(());
    }
    let manifest = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let mut fixture_path = manifest.join(DEFAULT_FIXTURE);
    let mut out_path = manifest.join(DEFAULT_OUT);
    let mut config = RenderConfig {
        repeat: 1,
        ..Default::default()
    };
    let mut json = false;
    let mut args = std::env::args().skip(1);
    while let Some(arg) = args.next() {
        match arg.as_str() {
            "--fixture" => {
                fixture_path = PathBuf::from(args.next().ok_or("--fixture needs a path")?);
            }
            "--out" => {
                out_path = PathBuf::from(args.next().ok_or("--out needs a path")?);
            }
            "--repeat" => {
                config.repeat = args
                    .next()
                    .ok_or("--repeat needs a count")?
                    .parse()
                    .map_err(|e| format!("invalid --repeat: {e}"))?;
            }
            "--cpu" => config.cpu = true,
            "--no-pass-files" => config.write_pass_files = false,
            "--json" => json = true,
            "-h" | "--help" => {
                println!(
                    "usage: ncel-vello [--fixture FILE] [--out FILE] [--repeat N] [--cpu] [--no-pass-files] [--json]\n\
                     \n\
                     Renders one flattened NorthCel paint-list fixture with Vello/wgpu.\n\
                     Default fixture: {DEFAULT_FIXTURE}\n\
                     Default output:  {DEFAULT_OUT}"
                );
                return Ok(());
            }
            other => return Err(format!("unknown argument {other:?}; try --help")),
        }
    }

    if config.repeat == 0 {
        return Err("--repeat must be at least 1".into());
    }
    let fixture = Fixture::load(&fixture_path)?;
    let report = render_fixture(&fixture, &out_path, &config)?;

    let summary = serde_json::json!({
        "tool": "ncel-vello",
        "status": "prototype",
        "fixture": fixture_path,
        "source": fixture.source,
        "frame_index": fixture.frame_index,
        "width": report.width,
        "height": report.height,
        "cpu_stages": config.cpu,
        "adapter": report.adapter,
        "layers": fixture.layer_count(),
        "rings": fixture.ring_count(),
        "points": fixture.point_count(),
        "clip_points": fixture.clip_point_count(),
        "timing_ms": {
            "init": report.timings.init_ms,
            "scene_build": report.timings.scene_ms,
            "render_passes": report.timings.pass_render_ms,
            "readback_passes": report.timings.pass_readback_ms,
            "render_including_readback_passes": report.timings.pass_render_ms.iter()
                .zip(&report.timings.pass_readback_ms).map(|(render, readback)| render + readback)
                .collect::<Vec<_>>(),
            "grain_passes": report.timings.pass_grain_ms,
            "png_passes": report.timings.pass_png_ms,
            "total": report.timings.total_ms,
        },
        "repeat": config.repeat.max(1),
        "deterministic_in_process": report.identical,
        "pass_diff_from_first": report.pass_diffs.iter().map(|d| serde_json::json!({
            "pass": d.index,
            "differing_bytes": d.differing_bytes,
            "differing_pixels": d.differing_pixels,
            "max_channel_delta": d.max_channel_delta,
        })).collect::<Vec<_>>(),
        "passes": report.passes.iter().map(|p| serde_json::json!({
            "index": p.index,
            "path": p.path,
            "png_bytes": p.png_bytes,
            "fnv1a64": format!("0x{:016x}", p.fnv1a64),
        })).collect::<Vec<_>>(),
        "fixture_notes": fixture.notes,
        "notes": report.notes,
    });

    if json {
        println!(
            "{}",
            serde_json::to_string_pretty(&summary)
                .map_err(|e| format!("cannot encode JSON: {e}"))?
        );
    } else {
        let adapter = &report.adapter;
        println!(
            "ncel-vello (prototype)  {:.0}x{:.0}  {} layers / {} rings / {} points",
            report.width as f64,
            report.height as f64,
            fixture.layer_count(),
            fixture.ring_count(),
            fixture.point_count()
        );
        println!(
            "adapter: {} [{}] ({})",
            adapter["name"].as_str().unwrap_or("?"),
            adapter["backend"].as_str().unwrap_or("?"),
            adapter["device_type"].as_str().unwrap_or("?")
        );
        println!(
            "timing: init {:.2} ms | scene {:.2} ms | render {} | readback {} | png {} | total {:.2} ms",
            report.timings.init_ms,
            report.timings.scene_ms,
            fmt_list(&report.timings.pass_render_ms),
            fmt_list(&report.timings.pass_readback_ms),
            fmt_list(&report.timings.pass_png_ms),
            report.timings.total_ms,
        );
        for pass in &report.passes {
            println!(
                "pass {}: {} ({:.0} bytes, fnv1a64 0x{:016x})",
                pass.index,
                pass.path.display(),
                pass.png_bytes,
                pass.fnv1a64
            );
        }
        println!(
            "determinism (in-process, {} pass{}): {}",
            report.passes.len(),
            if report.passes.len() == 1 { "" } else { "es" },
            if report.identical {
                "identical raw RGBA"
            } else {
                "DIFFERENT raw RGBA"
            }
        );
        for diff in &report.pass_diffs {
            println!(
                "  pass {} vs pass 0: {} differing pixels, {} differing bytes, max channel delta {}",
                diff.index, diff.differing_pixels, diff.differing_bytes, diff.max_channel_delta
            );
        }
        for note in &report.notes {
            println!("note: {note}");
        }
    }
    Ok(())
}

fn fmt_list(values: &[f64]) -> String {
    values
        .iter()
        .map(|v| format!("{v:.2} ms"))
        .collect::<Vec<_>>()
        .join(", ")
}
