//! Vello/wgpu rendering of a flattened NorthCel paint list.
//!
//! Semantics mapped from the Python reference renderer:
//! * paper -> `RenderParams::base_color` (opaque), grain applied afterwards in
//!   CPU with the reference `sin` formula;
//! * each layer's rings -> one even-odd `BezPath` (matching the reference
//!   even-odd parity across all rings of a layer);
//! * layer `opacity` -> brush alpha; group opacity -> nested Vello blend layers;
//! * a single resolved clip shape -> an even-odd clip layer;
//! * multiple clip shapes -> approximate NonZero union (reported limitation);
//! * paint order -> scene draw order, back to front.
//!
//! This is deliberately a prototype: Vello's analytic area AA is not the
//! reference's 4x4 subpixel box integration, so edge pixels are expected to
//! differ.

use crate::fixture::Fixture;
use std::fs::File;
use std::io::BufWriter;
use std::path::{Path, PathBuf};
use std::time::Instant;
use vello::{
    AaConfig, AaSupport, RenderParams, Renderer, RendererOptions, Scene,
    kurbo::{Affine, BezPath, Rect},
    peniko::{BlendMode, Color, Fill},
};

pub struct RenderConfig {
    pub cpu: bool,
    pub repeat: usize,
    pub write_pass_files: bool,
}

impl Default for RenderConfig {
    fn default() -> Self {
        Self {
            cpu: false,
            repeat: 1,
            write_pass_files: true,
        }
    }
}

pub struct Timings {
    pub init_ms: f64,
    pub scene_ms: f64,
    pub pass_render_ms: Vec<f64>,
    pub pass_readback_ms: Vec<f64>,
    pub pass_grain_ms: Vec<f64>,
    pub pass_png_ms: Vec<f64>,
    pub total_ms: f64,
}

pub struct PassOutput {
    pub index: usize,
    pub path: PathBuf,
    pub png_bytes: u64,
    pub fnv1a64: u64,
    pub rgba: Vec<u8>,
}

pub struct RenderReport {
    pub adapter: serde_json::Value,
    pub timings: Timings,
    pub passes: Vec<PassOutput>,
    pub pass_diffs: Vec<PassDiff>,
    pub identical: bool,
    pub width: u32,
    pub height: u32,
    pub notes: Vec<String>,
}

/// A byte-level difference between one pass and the first pass.
pub struct PassDiff {
    pub index: usize,
    pub differing_bytes: usize,
    pub differing_pixels: usize,
    pub max_channel_delta: u8,
}

pub fn pass_diff(first: &[u8], other: &[u8]) -> (usize, usize, u8) {
    let mut bytes = 0usize;
    let mut pixels = 0usize;
    let mut max_delta = 0u8;
    for (pa, pb) in first
        .as_chunks::<4>()
        .0
        .iter()
        .zip(other.as_chunks::<4>().0)
    {
        let mut pixel_differs = false;
        for (&a, &b) in pa.iter().zip(pb.iter()) {
            let delta = a.abs_diff(b);
            if delta != 0 {
                bytes += 1;
                max_delta = max_delta.max(delta);
                pixel_differs = true;
            }
        }
        if pixel_differs {
            pixels += 1;
        }
    }
    (bytes, pixels, max_delta)
}

