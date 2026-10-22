"""Reproducible PLCWeave modifications to the pinned 102/gxwlib import.

HBDTECH 2026. Original MIT and nested notices remain in vendor/gxwlib.
No original source file outside this repository is modified.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "vendor/gxwlib/crates/gxw-core/src"
COMPARE = "Opcode::AndEq | Opcode::AndLt | Opcode::AndLe | Opcode::AndGt | Opcode::AndGe"
WORDS = "Opcode::Mov | Opcode::Add | Opcode::Sub | Opcode::Mul | Opcode::Div"

def edit(file, replacements):
    path = ROOT / file
    text = path.read_text(encoding="utf-8")
    for old, new in replacements:
        if old not in text:
            raise SystemExit(f"Expected anchor absent in {file}: {old[:90]}")
        text = text.replace(old, new)
    path.write_text(text, encoding="utf-8")

edit("ir.rs", [
    ("    Add,\n}", "    Add,\n    // PLCWeave extension, EXECUTION_IMPLEMENTED; no vendor verification claimed.\n    Sub, Mul, Div, AndEq, AndLt, AndLe, AndGt, AndGe,\n}"),
    ('            "ADD" => Self::Add,', '            "ADD" => Self::Add,\n' + '\n'.join(f'            "{op}" => Self::{variant},' for op,variant in [("SUB","Sub"),("MUL","Mul"),("DIV","Div"),("AND=","AndEq"),("AND<","AndLt"),("AND<=","AndLe"),("AND>","AndGt"),("AND>=","AndGe")])),
    ('            Self::Add => "ADD",', '            Self::Add => "ADD",\n' + '\n'.join(f'            Self::{variant} => "{op}",' for op,variant in [("SUB","Sub"),("MUL","Mul"),("DIV","Div"),("AND=","AndEq"),("AND<","AndLt"),("AND<=","AndLe"),("AND>","AndGt"),("AND>=","AndGe")])),
    ('            Some(Opcode::Add),', '            Some(Opcode::Add | Opcode::Sub | Opcode::Mul | Opcode::Div),'),
    ('        _ => false,\n    }\n}\n\n/// FX spelling', f'''        (Some({COMPARE}), [s1, s2]) => {{
            matches!(s1, Constant {{ .. }} | Device {{ device: D, .. }})
                && matches!(s2, Constant {{ .. }} | Device {{ device: D, .. }})
        }}
        _ => false,
    }}
}}

/// FX spelling'''),
])
edit("ladder/mod.rs", [
    ('Opcode::And | Opcode::Ani | Opcode::Or | Opcode::Ori => {', f'Opcode::And | Opcode::Ani | Opcode::Or | Opcode::Ori | {COMPARE} => {{'),
    ('matches!(op, Opcode::And | Opcode::Ani)', f'matches!(op, Opcode::And | Opcode::Ani | {COMPARE})'),
    ('Opcode::Mov | Opcode::Add => {', WORDS + ' => {'),
])
edit("simulation/compile.rs", [
    ('pub(crate) const WORD_COUNT: usize = 8000;', '// PLCWeave: external L01S special D image; peripherals are not simulated.\npub(crate) const WORD_COUNT: usize = 8512;'),
    ('D0..D7999 (16-bit word subset)', 'D0..D8511 (16-bit image; external peripheral semantics unmodelled)'),
    ('Some(Opcode::Mov | Opcode::Add)', f'Some({WORDS} | {COMPARE})'),
    ('        let (device, slot) = if is_word_instruction {', '''        // PLCWeave: double-register destinations must both exist and be tracked.
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
        let (device, slot) = if is_word_instruction {'''),
])
edit("simulation/scan.rs", [
    ('                Opcode::Mov | Opcode::Add => {', f'''                // PLCWeave signed word comparison contacts.
                {COMPARE} => {{
                    let read = |op: &WordOperand| match op {{
                        WordOperand::Constant {{ value }} => *value as i16,
                        WordOperand::Word {{ address }} => self.memory.words[*address as usize],
                    }};
                    let a = read(&ins.word_operands[0]);
                    let b = read(&ins.word_operands[1]);
                    let value = match ins.opcode {{
                        Opcode::AndEq => a == b, Opcode::AndLt => a < b,
                        Opcode::AndLe => a <= b, Opcode::AndGt => a > b,
                        Opcode::AndGe => a >= b, _ => unreachable!(),
                    }};
                    current = Some(current.expect("compiled predecessor") & value);
                }}
                {WORDS} => {{'''),
    ('                            _ => unreachable!("word instruction dispatched"),', '''                            // PLCWeave: signed 16-bit sources, two-word MUL/DIV result.
                            Opcode::Sub | Opcode::Mul | Opcode::Div => {
                                let a = read(&ins.word_operands[0], &self.memory.words) as i32;
                                let b = read(&ins.word_operands[1], &self.memory.words) as i32;
                                let WordOperand::Word { address } = ins.word_operands[2] else { unreachable!() };
                                let dest = address as usize;
                                match ins.opcode {
                                    Opcode::Sub => self.memory.words[dest] = (a - b) as i16,
                                    Opcode::Mul => {
                                        let value = a * b;
                                        self.memory.words[dest] = value as i16;
                                        self.memory.words[dest+1] = (value >> 16) as i16;
                                    }
                                    Opcode::Div => {
                                        self.memory.words[dest] = (a / b) as i16;
                                        self.memory.words[dest+1] = (a % b) as i16;
                                    }
                                    _ => unreachable!(),
                                }
                            }
                            _ => unreachable!("word instruction dispatched"),'''),
])
print("Extended pinned runtime; run micro-tests before project tests")
