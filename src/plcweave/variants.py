"""Build an isolated HIL image and a real-I/O image from one control core.

The first adapter is deliberately limited to the existing FX execution subset
and the L01S Modbus register profile. Design tables remain the authoring source.
"""
import re
from pathlib import Path

from .fx import parse_fxil

IDENTITY = set(range(196, 203))
TABLES = {
    "PLCWeave": ["key", "value"],
    "Inputs": ["logical", "physical", "injection"],
    "Outputs": ["logical", "physical"],
    "HIL reset": ["device", "value"],
    "Reset expectations": ["device", "value"],
    "HIL cleanup": ["device", "value"],
    "Cleanup expectations": ["device", "value"],
}

DESIGN_DRAFT = """# 设计方案（由AI根据requirements.md完善）

请补全资源分配、控制逻辑、状态转换、故障响应与需求覆盖说明。
以下是可执行接口契约；占位项未填完不能冻结。

## PLCWeave
| key | value |
| --- | --- |
| target | 请填写：l01s 或 fx3u |
| protocol | l01s-modbus-rtu |
| program_version | 1 |
| edition | 51 |
| suite_word | 1 |
| reset_ms | 100 |

## Inputs
| logical | physical | injection |
| --- | --- | --- |

## Outputs
| logical | physical |
| --- | --- |

## HIL reset
| device | value |
| --- | --- |

## Reset expectations
| device | value |
| --- | --- |

## HIL cleanup
| device | value |
| --- | --- |

## Cleanup expectations
| device | value |
| --- | --- |
"""


def _internal(name):
    if not re.fullmatch(r"[MD](?:0|[1-9]\d*)", name):
        raise ValueError(f"Expected canonical internal M/D address: {name}")
    index = int(name[1:])
    if name.startswith("M") and index <= 7679:
        return "bit"
    if name.startswith("D") and index < 8000 and index not in IDENTITY:
        return "word"
    raise ValueError(f"Reserved/out-of-range address: {name}")


def _physical(name, output=False):
    if re.fullmatch(r"[XY](?:0|[1-7][0-7]*)", name):
        if name[0] != ("Y" if output else "X") or int(name[1:], 8) > 0o177:
            raise ValueError(f"Unsupported physical bit: {name}")
        return "bit"
    if name in ({"D8050", "D8051"} if output else {"D8030", "D8031", "D8032", "D8033"}):
        return "word"
    raise ValueError(f"Unsupported physical address in initial L01S profile: {name}")


def read_design(path):
    rows = {key: [] for key in TABLES}
    section = None
    header = False
    for line in Path(path).read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if line.startswith("## "):
            section = line[3:]
            header = False
        elif line.startswith("|") and section in TABLES:
            cells = [x.strip().strip("`") for x in line.strip("|").split("|")]
            if all(re.fullmatch(r":?-{3,}:?", x) for x in cells):
                continue
            if not header:
                if cells != TABLES[section]:
                    raise ValueError(f"Invalid {section} columns")
                header = True
            else:
                if len(cells) != len(TABLES[section]):
                    raise ValueError(f"Invalid {section} row")
                rows[section].append(dict(zip(TABLES[section], cells)))
    settings = {}
    for row in rows["PLCWeave"]:
        if row["key"] in settings:
            raise ValueError("Duplicate PLCWeave key")
        settings[row["key"]] = row["value"]
    required = {"target", "protocol", "program_version", "edition", "suite_word", "reset_ms"}
    if set(settings) != required:
        raise ValueError("Incomplete/unknown PLCWeave settings")
    if settings["target"] not in {"l01s", "fx3u"}:
        raise ValueError("UNSUPPORTED target; Delta WPLSoft/ISPSoft adapter is not implemented")
    if settings["protocol"] != "l01s-modbus-rtu":
        raise ValueError("UNSUPPORTED HIL protocol; verify a target register profile first")
    for key in ("program_version", "edition", "suite_word", "reset_ms"):
        if not re.fullmatch(r"[1-9]\d*", settings[key]):
            raise ValueError(f"Invalid {key}")
        settings[key] = int(settings[key])
        if settings[key] > (60000 if key == "reset_ms" else 32767):
            raise ValueError(f"Out-of-range {key}")
    inputs, outputs = rows["Inputs"], rows["Outputs"]
    if not inputs or not outputs:
        raise ValueError("Complete Inputs and Outputs resource tables before freezing")
    used, physical, injections = set(), set(), set()
    for row in inputs + outputs:
        logical = row["logical"]
        kind = _internal(logical)
        if logical in used or row["physical"] in physical:
            raise ValueError("Duplicate logical/physical resource")
        used.add(logical)
        physical.add(row["physical"])
        if kind != _physical(row["physical"], output="injection" not in row):
            raise ValueError("Logical and physical types differ")
        if "injection" in row:
            address = row["injection"]
            if _internal(address) != "word" or address in injections:
                raise ValueError("Each input needs a unique internal D injection register")
            injections.add(address)
    if injections & used:
        raise ValueError("Injection registers overlap the control image")
    values = {}
    for name in ("HIL reset", "Reset expectations", "HIL cleanup", "Cleanup expectations"):
        table = {}
        for row in rows[name]:
            device, value = row["device"], row["value"]
            kind = _internal(device)
            if device in table or not re.fullmatch(r"-?\d+", value):
                raise ValueError(f"Invalid/duplicate {name} value")
            table[device] = int(value)
            if not -32768 <= table[device] <= 32767 or kind == "bit" and table[device] not in {0, 1}:
                raise ValueError(f"Out-of-range {name} value")
        if not table:
            raise ValueError(f"Missing {name}")
        if name in {"HIL reset", "HIL cleanup"} and set(table) != injections:
            raise ValueError(f"{name} must specify every injection register, and nothing else")
        values[name] = table
    output_images = {row["logical"] for row in outputs}
    for name in ("Reset expectations", "Cleanup expectations"):
        if not output_images <= set(values[name]):
            raise ValueError(f"{name} must check every declared logical output")
    for row in inputs:
        if _internal(row["logical"]) == "bit":
            for name in ("HIL reset", "HIL cleanup"):
                if values[name][row["injection"]] not in {0, 1}:
                    raise ValueError("Bit injections must be 0 or 1")
    return {"settings": settings, "inputs": inputs, "outputs": outputs, **values}