pub fn render_fixture(
    fixture: &Fixture,
    out_path: &Path,
    config: &RenderConfig,
) -> Result<RenderReport, String> {
    let total_start = Instant::now();
    let width = fixture.width;
    let height = fixture.height;

    // ---------------------------------------------------------------- device
    let t = Instant::now();
    let instance =
        wgpu::Instance::new(wgpu::InstanceDescriptor::new_without_display_handle().with_env());
    let adapter = pollster::block_on(instance.request_adapter(&wgpu::RequestAdapterOptions {
        power_preference: wgpu::PowerPreference::HighPerformance,
        ..Default::default()
    }))
    .map_err(|e| format!("no wgpu adapter: {e}"))?;
    let info = adapter.get_info();
    let adapter_json = serde_json::json!({
        "name": info.name,
        "vendor": info.vendor,
        "device": info.device,
        "device_type": format!("{:?}", info.device_type),
        "driver": info.driver,
        "driver_info": info.driver_info,
        "backend": format!("{:?}", info.backend),
    });
    let (device, queue) = pollster::block_on(adapter.request_device(&wgpu::DeviceDescriptor {
        label: Some("ncel-vello-device"),
        required_features: wgpu::Features::empty(),
        required_limits: wgpu::Limits::default(),
        experimental_features: wgpu::ExperimentalFeatures::disabled(),
        memory_hints: wgpu::MemoryHints::Performance,
        trace: wgpu::Trace::Off,
    }))
    .map_err(|e| format!("cannot create wgpu device: {e}"))?;

    let mut renderer = Renderer::new(
        &device,
        RendererOptions {
            use_cpu: config.cpu,
            antialiasing_support: AaSupport::area_only(),
            ..Default::default()
        },
    )
    .map_err(|e| format!("cannot create Vello renderer: {e:?}"))?;
    let init_ms = ms(t.elapsed());

    // ----------------------------------------------------------------- scene
    let t = Instant::now();
    let (scene, scene_notes) = build_scene(fixture);
    let scene_ms = ms(t.elapsed());

    let paper = fixture.paper.rgb;
    let base_color = Color::new([
        paper[0] as f32 / 255.0,
        paper[1] as f32 / 255.0,
        paper[2] as f32 / 255.0,
        1.0,
    ]);

    let texture = device.create_texture(&wgpu::TextureDescriptor {
        label: Some("ncel-vello-target"),
        size: wgpu::Extent3d {
            width,
            height,
            depth_or_array_layers: 1,
        },
        mip_level_count: 1,
        sample_count: 1,
        dimension: wgpu::TextureDimension::D2,
        format: wgpu::TextureFormat::Rgba8Unorm,
        usage: wgpu::TextureUsages::STORAGE_BINDING
            | wgpu::TextureUsages::COPY_SRC
            | wgpu::TextureUsages::RENDER_ATTACHMENT,
        view_formats: &[],
    });
    let view = texture.create_view(&wgpu::TextureViewDescriptor::default());

    let unpadded_bytes_per_row = width * 4;
    let padded_bytes_per_row = unpadded_bytes_per_row.div_ceil(wgpu::COPY_BYTES_PER_ROW_ALIGNMENT)
        * wgpu::COPY_BYTES_PER_ROW_ALIGNMENT;
    let buffer = device.create_buffer(&wgpu::BufferDescriptor {
        label: Some("ncel-vello-readback"),
        size: (padded_bytes_per_row as u64) * (height as u64),
        usage: wgpu::BufferUsages::COPY_DST | wgpu::BufferUsages::MAP_READ,
        mapped_at_creation: false,
    });

    let mut pass_render_ms = Vec::with_capacity(config.repeat);
    let mut pass_readback_ms = Vec::with_capacity(config.repeat);
    let mut pass_grain_ms = Vec::with_capacity(config.repeat);
    let mut pass_png_ms = Vec::with_capacity(config.repeat);
    let mut passes: Vec<PassOutput> = Vec::with_capacity(config.repeat);

    let out_dir = out_path.parent().unwrap_or_else(|| Path::new("."));
    std::fs::create_dir_all(out_dir)
        .map_err(|e| format!("cannot create output directory {}: {e}", out_dir.display()))?;

    for pass in 0..config.repeat.max(1) {
        // -------------------------------------------------------------- draw
        let t = Instant::now();
        renderer
            .render_to_texture(
                &device,
                &queue,
                &scene,
                &view,
                &RenderParams {
                    base_color,
                    width,
                    height,
                    antialiasing_method: AaConfig::Area,
                },
            )
            .map_err(|e| format!("Vello render failed: {e:?}"))?;
        pass_render_ms.push(ms(t.elapsed()));

        // ---------------------------------------------------------- readback
        let t = Instant::now();
        let mut encoder = device.create_command_encoder(&wgpu::CommandEncoderDescriptor {
            label: Some("ncel-vello-copy"),
        });
        encoder.copy_texture_to_buffer(
            wgpu::TexelCopyTextureInfo {
                texture: &texture,
                mip_level: 0,
                origin: wgpu::Origin3d::ZERO,
                aspect: wgpu::TextureAspect::All,
            },
            wgpu::TexelCopyBufferInfo {
                buffer: &buffer,
                layout: wgpu::TexelCopyBufferLayout {
                    offset: 0,
                    bytes_per_row: Some(padded_bytes_per_row),
                    rows_per_image: Some(height),
                },
            },
            wgpu::Extent3d {
                width,
                height,
                depth_or_array_layers: 1,
            },
        );
        queue.submit(Some(encoder.finish()));

        let slice = buffer.slice(..);
        let (sender, receiver) = std::sync::mpsc::channel();
        slice.map_async(wgpu::MapMode::Read, move |result| {
            let _ = sender.send(result);
        });
        device
            .poll(wgpu::PollType::wait_indefinitely())
            .map_err(|e| format!("device poll failed: {e}"))?;
        receiver
            .recv()
            .map_err(|e| format!("readback callback dropped: {e}"))?
            .map_err(|e| format!("buffer map failed: {e}"))?;

        let mut rgba = Vec::with_capacity((width * height * 4) as usize);
        {
            let mapped = slice
                .get_mapped_range()
                .map_err(|e| format!("buffer view failed: {e}"))?;
            for row in 0..height as usize {
                let start = row * padded_bytes_per_row as usize;
                let end = start + unpadded_bytes_per_row as usize;
                rgba.extend_from_slice(&mapped[start..end]);
            }
        }
        buffer.unmap();
        pass_readback_ms.push(ms(t.elapsed()));

        // -------------------------------------------------------------- grain
        let t = Instant::now();
        if fixture.paper.grain > 0.0 {
            apply_grain(&mut rgba, width, height, fixture.seed, fixture.paper.grain);
        }
        pass_grain_ms.push(ms(t.elapsed()));

        // ---------------------------------------------------------------- png
        let t = Instant::now();
        let pass_path = if pass == 0 {
            out_path.to_path_buf()
        } else if config.write_pass_files {
            out_path.with_file_name(format!(
                "{}.pass{}",
                out_path
                    .file_name()
                    .map(|s| s.to_string_lossy().to_string())
                    .unwrap_or_else(|| "pass.png".into()),
                pass
            ))
        } else {
            out_path.to_path_buf()
        };
        if pass == 0 || config.write_pass_files {
            write_png(&pass_path, &rgba, width, height)?;
        }
        let png_bytes = if pass == 0 || config.write_pass_files {
            std::fs::metadata(&pass_path).map(|m| m.len()).unwrap_or(0)
        } else {
            0
        };
        pass_png_ms.push(ms(t.elapsed()));

        passes.push(PassOutput {
            index: pass,
            path: pass_path,
            png_bytes,
            fnv1a64: fnv1a64(&rgba),
            rgba,
        });
    }

    let identical = passes.windows(2).all(|pair| pair[0].rgba == pair[1].rgba);
    let pass_diffs: Vec<PassDiff> = passes
        .iter()
        .skip(1)
        .map(|pass| {
            let (differing_bytes, differing_pixels, max_channel_delta) =
                pass_diff(&passes[0].rgba, &pass.rgba);
            PassDiff {
                index: pass.index,
                differing_bytes,
                differing_pixels,
                max_channel_delta,
            }
        })
        .collect();
    let total_ms = ms(total_start.elapsed());

    let mut notes = fixture.limitation_notes();
    notes.extend(scene_notes);
    notes.push(
        "render_passes measures CPU encoding/submission, not GPU completion; add readback_passes for completed render+readback wall time".to_string(),
    );
    notes.push(
        "Vello uses analytic area AA; the reference integrates a 4x4 subpixel grid.".to_string(),
    );
    if config.cpu {
        notes.push(
            "RendererOptions::use_cpu = true (coarse stages on CPU; fine raster still GPU)"
                .to_string(),
        );
    }

    Ok(RenderReport {
        adapter: adapter_json,
        timings: Timings {
            init_ms,
            scene_ms,
            pass_render_ms,
            pass_readback_ms,
            pass_grain_ms,
            pass_png_ms,
            total_ms,
        },
        passes,
        pass_diffs,
        identical,
        width,
        height,
        notes,
    })
}

