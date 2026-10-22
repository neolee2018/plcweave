use super::{error, profiles::fx3g};
use crate::{
    AnalysisOptions, DeviceKind, DeviceRef, GxwError, InstructionProgram, InstructionSpan, Opcode,
    OperandValue, analysis::limit, build_ladder,
};
use serde::Serialize;
use std::{collections::BTreeSet, sync::Arc};

pub(crate) const X_COUNT: usize = 128;
pub(crate) const Y_COUNT: usize = 128;
pub(crate) const M_COUNT: usize = 7680;
pub(crate) const T_START: usize = X_COUNT + Y_COUNT + M_COUNT;
pub(crate) const C_START: usize = T_START + 320;
pub(crate) const MEMORY_SIZE: usize = C_START + 200;
// HBDTECH S2 extension (FX3U profile only): special auxiliary relays
// M8000..M8511 live in their own image tail, after the FX3G-compatible area,
// so every pre-existing slot stays unchanged under the fx3g profile.
pub(crate) const SPECIAL_M_FIRST: u32 = 8000;
pub(crate) const SPECIAL_M_COUNT: usize = 512;
pub(crate) const SPECIAL_M_START: usize = MEMORY_SIZE;
pub(crate) const FX3U_MEMORY_SIZE: usize = MEMORY_SIZE + SPECIAL_M_COUNT;
/// D data registers D0..D7999, 16-bit words stored outside the bit image.
// PLCWeave: external L01S special D image; peripherals are not simulated.
pub(crate) const WORD_COUNT: usize = 8512;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "lowercase")]
pub enum SimulationProfile {
    Fx3g,
    Fx3u,
}
impl SimulationProfile {
    pub fn parse(name: &str) -> Result<Self, GxwError> {
        match name {
            "fx3g" => Ok(Self::Fx3g),
            "fx3u" => Ok(Self::Fx3u),
            _ => Err(error(
                "GXW_SIM_PROFILE_UNSUPPORTED",
                format!("Unsupported simulation profile: {name}"),
                None,
            )),
        }
    }
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Fx3g => "fx3g",
            Self::Fx3u => "fx3u",
        }
    }
    /// Word slots index Memory::words; only the FX3U profile has D storage.
    pub(crate) fn word_slot(self, d: &DeviceRef) -> Result<usize, GxwError> {
        if !matches!(self, Self::Fx3u) {
            return Err(error(
                "GXW_SIM_DEVICE_UNSUPPORTED",
                format!("{} requires the fx3u profile (word devices)", d.name()),
                None,
            ));
        }
        if d.device == DeviceKind::D && (d.address as usize) < WORD_COUNT {
            Ok(d.address as usize)
        } else {
            Err(error(
                "GXW_SIM_DEVICE_UNSUPPORTED",
                format!("{} is outside D0..D8511 (16-bit image; external peripheral semantics unmodelled)", d.name()),
                None,
            ))
        }
    }
    pub fn parse_device(self, name: &str) -> Result<DeviceRef, GxwError> {
        let d = DeviceRef::parse(name).map_err(|_| {
            error(
                "GXW_SIM_DEVICE_INVALID",
                format!("Invalid FX bit device: {name}"),
                None,
            )
        })?;
        if d.device == DeviceKind::D {
            self.word_slot(&d)?;
        } else {
            self.slot(&d)?;
        }
        Ok(d)
    }
    pub(crate) fn slot(self, d: &DeviceRef) -> Result<usize, GxwError> {
        let a = d.address as usize;
        match d.device {
            DeviceKind::X if a < X_COUNT => Ok(a),
            DeviceKind::Y if a < Y_COUNT => Ok(X_COUNT + a),
            DeviceKind::M if a < M_COUNT => Ok(X_COUNT + Y_COUNT + a),
            DeviceKind::M
                if matches!(self, Self::Fx3u)
                    && d.address >= SPECIAL_M_FIRST
                    && a < SPECIAL_M_FIRST as usize + SPECIAL_M_COUNT =>
            {
                Ok(SPECIAL_M_START + (a - SPECIAL_M_FIRST as usize))
            }
            DeviceKind::T if fx3g::timer(d.address).is_some() => Ok(T_START + a),
            DeviceKind::C if a < 200 => Ok(C_START + a),
            _ => Err(error(
                "GXW_SIM_DEVICE_UNSUPPORTED",
                format!(
                    "{} is outside the simulation subset (X/Y0..177 octal, M0..7679, T0..191/T200..245/T250..319, C0..199 decimal; fx3u adds M8000..M8511 and D0..D7999)",
                    d.name()
                ),
                None,
            )),
        }
    }
}

