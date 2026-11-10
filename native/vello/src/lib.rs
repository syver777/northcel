//! NorthCel Vello backend (tools 0.7): NCIR v2 -> Vello/wgpu frames.
//!
//! This is the tolerance tier: Vello's analytic area AA differs from the
//! reference's `aa x aa` subpixel box integration at edges, so the reference
//! stays the exact tier. Everything above the pixel is normative: even-odd
//! rings, paint order, group opacity scopes, clip rings, per-paint opacity and
//! the paper grain formula all come from NCIR v2.

pub mod ncir;

use std::path::{Path, PathBuf};
use std::time::Instant;

use vello::{
    AaConfig, AaSupport, RenderParams, Renderer, RendererOptions, Scene,
    kurbo::{Affine, BezPath, Rect},
    peniko::{BlendMode, Color, Fill},
};

pub use ncir::Ncir;

pub struct Gpu {
    device: wgpu::Device,
    queue: wgpu::Queue,
    renderer: Renderer,
    texture: wgpu::Texture,
    view: wgpu::TextureView,
    buffer: wgpu::Buffer,
    width: u32,
    height: u32,
    padded_bytes_per_row: u32,
    adapter: serde_json::Value,
}

pub struct FrameStats {
    pub width: u32,
    pub height: u32,
    pub paints: usize,
    pub scene_ms: f64,
    pub render_ms: f64,
    pub readback_ms: f64,
    pub grain_ms: f64,
    pub png_ms: f64,
    pub rgba_sha256: String,
}

impl Gpu {
    pub fn new() -> Result<Self, String> {
        let instance = wgpu::Instance::new(
            wgpu::InstanceDescriptor::new_without_display_handle().with_env(),
        );
        let adapter = pollster::block_on(instance.request_adapter(&wgpu::RequestAdapterOptions {
            power_preference: wgpu::PowerPreference::HighPerformance,
            ..Default::default()
        }))
        .map_err(|e| format!("no wgpu adapter: {e}"))?;
        let info = adapter.get_info();
        let adapter_json = serde_json::json!({
            "name": info.name,
            "backend": format!("{:?}", info.backend),
            "driver": info.driver,
            "device_type": format!("{:?}", info.device_type),
        });
        let (device, queue) = pollster::block_on(adapter.request_device(&wgpu::DeviceDescriptor {
            label: Some("northcel-vello"),
            required_features: wgpu::Features::empty(),
            required_limits: wgpu::Limits::default(),
            experimental_features: wgpu::ExperimentalFeatures::disabled(),
            memory_hints: wgpu::MemoryHints::Performance,
            trace: wgpu::Trace::Off,
        }))
        .map_err(|e| format!("cannot create wgpu device: {e}"))?;
        let renderer = Renderer::new(
            &device,
            RendererOptions {
                use_cpu: false,
                antialiasing_support: AaSupport::area_only(),
                ..Default::default()
            },
        )
        .map_err(|e| format!("cannot create Vello renderer: {e:?}"))?;
        // A 1x1 placeholder; resized on the first frame.
        let (texture, view, buffer, padded) = make_target(&device, 1, 1);
        Ok(Self {
            device,
            queue,
            renderer,
            texture,
            view,
            buffer,
            width: 1,
            height: 1,
            padded_bytes_per_row: padded,
            adapter: adapter_json,
        })
    }

    pub fn adapter(&self) -> &serde_json::Value {
        &self.adapter
    }

    fn ensure_size(&mut self, width: u32, height: u32) {
        if (width, height) == (self.width, self.height) {
            return;
        }
        let (texture, view, buffer, padded) = make_target(&self.device, width, height);
        self.texture = texture;
        self.view = view;
        self.buffer = buffer;
        self.width = width;
        self.height = height;
        self.padded_bytes_per_row = padded;
    }

}