fn build_scene(fixture: &Fixture) -> (Scene, Vec<String>) {
    let mut scene = Scene::new();
    let mut notes = Vec::new();
    let canvas = Rect::new(0.0, 0.0, fixture.width as f64, fixture.height as f64);
    let mut group_stack: Vec<u32> = Vec::new();
    let mut skipped = 0usize;
    let mut clipped = 0usize;

    for layer in &fixture.layers {
        // The reference does not treat an invisible paint as an event: it does
        // not open/close group scopes and paints nothing.
        if layer.rings.is_empty()
            || layer.opacity <= 0.0
            || layer
                .group_opacity
                .iter()
                .any(|(_, opacity)| *opacity <= 0.0)
        {
            skipped += 1;
            continue;
        }

        // Close scopes this paint is not inside, then open its new scopes.
        let shared = shared_group_prefix(&group_stack, &layer.group_opacity);
        while group_stack.len() > shared {
            scene.pop_layer();
            group_stack.pop();
        }
        for (gid, opacity) in layer.group_opacity.iter().skip(group_stack.len()) {
            scene.push_layer(
                Fill::NonZero,
                BlendMode::default(),
                (*opacity as f32).clamp(0.0, 1.0),
                Affine::IDENTITY,
                &canvas,
            );
            group_stack.push(*gid);
        }

        let path = rings_to_path(&layer.rings);
        let clip_path = if layer.clip_shapes.is_empty() {
            None
        } else {
            let mut all_rings = Vec::new();
            for shape in &layer.clip_shapes {
                all_rings.extend(shape.iter().cloned());
            }
            Some(rings_to_path(&all_rings))
        };
        if let Some(clip) = &clip_path {
            clipped += 1;
            scene.push_clip_layer(
                if layer.clip_shapes.len() == 1 {
                    Fill::EvenOdd
                } else {
                    Fill::NonZero
                },
                Affine::IDENTITY,
                clip,
            );
        }

        let color = Color::new([
            layer.color[0] as f32 / 255.0,
            layer.color[1] as f32 / 255.0,
            layer.color[2] as f32 / 255.0,
            (layer.opacity as f32).clamp(0.0, 1.0),
        ]);
        scene.fill(Fill::EvenOdd, Affine::IDENTITY, color, None, &path);

        if layer.clip_shapes.len() > 1 {
            notes.push(format!(
                "layer {:?} has {} clip shapes; merged as one NonZero union path",
                layer.name,
                layer.clip_shapes.len()
            ));
        }

        if clip_path.is_some() {
            scene.pop_layer();
        }
    }
    while !group_stack.is_empty() {
        scene.pop_layer();
        group_stack.pop();
    }
    if skipped > 0 {
        notes.push(format!(
            "{skipped} invisible paint(s) skipped exactly like the reference paint loop"
        ));
    }
    if clipped > 0 {
        notes.push(format!(
            "{clipped} paint(s) clipped by resolved clip shapes"
        ));
    }
    (scene, notes)
}

