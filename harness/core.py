import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import uuid

ROOT = Path.cwd()
RESULTS = ROOT / ".harness/results"
CODES = {"PASS": 0, "FAIL": 1, "BLOCKED": 2, "NOT_CONFIGURED": 3}


def fingerprint():
    files = subprocess.check_output(["git", "ls-files", "-co", "--exclude-standard", "-z"])
    digest = hashlib.sha256()
    for name in sorted(set(files.split(b"\0")) - {b""}):
        path = Path(os.fsdecode(name))
        if path.is_symlink():
            data = b"L" + os.fsencode(os.readlink(path))
        elif path.is_file():
            data = str(path.stat().st_mode).encode() + path.read_bytes()
        else:
            data = b"missing"
        digest.update(name + b"\0" + hashlib.sha256(data).digest())
    return digest.hexdigest()


def plan(target):
    if target == "template":
        return [{"id": "contract", "argv": [sys.executable, "-m", "unittest", "discover", "-s", "tests"], "required": True}]
    path = Path("harness/project.json")
    if not path.exists():
        return []
    config = json.loads(path.read_text())
    if set(config) != {"version", "checks"} or type(config["version"]) is not int or config["version"] != 1:
        raise ValueError()
    checks = config["checks"]
    if not isinstance(checks, list):
        raise ValueError()
    ordered = []
    ids = set()
    for c in checks:
        if set(c) - {"id","argv","required","depends","timeout"} or not isinstance(c["id"], str) or not c["id"].isascii() or not c["id"].isidentifier() or c["id"] in ids:
            raise ValueError()
        if type(c["required"]) is not bool or not isinstance(c["argv"], list) or not c["argv"] or not all(isinstance(x,str) for x in c["argv"]):
            raise ValueError()
        if type(c.get("timeout",120)) is not int or c.get("timeout",120) <= 0 or not isinstance(c.get("depends",[]),list):
            raise ValueError()
        ids.add(c["id"])
    done = set()
    while len(ordered) < len(checks):
        ready = [c for c in checks if c["id"] not in done and set(c.get("depends",[])) <= done]
        if not ready:
            raise ValueError()
        ordered.extend(ready)
        done.update(c["id"] for c in ready)
    return ordered


def execute(c):
    try:
        with subprocess.Popen(c["argv"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True) as proc:
            try:
                code = proc.wait(timeout=c.get("timeout",120))
            except BaseException:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                raise
        return ("PASS" if code == 0 else "FAIL", code)
    except (OSError, subprocess.TimeoutExpired):
        return "BLOCKED", None


def validate(target, record):
    checks = plan(target)
    if record["target"] != target or record["digest"] != fingerprint() or record["commit"] != commit():
        return "BLOCKED"
    rows = record["checks"]
    if [r["id"] for r in rows] != [c["id"] for c in checks]:
        return "BLOCKED"
    seen = {}
    for c,r in zip(checks,rows):
        state, code = r["state"], r["code"]
        skipped = any(seen[d] != "PASS" for d in c.get("depends",[]))
        if skipped != (state == "SKIPPED") or state not in {"PASS","FAIL","BLOCKED","SKIPPED"}:
            return "BLOCKED"
        if state in {"PASS","FAIL"}:
            if type(code) is not int or (state == "PASS") != (code == 0):
                return "BLOCKED"
        elif code is not None:
            return "BLOCKED"
        seen[c["id"]] = state
    required = [seen[c["id"]] for c in checks if c["required"]]
    if not required:
        return "NOT_CONFIGURED"
    if "BLOCKED" in required or ("SKIPPED" in required and "FAIL" not in required):
        return "BLOCKED"
    return "FAIL" if "FAIL" in required else "PASS"


def commit():
    return subprocess.check_output(["git","rev-parse","HEAD"],text=True).strip()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("action", choices=["verify","evaluate","bootstrap"])
    p.add_argument("--target", choices=["template","project"])
    p.add_argument("--results", type=Path)
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()
    if a.action == "bootstrap":
        path = Path("harness/project.json")
        if path.exists():
            plan("project")
            print("Existing configuration preserved")
        else:
            print("Create harness/project.json with no configured checks")
            if not a.dry_run:
                with path.open("x") as f:
                    f.write('{"version":1,"checks":[]}\n')
        return 0
    if not a.target:
        p.error("--target required")
    if a.action == "evaluate":
        record = json.loads((a.results / "result.json").read_text())
        state = validate(a.target,record)
        if record["state"] != state:
            state = "BLOCKED"
    else:
        checks = plan(a.target)
        record = dict(target=a.target, digest=fingerprint(), commit=commit(), checks=[], started=time.time())
        states = {}
        directory = RESULTS / uuid.uuid4().hex
        directory.mkdir(parents=True)
        for c in checks:
            state,code = ("SKIPPED",None) if any(states[d] != "PASS" for d in c.get("depends",[])) else execute(c)
            states[c["id"]] = state
            record["checks"].append(dict(id=c["id"],state=state,code=code))
        state = validate(a.target,record)
        record.update(state=state,finished=time.time())
        (directory/"summary.md").write_text(f"# {a.target}: {state}\n")
        temp = directory/"result.tmp"
        temp.write_text(json.dumps(record))
        temp.replace(directory/"result.json")
        print(directory)
    print(state)
    return CODES[state]


if __name__ == "__main__":
    try:
        signal.signal(signal.SIGTERM, lambda *_: sys.exit(2))
        sys.exit(main())
    except (Exception, KeyboardInterrupt):
        print("BLOCKED", file=sys.stderr)
        sys.exit(2)