/// HBDTECH S2 extension: one resolved 16-bit word operand of MOV/ADD.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum WordOperand {
    Constant { value: i32 },
    Word { address: u32 },
}

#[derive(Debug, Clone, Serialize)]
pub struct CompiledInstruction {
    pub instruction: usize,
    pub opcode: Opcode,
    pub device: Option<DeviceRef>,
    pub preset: Option<u16>,
    /// Resolved word operands for MOV/ADD; empty for bit instructions.
    pub word_operands: Vec<WordOperand>,
    pub source: InstructionSpan,
    #[serde(skip)]
    pub(crate) slot: usize,
}
/// No public constructor or mutable operations: only the compiler can create
/// executable instructions. The source remains owned and immutable under Arc.
#[derive(Debug, Serialize)]
pub struct CompiledProgram {
    schema_version: u32,
    profile: SimulationProfile,
    execution_scope: &'static str,
    source_sha256: String,
    instructions: Vec<CompiledInstruction>,
    devices: Vec<DeviceRef>,
    #[serde(skip)]
    program: Arc<InstructionProgram>,
}
impl CompiledProgram {
    pub fn schema_version(&self) -> u32 {
        self.schema_version
    }
    pub fn profile(&self) -> SimulationProfile {
        self.profile
    }
    pub fn execution_scope(&self) -> &str {
        self.execution_scope
    }
    pub fn source_sha256(&self) -> &str {
        &self.source_sha256
    }
    pub fn instructions(&self) -> &[CompiledInstruction] {
        &self.instructions
    }
    pub fn devices(&self) -> &[DeviceRef] {
        &self.devices
    }
    pub fn program(&self) -> &Arc<InstructionProgram> {
        &self.program
    }
    pub fn to_json(&self) -> Result<String, serde_json::Error> {
        serde_json::to_string_pretty(self)
    }
}

