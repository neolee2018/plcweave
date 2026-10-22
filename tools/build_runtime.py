"""Build the vendored development binding into the local project venv."""
import os
import shutil
import subprocess
from pathlib import Path

root=Path(__file__).resolve().parents[1]
environment=os.environ.copy()
environment["CARGO_TARGET_DIR"]=str(root/"target")
environment["PYO3_PYTHON"]=str(root/".venv/Scripts/python.exe")
subprocess.run(["cargo","build","--manifest-path",str(root/"vendor/gxwlib/Cargo.toml"),"-p","gxw-python","--offline"],env=environment,cwd=root,check=True,timeout=120)
package=root/".venv/Lib/site-packages/gxwlib"
shutil.copytree(root/"vendor/gxwlib/src/gxwlib",package,dirs_exist_ok=True)
shutil.copy2(root/"target/debug/_core.dll",package/"_core.pyd")
print("Development runtime built into project .venv")