fn make_target(
    device: &wgpu::Device,
    width: u32,
    height: u32,
) -> (wgpu::Texture, wgpu::TextureView, wgpu::Buffer, u32) {
    let texture = device.create_texture(&wgpu::TextureDescriptor {
        label: Some("northcel-vello-target"),
        size: wgpu::Extent3d { width, height, depth_or_array_layers: 1 },
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
    let padded = (width * 4).div_ceil(wgpu::COPY_BYTES_PER_ROW_ALIGNMENT)
        * wgpu::COPY_BYTES_PER_ROW_ALIGNMENT;
    let buffer = device.create_buffer(&wgpu::BufferDescriptor {
        label: Some("northcel-vello-readback"),
        size: (padded as u64) * (height as u64),
        usage: wgpu::BufferUsages::COPY_DST | wgpu::BufferUsages::MAP_READ,
        mapped_at_creation: false,
    });
    (texture, view, buffer, padded)
}

fn rings_to_path(rings: &[Vec<[f64; 2]>]) -> BezPath {
    let mut path = BezPath::new();
    for ring in rings {
        if ring.len() < 3 {
            continue;
        }
        path.move_to((ring[0][0], ring[0][1]));
        for p in &ring[1..] {
            path.line_to((p[0], p[1]));
        }
        path.close_path();
    }
    path
}

fn shared_prefix_len(stack: &[u32], groups: &[(u32, f32)]) -> usize {
    let mut shared = 0;
    while shared < stack.len()
        && shared < groups.len()
        && stack[shared] == groups[shared].0
    {
        shared += 1;
    }
    shared
}

pub fn build_scene(n: &Ncir) -> Scene {
    let mut scene = Scene::new();
    let canvas = Rect::new(0.0, 0.0, n.width as f64, n.height as f64);
    let mut group_stack: Vec<u32> = Vec::new();
    for paint in &n.paints {
        if paint.rings.is_empty()
            || paint.opacity <= 0.0
            || paint.groups.iter().any(|(_, op)| *op <= 0.0)
        {
            continue;
        }
        let shared = shared_prefix_len(&group_stack, &paint.groups);
        while group_stack.len() > shared {
            scene.pop_layer();
            group_stack.pop();
        }
        for (_gid, opacity) in paint.groups.iter().skip(group_stack.len()) {
            scene.push_layer(
                Fill::NonZero,
                BlendMode::default(),
                opacity.clamp(0.0, 1.0),
                Affine::IDENTITY,
                &canvas,
            );
            group_stack.push(_gid.clone());
        }
        let path = rings_to_path(&paint.rings);
        let clip_path = if paint.clips.is_empty() {
            None
        } else {
            Some(rings_to_path(&paint.clips))
        };
        if let Some(clip) = &clip_path {
            // A single clip target keeps the reference's even-odd coverage; a
            // merged union of several targets is NonZero.
            scene.push_clip_layer(Fill::EvenOdd, Affine::IDENTITY, clip);
        }
        let color = Color::new([
            paint.color[0] as f32 / 255.0,
            paint.color[1] as f32 / 255.0,
            paint.color[2] as f32 / 255.0,
            paint.opacity.clamp(0.0, 1.0),
        ]);
        scene.fill(Fill::EvenOdd, Affine::IDENTITY, color, None, &path);
        if clip_path.is_some() {
            scene.pop_layer();
        }
    }
    while !group_stack.is_empty() {
        scene.pop_layer();
        group_stack.pop();
    }
    scene
}

pub fn render_file(path: &Path, out: &Path) -> Result<FrameStats, String> {
    let mut gpu = Gpu::new()?;
    let bytes = std::fs::read(path)
        .map_err(|e| format!("cannot read {}: {e}", path.display()))?;
    let n = ncir::parse(&bytes)?;
    render_one(&mut gpu, &n, out)
}

pub fn render_one(gpu: &mut Gpu, n: &Ncir, out: &Path) -> Result<FrameStats, String> {
    let t_scene = Instant::now();
    let scene = build_scene(n);
    let scene_ms = ms(t_scene.elapsed());
    let base_color = Color::new([
        n.paper[0] as f32 / 255.0,
        n.paper[1] as f32 / 255.0,
        n.paper[2] as f32 / 255.0,
        1.0,
    ]);
    gpu.ensure_size(n.width, n.height);
    let t_render = Instant::now();
    gpu.renderer
        .render_to_texture(
            &gpu.device,
            &gpu.queue,
            &scene,
            &gpu.view,
            &RenderParams {
                base_color,
                width: n.width,
                height: n.height,
                antialiasing_method: AaConfig::Area,
            },
        )
        .map_err(|e| format!("Vello render failed: {e:?}"))?;
    let render_ms = ms(t_render.elapsed());
    let t_read = Instant::now();
    let mut encoder = gpu
        .device
        .create_command_encoder(&wgpu::CommandEncoderDescriptor { label: Some("ncel-vello") });
    encoder.copy_texture_to_buffer(
        wgpu::TexelCopyTextureInfo {
            texture: &gpu.texture,
            mip_level: 0,
            origin: wgpu::Origin3d::ZERO,
            aspect: wgpu::TextureAspect::All,
        },
        wgpu::TexelCopyBufferInfo {
            buffer: &gpu.buffer,
            layout: wgpu::TexelCopyBufferLayout {
                offset: 0,
                bytes_per_row: Some(gpu.padded_bytes_per_row),
                rows_per_image: Some(n.height),
            },
        },
        wgpu::Extent3d { width: n.width, height: n.height, depth_or_array_layers: 1 },
    );
    gpu.queue.submit(Some(encoder.finish()));
    let slice = gpu.buffer.slice(..);
    let (sender, receiver) = std::sync::mpsc::channel();
    slice.map_async(wgpu::MapMode::Read, move |result| {
        let _ = sender.send(result);
    });
    gpu.device
        .poll(wgpu::PollType::wait_indefinitely())
        .map_err(|e| format!("device poll failed: {e}"))?;
    receiver
        .recv()
        .map_err(|e| format!("readback callback dropped: {e}"))?
        .map_err(|e| format!("buffer map failed: {e}"))?;
    let mut rgba = Vec::with_capacity((n.width * n.height * 4) as usize);
    {
        let mapped = slice
            .get_mapped_range()
            .map_err(|e| format!("buffer view failed: {e}"))?;
        let row_bytes = (n.width * 4) as usize;
        for row in 0..n.height as usize {
            let start = row * gpu.padded_bytes_per_row as usize;
            rgba.extend_from_slice(&mapped[start..start + row_bytes]);
        }
    }
    gpu.buffer.unmap();
    let readback_ms = ms(t_read.elapsed());
    let t_grain = Instant::now();
    if n.grain > 0.0 {
        apply_grain(&mut rgba, n.width, n.height, n.seed as i64, n.grain as f64);
    }
    let grain_ms = ms(t_grain.elapsed());
    let t_png = Instant::now();
    if let Some(parent) = out.parent() {
        std::fs::create_dir_all(parent)
            .map_err(|e| format!("cannot create {}: {e}", parent.display()))?;
    }
    write_png(out, &rgba, n.width, n.height)?;
    let png_ms = ms(t_png.elapsed());
    Ok(FrameStats {
        width: n.width,
        height: n.height,
        paints: n.paints.len(),
        scene_ms,
        render_ms,
        readback_ms,
        grain_ms,
        png_ms,
        rgba_sha256: sha256_hex(&rgba),
    })
}

pub fn render_sequence(frames: &[PathBuf], out_dir: &Path) -> Result<Vec<FrameStats>, String> {
    std::fs::create_dir_all(out_dir)
        .map_err(|e| format!("cannot create {}: {e}", out_dir.display()))?;
    let mut gpu = Gpu::new()?;
    let mut stats = Vec::with_capacity(frames.len());
    for path in frames {
        let bytes = std::fs::read(path)
            .map_err(|e| format!("cannot read {}: {e}", path.display()))?;
        let n = ncir::parse(&bytes)?;
        let name = path
            .file_stem()
            .map(|s| s.to_string_lossy().to_string())
            .unwrap_or_else(|| "frame".into());
        let out = out_dir.join(format!("{name}.png"));
        stats.push(render_one(&mut gpu, &n, &out)?);
    }
    Ok(stats)
}

fn apply_grain(rgba: &mut [u8], width: u32, height: u32, seed: i64, grain: f64) {
    // Reference formula (renderer.py): hashed per-pixel phase, one noise value
    // for all channels, added before the final 8-bit rounding.
    let amplitude = grain * 255.0;
    for y in 0..height as usize {
        for x in 0..width as usize {
            let h = ((x as u64).wrapping_mul(374761393)
                + (y as u64).wrapping_mul(668265263)
                + (seed as u64).wrapping_mul(1442695041)) & 0xFFFFFFFF;
            let noise = (f64::sin(h as f64 * 0.0001) * 0.5) * amplitude;
            let i = (y * width as usize + x) * 4;
            for c in 0..3 {
                let v = rgba[i + c] as f64 + noise;
                rgba[i + c] = v.clamp(0.0, 255.0).round() as u8;
            }
        }
    }
}

fn write_png(path: &Path, rgba: &[u8], width: u32, height: u32) -> Result<(), String> {
    let file = std::fs::File::create(path)
        .map_err(|e| format!("cannot create {}: {e}", path.display()))?;
    let writer = std::io::BufWriter::new(file);
    let mut encoder = png::Encoder::new(writer, width, height);
    encoder.set_color(png::ColorType::Rgba);
    encoder.set_depth(png::BitDepth::Eight);
    let mut writer = encoder.write_header().map_err(|e| format!("PNG header: {e}"))?;
    writer.write_image_data(rgba).map_err(|e| format!("PNG data: {e}"))?;
    Ok(())
}

fn sha256_hex(bytes: &[u8]) -> String {
    use sha2::{Digest, Sha256};
    let digest = Sha256::digest(bytes);
    digest.iter().map(|b| format!("{b:02x}")).collect()
}

fn ms(d: std::time::Duration) -> f64 {
    d.as_secs_f64() * 1000.0
}