pub fn compile_program(
    program: Arc<InstructionProgram>,
    profile: SimulationProfile,
    max_instructions: usize,
) -> Result<CompiledProgram, GxwError> {
    limit(
        "simulation compiler instruction limit",
        max_instructions,
        1_000_000,
    )?;
    limit(
        "simulation instructions",
        program.instructions.len(),
        max_instructions,
    )?;
    if !program.complete || !program.opaque_regions.is_empty() {
        return Err(error(
            "GXW_SIM_INCOMPLETE",
            "Instruction program is incomplete; unsupported code and opaque regions cannot execute",
            None,
        ));
    }
    // Check the source program itself, never a caller-supplied display graph.
    let mut devices = BTreeSet::new();
    let mut instructions = Vec::with_capacity(program.instructions.len());
    let mut coils = BTreeSet::new();
    let mut resets = BTreeSet::new();
    for (index, ins) in program.instructions.iter().enumerate() {
        if ins.ordinal != index || !ins.supported || !crate::ir::valid_instruction(ins) {
            return Err(error(
                "GXW_SIM_INSTRUCTION_UNSUPPORTED",
                "Unvalidated instruction or operand",
                Some(index),
            ));
        }
        if ins.source.length == 0 || program.source_bytes(&ins.source).is_none() {
            return Err(error(
                "GXW_SIM_SOURCE_INVALID",
                "Instruction has no valid source range",
                Some(index),
            ));
        }
        // HBDTECH S2 extension: word application instructions resolve every
        // operand into a constant or a D word slot; bit instructions keep the
        // single-device compilation below unchanged.
        let is_word_instruction = matches!(ins.opcode, Some(Opcode::Mov | Opcode::Add | Opcode::Sub | Opcode::Mul | Opcode::Div | Opcode::AndEq | Opcode::AndLt | Opcode::AndLe | Opcode::AndGt | Opcode::AndGe));
        let mut word_operands = Vec::new();
        if is_word_instruction {
            if !matches!(profile, SimulationProfile::Fx3u) {
                return Err(error(
                    "GXW_SIM_PROFILE_UNSUPPORTED",
                    "MOV/ADD require the fx3u profile",
                    Some(index),
                ));
            }
            for (operand_index, operand) in ins.operands.iter().enumerate() {
                match &operand.value {
                    OperandValue::Constant { value, .. } => {
                        word_operands.push(WordOperand::Constant { value: *value as i32 });
                    }
                    OperandValue::Device {
                        device: DeviceKind::D,
                        address,
                        ..
                    } => {
                        let d = DeviceRef {
                            device: DeviceKind::D,
                            address: *address,
                        };
                        profile
                            .word_slot(&d)
                            .map_err(|e| error("GXW_SIM_DEVICE_UNSUPPORTED", e.to_string(), Some(index)))?;
                        devices.insert(d);
                        word_operands.push(WordOperand::Word { address: *address });
                    }
                    _ => {
                        return Err(error(
                            "GXW_SIM_OPERAND_UNSUPPORTED",
                            format!(
                                "operand {} of {} is not a K/H constant or D word",
                                operand_index + 1,
                                ins.opcode.expect("word instruction").as_str()
                            ),
                            Some(index),
                        ));
                    }
                }
            }
        }
        // PLCWeave: double-register destinations must both exist and be tracked.
        if matches!(ins.opcode, Some(Opcode::Mul | Opcode::Div)) {
            if ins.opcode == Some(Opcode::Div) && !matches!(word_operands.get(1), Some(WordOperand::Constant { value }) if (*value as i16) != 0) {
                return Err(error("GXW_SIM_DIVISOR_UNSUPPORTED", "DIV supports a nonzero literal divisor only", Some(index)));
            }
            if let Some(WordOperand::Word { address }) = word_operands.last() {
                let d = DeviceRef { device: DeviceKind::D, address: address + 1 };
                profile.word_slot(&d)?;
                devices.insert(d);
            }
        }
        let (device, slot) = if is_word_instruction {
            (None, 0)
        } else if let Some(operand) = ins.operands.first() {
            let OperandValue::Device {
                device, address, ..
            } = operand.value
            else {
                return Err(error(
                    "GXW_SIM_DEVICE_UNSUPPORTED",
                    "Expected a resolved bit device",
                    Some(index),
                ));
            };
            let d = DeviceRef { device, address };
            let slot = profile
                .slot(&d)
                .map_err(|e| error("GXW_SIM_DEVICE_UNSUPPORTED", e.to_string(), Some(index)))?;
            devices.insert(d.clone());
            (Some(d), slot)
        } else {
            (None, 0)
        };
        let mut preset = None;
        if let Some(d) = &device
            && matches!(d.device, DeviceKind::T | DeviceKind::C)
        {
            if ins.opcode == Some(Opcode::Out) {
                let Some(OperandValue::Constant {
                    value, radix: 10, ..
                }) = ins.operands.get(1).map(|o| &o.value)
                else {
                    return Err(error(
                        "GXW_SIM_PRESET_UNSUPPORTED",
                        "T/C OUT requires a literal K0..K32767 preset; D presets are not executable",
                        Some(index),
                    ));
                };
                preset = Some(*value as u16);
                if !coils.insert(d.clone()) {
                    return Err(error(
                        "GXW_SIM_MULTIPLE_COIL",
                        "Only one OUT per timer/counter is supported",
                        Some(index),
                    ));
                }
            } else if ins.opcode == Some(Opcode::Rst) && !resets.insert(d.clone()) {
                return Err(error(
                    "GXW_SIM_MULTIPLE_RESET",
                    "Only one RST per timer/counter is supported",
                    Some(index),
                ));
            }
        }
        instructions.push(CompiledInstruction {
            instruction: index,
            opcode: ins.opcode.expect("validated opcode"),
            device,
            preset,
            word_operands,
            source: ins.source.clone(),
            slot,
        });
    }
    let end_valid = instructions.last().is_some_and(|i| i.opcode == Opcode::End)
        && instructions
            .iter()
            .filter(|i| i.opcode == Opcode::End)
            .count()
            == 1;
    if !end_valid {
        return Err(error(
            "GXW_SIM_END_INVALID",
            "Expected exactly one final END",
            None,
        ));
    }
    let graph = build_ladder(
        program.clone(),
        &AnalysisOptions {
            max_instructions,
            ..AnalysisOptions::default()
        },
    )?;
    if !graph.complete {
        let f = graph
            .diagnostics
            .first()
            .expect("incomplete structure has diagnostic");
        return Err(error(
            "GXW_SIM_STRUCTURE_INVALID",
            format!("{}: {}", f.code, f.message),
            f.instruction,
        ));
    }
    Ok(CompiledProgram {
        schema_version: 2,
        profile,
        execution_scope: "isolated_single_program",
        source_sha256: program.source_sha256.clone(),
        instructions,
        devices: devices.into_iter().collect(),
        program,
    })
}