fn rings_to_path(rings: &[Vec<[f64; 2]>]) -> BezPath {
    let mut path = BezPath::new();
    for ring in rings {
        if ring.len() < 3 {
            continue;
        }
        path.move_to((ring[0][0], ring[0][1]));
        for point in &ring[1..] {
            path.line_to((point[0], point[1]));
        }
        path.close_path();
    }
    path
}

/// Only the common ancestor prefix may stay open across successive paints.
fn shared_group_prefix(stack: &[u32], groups: &[(u32, f64)]) -> usize {
    stack
        .iter()
        .zip(groups)
        .take_while(|(open, (next, _))| **open == *next)
        .count()
}

/// Reference paper grain (`python/northcel/renderer.py`, `_rasterize_paint`).
fn apply_grain(rgba: &mut [u8], width: u32, height: u32, seed: i64, grain: f64) {
    let seed32 = seed as u32;
    let seed_term = seed32.wrapping_mul(1_442_695_041);
    for y in 0..height {
        for x in 0..width {
            let idx = ((y as usize * width as usize) + x as usize) * 4;
            let h = x
                .wrapping_mul(374_761_393)
                .wrapping_add(y.wrapping_mul(668_265_263))
                .wrapping_add(seed_term);
            let noise = ((h as f64) * 0.0001).sin() * 0.5 * (grain * 255.0);
            for c in 0..3 {
                let value = rgba[idx + c] as f64 + noise;
                rgba[idx + c] = (value.clamp(0.0, 255.0) + 0.5).floor() as u8;
            }
        }
    }
}

