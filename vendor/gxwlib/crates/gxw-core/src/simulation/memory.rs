use super::{
    SimulationProfile,
    compile::{FX3U_MEMORY_SIZE, WORD_COUNT, X_COUNT, Y_COUNT},
    error,
};
use crate::{DeviceKind, DeviceRef, GxwError};
use std::collections::BTreeSet;

#[derive(Debug, Clone)]
pub(crate) struct Memory {
    /// Sized for the fx3u profile (includes the M8000.. tail); the fx3g
    /// profile simply never addresses the extra slots.
    pub image: Box<[bool]>,
    pub pending_inputs: [bool; X_COUNT],
    pub outputs: [bool; Y_COUNT],
    /// D data registers D0..D7999, 16-bit two's-complement words.
    pub words: Box<[i16]>,
}
impl Default for Memory {
    fn default() -> Self {
        Self {
            image: vec![false; FX3U_MEMORY_SIZE].into_boxed_slice(),
            pending_inputs: [false; X_COUNT],
            outputs: [false; Y_COUNT],
            words: vec![0; WORD_COUNT].into_boxed_slice(),
        }
    }
}
impl Memory {
    pub fn latch_inputs(&mut self) {
        self.image[..X_COUNT].copy_from_slice(&self.pending_inputs);
    }
    pub fn commit_outputs(&mut self) {
        self.outputs
            .copy_from_slice(&self.image[X_COUNT..X_COUNT + Y_COUNT]);
    }
}
/// Validate a complete update before changing any memory; reject aliased keys.
pub(crate) fn patch(
    profile: SimulationProfile,
    values: &[(String, bool)],
    inputs: bool,
) -> Result<Vec<(DeviceRef, usize, bool)>, GxwError> {
    let mut seen = BTreeSet::new();
    let mut result = Vec::new();
    for (name, value) in values {
        let d = profile.parse_device(name)?;
        if (inputs && d.device != DeviceKind::X)
            || (!inputs && !matches!(d.device, DeviceKind::Y | DeviceKind::M))
        {
            return Err(error(
                "GXW_SIM_UPDATE_TARGET",
                if inputs {
                    "set_inputs accepts only X devices"
                } else {
                    "initial_state/set_devices accept only Y and M devices"
                },
                None,
            ));
        }
        if !seen.insert(d.clone()) {
            return Err(error(
                "GXW_SIM_DUPLICATE_DEVICE",
                format!("Duplicate normalized device: {}", d.name()),
                None,
            ));
        }
        let slot = profile.slot(&d)?;
        result.push((d, slot, *value));
    }
    Ok(result)
}
/// HBDTECH S2 extension: validate a D-word update before changing memory.
pub(crate) fn word_patch(
    profile: SimulationProfile,
    values: &[(String, i32)],
) -> Result<Vec<(DeviceRef, usize, i16)>, GxwError> {
    let mut seen = BTreeSet::new();
    let mut result = Vec::new();
    for (name, value) in values {
        let d = profile
            .parse_device(name)
            .map_err(|_| error("GXW_SIM_DEVICE_INVALID", format!("Invalid D device: {name}"), None))?;
        if d.device != DeviceKind::D {
            return Err(error(
                "GXW_SIM_UPDATE_TARGET",
                "word updates accept only D devices",
                None,
            ));
        }
        if !seen.insert(d.clone()) {
            return Err(error(
                "GXW_SIM_DUPLICATE_DEVICE",
                format!("Duplicate normalized device: {}", d.name()),
                None,
            ));
        }
        let slot = profile.word_slot(&d)?;
        result.push((d, slot, *value as i16));
    }
    Ok(result)
}
