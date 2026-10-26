"""FX list artifacts with separate import and runtime CSV dialects."""
import csv
import io
from pathlib import Path

HEADER = ["Step No.", "Line Statement", "Instruction", "I/O(Device)", "Blank", "PI Statement", "Note"]

def parse_fxil(path):
    metadata, instructions, comments = {}, [], []
    section = None
    for number, raw in enumerate(Path(path).read_text(encoding="utf-8-sig").splitlines(), 1):
        line = raw.split("//", 1)[0].strip()
        if not line or line.startswith("#"):
            if line in ("#meta", "#instructions", "#comments"):
                section = line
            continue
        if section == "#meta":
            key, value = line.split(":", 1)
            metadata[key.strip()] = value.strip()
        elif section == "#instructions":
            fields = line.split()
            instructions.append({"mnemonic": fields[0].upper(), "operands": fields[1:], "line": number})
        elif section == "#comments":
            fields = line.split(None, 1)
            comments.append((fields[0], fields[1] if len(fields) == 2 else ""))
        else:
            raise ValueError(f"line {number}: content outside a section")
    if not instructions or instructions[-1]["mnemonic"] != "END":
        raise ValueError("Exactly one terminal END is required")
    if sum(x["mnemonic"] == "END" for x in instructions) != 1:
        raise ValueError("Unexpected END")
    return metadata, instructions, comments

def write_program(path, instructions, project="PLCWeave", quoted=False):
    rows = [[project, "", "", "", "", "", ""], ["PLC Information:", "FXCPU FX3U/FX3UC", "", "", "", "", ""], HEADER]
    if quoted:
        rows[0] = [project]
        rows[1] = ["PC Information:", "FXCPU FX3U/FX3UC"]
    for instruction in instructions:
        operands = instruction["operands"]
        rows.append(["", "", instruction["mnemonic"], operands[0] if operands else "", "", "", ""])
        rows.extend([["", "", "", operand, "", "", ""] for operand in operands[1:]])
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, delimiter="\t", lineterminator="\r\n", quoting=csv.QUOTE_ALL if quoted else csv.QUOTE_NONE)
    writer.writerows(rows)
    Path(path).write_bytes(buffer.getvalue().encode("utf-16"))

def export(source, output):
    metadata, instructions, comments = parse_fxil(source)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    project = metadata.get("project", "PLCWeave")
    write_program(output / "MAIN.csv", instructions, project, quoted=True)
    write_program(output / "runtime.csv", instructions, project, quoted=True)
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, delimiter="\t", lineterminator="\r\n", quoting=csv.QUOTE_ALL)
    writer.writerow([metadata.get("comment_project", project)])
    writer.writerow(["Device Name", "Comment"])
    writer.writerows(comments)
    (output / "COMMENT.csv").write_bytes(buffer.getvalue().encode("utf-16"))
    return instructions
