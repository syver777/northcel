//! NCIR v2 reader: one evaluated frame as a binary paint list.
//!
//! The writer is `northcel.ncir` in Python. Geometry is already frame-resolved;
//! this module only decodes ring topology, group scopes, clips and opacity.

#[derive(Debug, Clone)]
pub struct NcirPaint {
    pub name: String,
    pub color: [u8; 3],
    pub opacity: f32,
    pub groups: Vec<(u32, f32)>,
    pub path: Vec<String>,
    pub rings: Vec<Vec<[f64; 2]>>,
    pub clips: Vec<Vec<[f64; 2]>>,
}

#[derive(Debug, Clone)]
pub struct Ncir {
    pub flags: u16,
    pub width: u32,
    pub height: u32,
    pub frame: u32,
    pub fps: u32,
    pub seed: u32,
    pub paper: [u8; 3],
    pub antialias_grid: u8,
    pub grain: f32,
    pub paints: Vec<NcirPaint>,
}

struct Cursor<'a> {
    data: &'a [u8],
    at: usize,
}

impl<'a> Cursor<'a> {
    fn need(&self, n: usize) -> Result<(), String> {
        if self.at + n > self.data.len() {
            return Err(format!(
                "truncated NCIR at offset {} (need {n} more bytes, have {})",
                self.at,
                self.data.len() - self.at
            ));
        }
        Ok(())
    }

    fn u8(&mut self) -> Result<u8, String> {
        self.need(1)?;
        let v = self.data[self.at];
        self.at += 1;
        Ok(v)
    }

    fn u16(&mut self) -> Result<u16, String> {
        self.need(2)?;
        let v = u16::from_le_bytes([self.data[self.at], self.data[self.at + 1]]);
        self.at += 2;
        Ok(v)
    }

    fn u32(&mut self) -> Result<u32, String> {
        self.need(4)?;
        let mut b = [0u8; 4];
        b.copy_from_slice(&self.data[self.at..self.at + 4]);
        self.at += 4;
        Ok(u32::from_le_bytes(b))
    }

    fn f32(&mut self) -> Result<f32, String> {
        Ok(f32::from_bits(self.u32()?))
    }

    fn bytes(&mut self, n: usize) -> Result<&'a [u8], String> {
        self.need(n)?;
        let slice = &self.data[self.at..self.at + n];
        self.at += n;
        Ok(slice)
    }

    fn string(&mut self, n: usize) -> Result<String, String> {
        let raw = self.bytes(n)?;
        String::from_utf8(raw.to_vec()).map_err(|e| format!("invalid UTF-8 name: {e}"))
    }

    fn rings(&mut self, count: u32) -> Result<Vec<Vec<[f64; 2]>>, String> {
        let mut rings = Vec::with_capacity(count as usize);
        for _ in 0..count {
            let n = self.u32()? as usize;
            self.need(n * 8)?;
            let mut ring = Vec::with_capacity(n);
            for _ in 0..n {
                ring.push([self.f32()? as f64, self.f32()? as f64]);
            }
            rings.push(ring);
        }
        Ok(rings)
    }
}

pub fn parse(data: &[u8]) -> Result<Ncir, String> {
    if data.len() < 4 || &data[..4] != b"NCIR" {
        return Err("not an NCIR file (bad magic)".into());
    }
    let mut c = Cursor { data, at: 4 };
    let version = c.u16()?;
    if version != 2 {
        return Err(format!("unsupported NCIR version {version} (expected 2)"));
    }
    let flags = c.u16()?;
    let width = c.u32()?;
    let height = c.u32()?;
    let frame = c.u32()?;
    let fps = c.u32()?;
    let seed = c.u32()?;
    let paper = [c.u8()?, c.u8()?, c.u8()?];
    let antialias_grid = c.u8()?;
    let grain = c.f32()?;
    let count = c.u32()?;
    if width == 0 || height == 0 || width > 8192 || height > 8192 {
        return Err(format!("canvas {width}x{height} is outside 1..8192"));
    }
    let mut paints = Vec::with_capacity(count as usize);
    for _ in 0..count {
        let name_len = c.u16()? as usize;
        let name = c.string(name_len)?;
        let color = [c.u8()?, c.u8()?, c.u8()?];
        let opacity = c.f32()?;
        let group_count = c.u16()?;
        let mut groups = Vec::with_capacity(group_count as usize);
        for _ in 0..group_count {
            groups.push((c.u32()?, c.f32()?));
        }
        let path_count = c.u16()?;
        let mut path = Vec::with_capacity(path_count as usize);
        for _ in 0..path_count {
            let len = c.u16()? as usize;
            path.push(c.string(len)?);
        }
        let ring_count = c.u32()?;
        let rings = c.rings(ring_count)?;
        let clip_count = c.u16()? as u32;
        let clips = c.rings(clip_count)?;
        paints.push(NcirPaint { name, color, opacity, groups, path, rings, clips });
    }
    if c.at != data.len() {
        return Err(format!("{} trailing bytes after the paint list", data.len() - c.at));
    }
    Ok(Ncir { flags, width, height, frame, fps, seed, paper, antialias_grid, grain, paints })
}

/// Test/maintenance receipts: totals that a caller can report honestly.
pub fn summary(n: &Ncir) -> serde_json::Value {
    let vertices: usize = n.paints.iter().flat_map(|p| p.rings.iter()).map(|r| r.len()).sum();
    let clip_vertices: usize = n.paints.iter().flat_map(|p| p.clips.iter()).map(|r| r.len()).sum();
    serde_json::json!({
        "version": 2,
        "width": n.width,
        "height": n.height,
        "frame": n.frame,
        "fps": n.fps,
        "seed": n.seed,
        "paints": n.paints.len(),
        "vertices": vertices,
        "clip_vertices": clip_vertices,
        "groups": n.paints.iter().map(|p| p.groups.len()).sum::<usize>(),
        "clipped_paints": n.paints.iter().filter(|p| !p.clips.is_empty()).count(),
    })
}
