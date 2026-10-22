import argparse
import json
from .testing import simulate

def main():
    parser=argparse.ArgumentParser(description="PLCWeave deterministic case runner")
    parser.add_argument("command",choices=["init","freeze","package","simulate","preflight","hil"])
    parser.add_argument("case_directory")
    parser.add_argument("--isolated-bench",action="store_true")
    parser.add_argument("--directory",help="Explicit customer project directory for init")
    parser.add_argument("--version",default="V001")
    parser.add_argument("--file",action="append",default=[],help="Project-relative deliverable; repeat to select files")
    args=parser.parse_args()
    if args.command=='init':
        from .projects import create_project
        print(create_project(args.case_directory,directory=args.directory))
        return 0
    if args.command=='freeze':
        from .markdown_suite import freeze_markdown
        print(freeze_markdown(args.case_directory))
        return 0
    if args.command=='package':
        from .projects import package_delivery
        result=package_delivery(args.case_directory,args.version,args.file)
        print(json.dumps({k:str(v) for k,v in result.items()},ensure_ascii=False))
        return 0
    if args.command=="simulate":
        report=simulate(args.case_directory)
    else:
        from .hil import preflight,run
        report=preflight(args.case_directory) if args.command=="preflight" else run(args.case_directory,args.isolated_bench)
    print(json.dumps({"status":report["status"],"cases":len(report.get("cases",[]))}))
    return 0 if report["status"] in {"SIM_PASS","PROTOCOL_READ_PASS"} else 1

if __name__=="__main__":
    raise SystemExit(main())
