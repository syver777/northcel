//! Fixture model for the Vello prototype.
//!
//! The JSON file is written by `scripts/make_fixture.py` from the Python
//! reference renderer's flattened paint list (`frame_paint_list`). It is a
//! self-contained snapshot of one evaluated frame, not the binary NCIR.

use serde::Deserialize;
use std::path::Path;

#[derive(Debug, Clone, Deserialize)]
pub struct Fixture {
    pub format: String,
    pub source: String,
    pub frame_index: u32,
    pub width: u32,
    pub height: u32,
    pub seed: i64,
    pub paper: Paper,
    #[serde(default)]
    pub layers: Vec<Layer>,
    #[serde(default)]
    pub notes: Vec<String>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct Paper {
    pub rgb: [u8; 3],
    #[serde(default)]
    pub grain: f64,
    #[serde(default = "default_aa")]
    pub antialias_grid: u32,
}

fn default_aa() -> u32 {
    4
}

#[derive(Debug, Clone, Deserialize)]
pub struct Layer {
    pub name: String,
    pub color: [u8; 3],
    #[serde(default = "default_opacity")]
    pub opacity: f64,
    /// Enclosing group-opacity scopes, outermost first, as `(group_id, opacity)`.
    #[serde(default)]
    pub group_opacity: Vec<(u32, f64)>,
    #[serde(default)]
    pub rings: Vec<Vec<[f64; 2]>>,
    /// Resolved clip targets. Outer vec = clip shapes, middle = rings, inner = points.
    #[serde(default)]
    pub clip_shapes: Vec<Vec<Vec<[f64; 2]>>>,
}

fn default_opacity() -> f64 {
    1.0
}

impl Fixture {
    pub fn load(path: &Path) -> Result<Self, String> {
        let text = std::fs::read_to_string(path)
            .map_err(|e| format!("cannot read fixture {}: {e}", path.display()))?;
        let fixture: Fixture = serde_json::from_str(&text)
            .map_err(|e| format!("cannot parse fixture {}: {e}", path.display()))?;
        fixture.validate()?;
        Ok(fixture)
    }

    fn validate(&self) -> Result<(), String> {
        if self.format != "northcel-paintlist-v1" {
            return Err(format!(
                "unsupported fixture format {:?} (expected northcel-paintlist-v1)",
                self.format
            ));
        }
        if self.width == 0 || self.height == 0 {
            return Err("fixture has zero width or height".into());
        }
        if self.width > 8192 || self.height > 8192 {
            return Err("prototype canvas limit is 8192 per dimension".into());
        }
        if !self.paper.grain.is_finite() || self.paper.grain < 0.0 {
            return Err("paper grain must be finite and nonnegative".into());
        }
        let mut points = 0usize;
        for layer in &self.layers {
            if !layer.opacity.is_finite()
                || !(0.0..=1.0).contains(&layer.opacity)
                || layer
                    .group_opacity
                    .iter()
                    .any(|(_, opacity)| !opacity.is_finite() || !(0.0..=1.0).contains(opacity))
            {
                return Err(format!("layer {:?} has opacity outside 0..1", layer.name));
            }
            for ring in layer.rings.iter().chain(layer.clip_shapes.iter().flatten()) {
                if ring.len() < 3 {
                    return Err(format!(
                        "layer {:?} has a ring with {} vertices (< 3)",
                        layer.name,
                        ring.len()
                    ));
                }
                if !ring.iter().all(|p| p[0].is_finite() && p[1].is_finite()) {
                    return Err(format!("layer {:?} has a non-finite point", layer.name));
                }
            }
            points += layer.rings.iter().map(Vec::len).sum::<usize>();
        }
        if points == 0 {
            return Err("fixture has no drawable geometry".into());
        }
        Ok(())
    }

    pub fn layer_count(&self) -> usize {
        self.layers.len()
    }

    pub fn ring_count(&self) -> usize {
        self.layers.iter().map(|l| l.rings.len()).sum()
    }

    pub fn point_count(&self) -> usize {
        self.layers
            .iter()
            .flat_map(|l| &l.rings)
            .map(|r| r.len())
            .sum()
    }

    pub fn clip_point_count(&self) -> usize {
        self.layers
            .iter()
            .flat_map(|l| &l.clip_shapes)
            .flat_map(|s| s.iter())
            .map(|r| r.len())
            .sum()
    }

    /// True when any layer uses a feature Vello's prototype path does not model
    /// exactly. Used for an honest note in the report/JSON output.
    pub fn limitation_notes(&self) -> Vec<String> {
        let mut notes = Vec::new();
        if self.paper.grain > 0.0 {
            notes.push(
                "paper grain is applied on the CPU after render using the reference formula"
                    .to_string(),
            );
        }
        if self.paper.antialias_grid != 4 {
            notes.push(format!(
                "fixture AA grid is {}; Vello always uses its analytic area AA",
                self.paper.antialias_grid
            ));
        }
        let multi_clip = self.layers.iter().any(|l| l.clip_shapes.len() > 1);
        if multi_clip {
            notes.push(
                "multiple clip shapes are approximated by one NonZero path, not a general even-odd span union; holes or opposite windings can differ"
                    .to_string(),
            );
        }
        let nested_groups = self.layers.iter().any(|l| l.group_opacity.len() > 1);
        if nested_groups {
            notes.push(
                "nested group opacity is emulated with nested Vello blend layers".to_string(),
            );
        }
        notes
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sample() -> Fixture {
        serde_json::from_str(include_str!("../fixtures/skyline_1080_flat.paintlist.json")).unwrap()
    }

    #[test]
    fn supplied_fixture_has_expected_geometry() {
        let f = sample();
        assert!(f.validate().is_ok());
        assert_eq!(
            (
                f.layer_count(),
                f.ring_count(),
                f.point_count(),
                f.clip_point_count()
            ),
            (26, 40, 2427, 102)
        );
    }

    #[test]
    fn rejects_invalid_format_and_dimensions() {
        let mut f = sample();
        f.format = "NCIR".into();
        assert!(f.validate().unwrap_err().contains("unsupported fixture"));
        f.format = "northcel-paintlist-v1".into();
        f.width = 0;
        assert!(f.validate().is_err());
        f.width = u32::MAX;
        assert!(f.validate().is_err());
    }

    #[test]
    fn rejects_invalid_clip_geometry_and_opacity() {
        let mut f = sample();
        f.layers[0].clip_shapes = vec![vec![vec![[0.0, 0.0]; 2]]];
        assert!(f.validate().is_err());
        f.layers[0].clip_shapes = vec![vec![vec![[f64::NAN, 0.0]; 3]]];
        assert!(f.validate().is_err());
        f.layers[0].clip_shapes.clear();
        f.layers[0].opacity = 2.0;
        assert!(f.validate().is_err());
    }

    #[test]
    fn rejects_empty_drawable_geometry() {
        let mut f = sample();
        f.layers.clear();
        assert!(f.validate().unwrap_err().contains("no drawable geometry"));
    }
}
