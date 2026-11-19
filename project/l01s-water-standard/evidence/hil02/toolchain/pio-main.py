"""Original PlatformIO adapter; no native L01S uploader is represented."""
import os
import subprocess
from pathlib import Path
from SCons.Script import Default, DefaultEnvironment

env=DefaultEnvironment()
case=Path(env.subst("$PROJECT_DIR")).resolve()
root=Path(env.GetProjectOption("custom_workspace")).resolve()
python=root/".venv/Scripts/python.exe"

def command(name):
    def action(source,target,env):
        process_env=os.environ.copy()
        process_env["PYTHONPATH"]=str(root/"src")
        try:
            return subprocess.run([str(python),"-m","plcweave",name,str(case)],cwd=root,env=process_env,timeout=600).returncode
        except subprocess.TimeoutExpired:
            print("TEST_INFRA_ERROR: PlatformIO task exceeded 600 seconds; task subprocess terminated.")
            return 2
    return action

validate=env.AddCustomTarget("simulate",None,command("simulate"),title="Simulate",description="Run frozen cases on the instruction runtime")
env.AddCustomTarget("preflight",None,command("preflight"),title="Read-only preflight",description="Check Modbus identity and heartbeat; no writes")

def bench_action(source,target,env):
    configured=env.GetProjectOption("custom_hil_script", "")
    script=(case/configured).resolve()
    if not configured or not script.is_relative_to(case) or not script.is_file():
        print("TEST_INFRA_ERROR: an existing case-local qualified HIL script is required.")
        return 2
    process_env=os.environ.copy()
    process_env["PYTHONPATH"]=str(root/"src")
    arguments=[str(python),str(script),"--isolated-bench"]
    output_name=env.GetProjectOption("custom_hil_output", "")
    if output_name:
        arguments.extend(["--output-name",output_name])
    try:
        return subprocess.run(arguments,cwd=root,env=process_env,timeout=1800).returncode
    except subprocess.TimeoutExpired:
        print("TEST_INFRA_ERROR: qualified bench task exceeded 1800 seconds.")
        return 2

env.AddCustomTarget("bench",None,bench_action,title="Qualified isolated bench",description="Explicitly execute the configured frozen isolated-bench procedures")

def manual_gate(source,target,env):
    print("UNVERIFIED: no validated L01S application compiler/downloader was found.")
    print("Manual download is required. No serial write or MCU firmware operation was attempted.")
    return 2

env.AddCustomTarget("upload",None,manual_gate,title="Manual download required",description="Fail closed until a validated application-program downloader is supplied")
Default(validate)