fn write_png(path: &Path, rgba: &[u8], width: u32, height: u32) -> Result<(), String> {
    let file =
        File::create(path).map_err(|e| format!("cannot create PNG {}: {e}", path.display()))?;
    let writer = BufWriter::new(file);
    let mut encoder = png::Encoder::new(writer, width, height);
    encoder.set_color(png::ColorType::Rgba);
    encoder.set_depth(png::BitDepth::Eight);
    let mut writer = encoder
        .write_header()
        .map_err(|e| format!("cannot write PNG header {}: {e}", path.display()))?;
    writer
        .write_image_data(rgba)
        .map_err(|e| format!("cannot write PNG data {}: {e}", path.display()))?;
    Ok(())
}

pub fn fnv1a64(bytes: &[u8]) -> u64 {
    let mut hash: u64 = 0xcbf2_9ce4_8422_2325;
    for &byte in bytes {
        hash ^= byte as u64;
        hash = hash.wrapping_mul(0x0000_0100_0000_01b3);
    }
    hash
}

fn ms(duration: std::time::Duration) -> f64 {
    duration.as_secs_f64() * 1000.0
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn group_scope_survives_consecutive_paints() {
        assert_eq!(shared_group_prefix(&[1], &[(1, 0.5)]), 1);
        assert_eq!(shared_group_prefix(&[1, 2], &[(1, 0.5), (2, 0.6)]), 2);
    }

    #[test]
    fn group_scope_closes_only_to_common_ancestor() {
        assert_eq!(shared_group_prefix(&[1, 2], &[(1, 0.5), (3, 0.6)]), 1);
        assert_eq!(shared_group_prefix(&[1, 2], &[(1, 0.5)]), 1);
        assert_eq!(shared_group_prefix(&[1, 2], &[(3, 0.5), (2, 0.6)]), 0);
        assert_eq!(shared_group_prefix(&[1], &[]), 0);
        assert_eq!(shared_group_prefix(&[], &[(1, 0.5)]), 0);
    }

    #[test]
    fn raw_rgba_diff_counts_pixels_and_channels() {
        assert_eq!(pass_diff(&[0, 1, 2, 255], &[0, 1, 2, 255]), (0, 0, 0));
        assert_eq!(
            pass_diff(
                &[0, 1, 2, 255, 10, 20, 30, 255],
                &[1, 1, 5, 255, 10, 20, 29, 255]
            ),
            (3, 2, 3)
        );
    }

    #[test]
    fn grain_preserves_alpha_and_seed_wraps() {
        let mut a = vec![100, 120, 140, 255];
        let mut b = a.clone();
        apply_grain(&mut a, 1, 1, -1, 0.008);
        apply_grain(&mut b, 1, 1, u32::MAX as i64, 0.008);
        assert_eq!(a, b);
        assert_eq!(a[3], 255);
    }

    #[test]
    fn rings_are_closed_separately_for_even_odd_fill() {
        let ring = vec![[0.0, 0.0], [4.0, 0.0], [4.0, 4.0]];
        let path = rings_to_path(&[ring.clone(), ring]);
        assert_eq!(path.elements().len(), 8);
        assert!(matches!(
            path.elements()[3],
            vello::kurbo::PathEl::ClosePath
        ));
        assert!(matches!(
            path.elements()[7],
            vello::kurbo::PathEl::ClosePath
        ));
    }
}