def validate_core(path, design):
    metadata, instructions, comments = parse_fxil(path)
    injections = {row["injection"] for row in design["inputs"]}
    input_images = {row["logical"] for row in design["inputs"]}
    # A narrow, explicit instruction signature table keeps hidden I/O writes,
    # indirect addressing and block/double-word overlaps out of this adapter.
    signatures = {
        "LD": (1, None), "LDI": (1, None), "AND": (1, None), "ANI": (1, None),
        "OR": (1, None), "ORI": (1, None), "MPS": (0, None), "MRD": (0, None),
        "MPP": (0, None), "ANB": (0, None), "ORB": (0, None),
        "MOV": (2, 1), "ADD": (3, 2), "SUB": (3, 2), "MUL": (3, 2),
        "OUT": (None, 0), "SET": (1, 0), "RST": (1, 0), "END": (0, None),
    }
    for row in instructions:
        op, operands = row["mnemonic"], row["operands"]
        signature = signatures.get(op)
        if re.fullmatch(r"(?:LD|AND|OR)(?:=|<>|<=|>=|<|>)", op):
            signature = (2, None)
        if signature is None:
            raise ValueError(f"UNSUPPORTED common-core instruction: {op}")
        count, destination = signature
        if count is not None and len(operands) != count or op == "OUT" and len(operands) not in {1, 2}:
            raise ValueError(f"Invalid operands for {op}")
        for value in operands:
            if re.fullmatch(r"K-?\d+|H[0-9A-Fa-f]+|[TC](?:0|[1-9]\d*)", value):
                continue
            if value in {"M8000", "M8001", "M8002", "M8011", "M8012", "M8013"}:
                continue
            _internal(value)
            if value in injections:
                raise ValueError("Common core cannot access test injection registers")
        if destination is not None:
            dest = operands[destination]
            if dest in input_images or dest.startswith("M8") and int(dest[1:]) >= 8000:
                raise ValueError("Common core cannot write input images or system relays")
            if not re.fullmatch(r"[MDTC]\d+", dest):
                raise ValueError("Expected a writable device")
            if op == "MUL":
                # FX MUL writes a double-word result. Reject overlap of its high word.
                if not dest.startswith("D"):
                    raise ValueError("MUL destination must be D")
                high = f"D{int(dest[1:])+1}"
                _internal(high)
                if high in injections | input_images:
                    raise ValueError("MUL high word overlaps a protected resource")
    return metadata, instructions, comments


def render_variant(core, design, variant, *, serial_word, station, fingerprint=(0, 0)):
    if variant not in {"hil", "production"}:
        raise ValueError("Unknown program variant")
    metadata, instructions, comments = validate_core(core, design)
    lines = ["#meta", f"project: {metadata.get('project', 'PLCWeave')}-{variant}",
             f"version: {design['settings']['program_version']}", "#instructions"]
    if variant == "hil":
        settings = design["settings"]
        lines += ["LD M8002", "SET M8196", "SET M8125", f"MOV H{serial_word:04X} D8120",
                  f"MOV K{station} D8121", "// BEGIN_IDENTITY", "LD M8002",
                  f"MOV K{settings['program_version']} D196", f"MOV K{settings['edition']} D197",
                  f"MOV K{fingerprint[0]} D200", f"MOV K{fingerprint[1]} D201",
                  f"MOV K{settings['suite_word']} D202", "// END_IDENTITY",
                  "LD M8000", "ADD D198 K1 D198"]
    lines += ["// BEGIN_INPUT_IMAGE"]
    for row in design["inputs"]:
        source = row["injection"] if variant == "hil" else row["physical"]
        if _internal(row["logical"]) == "word":
            lines += ["LD M8000", f"MOV {source} {row['logical']}"]
        else:
            lines += (["LD M8000", f"AND= {source} K1"] if variant == "hil" else [f"LD {source}"])
            lines += [f"OUT {row['logical']}"]
    lines += ["// END_INPUT_IMAGE", "// BEGIN_CONTROL_CORE"]
    lines += [" ".join([row["mnemonic"], *row["operands"]]) for row in instructions[:-1]]
    lines += ["// END_CONTROL_CORE"]
    if variant == "production":
        for row in design["outputs"]:
            if _internal(row["logical"]) == "word":
                lines += ["LD M8000", f"MOV {row['logical']} {row['physical']}"]
            else:
                lines += [f"LD {row['logical']}", f"OUT {row['physical']}"]
    lines += ["END", "#comments"]
    lines += [f"{name} {text}" for name, text in comments]
    return "\n".join(lines) + "\n"
