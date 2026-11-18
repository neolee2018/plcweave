"""One-time, hash-first import of the authorized local S2 runtime.

Usage: python tools/import_runtime.py <path-to-102-plc-s2-engine>
       (or set PLCWEAVE_UPSTREAM_S2). The upstream path is machine-specific
       and is never hard-coded here.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = Path(sys.argv[1] if len(sys.argv) > 1 else os.environ.get("PLCWEAVE_UPSTREAM_S2", ""))
SOURCE = UPSTREAM / "vendor/gxwlib"
TARGET = ROOT / "vendor/gxwlib"

def main():
    if not UPSTREAM.is_dir():
        raise SystemExit("Upstream 102-plc-s2-engine path required: pass it as argv[1] or set PLCWEAVE_UPSTREAM_S2")
    if TARGET.exists():
        raise SystemExit("Refusing to overwrite an existing runtime import")
    commit = subprocess.check_output(["git", "-C", str(UPSTREAM), "rev-parse", "HEAD"], text=True).strip()
    records = []
    for path in SOURCE.rglob("*"):
        relative = path.relative_to(SOURCE)
        if not path.is_file() or any(x in {"target", ".git", "__pycache__"} for x in relative.parts):
            continue
        records.append({"path": relative.as_posix(), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    provenance = {"source": str(SOURCE), "local_commit": commit,
                  "upstream_commit": "1e9a8d7542665e5015041d361e4bb86d7650714f",
                  "license": "MIT; nested Apache-2.0 and third-party notices retained",
                  "planned_modifications": ["FX3U comparison contacts", "SUB/MUL/DIV", "L01S external word image"],
                  "files_before_modification": records}
    (ROOT / "docs/runtime-provenance.json").write_text(json.dumps(provenance, indent=2), encoding="utf-8")
    # The provenance is persisted before copying any source file.
    for record in records:
        dst = TARGET / record["path"]
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(SOURCE / record["path"], dst)
    (TARGET / "HBDTECH-S2-NOTICE.md").write_text((UPSTREAM / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8"), encoding="utf-8")
    print("Imported", len(records), "files from", commit)

if __name__ == "__main__":
    main()
