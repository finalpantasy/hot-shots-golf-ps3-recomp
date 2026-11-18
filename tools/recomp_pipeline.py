import argparse
import hashlib
import json
import os
import subprocess
import sys
import tomllib
from datetime import datetime, timezone
from pathlib import Path
from string import Template


def hash_paths(root, paths):
    digest = hashlib.sha256()
    for relative in sorted(paths):
        path = root / relative
        digest.update(relative.replace("\\", "/").encode("utf-8"))
        if path.is_file():
            digest.update(b"file\0")
            with path.open("rb") as source:
                for chunk in iter(lambda: source.read(8 * 1024 * 1024), b""):
                    digest.update(chunk)
        elif path.is_dir():
            for child in sorted(p for p in path.rglob("*") if p.is_file() and ".git" not in p.parts):
                digest.update(str(child.relative_to(path)).replace("\\", "/").encode("utf-8"))
                with child.open("rb") as source:
                    for chunk in iter(lambda: source.read(8 * 1024 * 1024), b""):
                        digest.update(chunk)
        else:
            digest.update(b"missing\0")
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("stages", nargs="*", default=["analyze", "spu", "lift", "build"])
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    config = tomllib.loads((root / "pipeline.toml").read_text(encoding="utf-8"))
    lock_path = root / "config/generated.lock"
    lock = json.loads(lock_path.read_text(encoding="utf-8")) if lock_path.exists() else {"stages": {}}
    values = dict(config["toolchain"])
    values["root"] = str(root).replace("\\", "/")
    selected = {stage["name"]: stage for stage in config["stages"]}
    for name in args.stages:
        if name not in selected:
            raise SystemExit(f"unknown stage: {name}")
        stage = selected[name]
        fingerprint = hashlib.sha256()
        fingerprint.update(json.dumps(stage["commands"]).encode("utf-8"))
        fingerprint.update(hash_paths(root, stage["inputs"]).encode("ascii"))
        stage_hash = fingerprint.hexdigest()
        previous = lock["stages"].get(name)
        output_hash = hash_paths(root, stage["outputs"])
        if not args.force and previous and previous["fingerprint"] == stage_hash and previous["outputs"] == output_hash:
            print(f"[skip] {name}: inputs and outputs unchanged")
            continue
        print(f"[run] {name}")
        for template in stage["commands"]:
            command = [Template(part).substitute(values) for part in template]
            # CreateProcess did not resolve a relative executable against cwd
            # here (WinError 2 on 2026-11-17), so launch it by absolute path.
            if (root / command[0]).is_file():
                command[0] = str(root / command[0])
            print(" ".join(command), flush=True)
            environment = os.environ.copy()
            environment["PYTHONIOENCODING"] = "utf-8"
            tool_paths = [root / ".venv/Scripts", root / "external/llvm-mingw/bin"]
            environment["PATH"] = os.pathsep.join(str(path) for path in tool_paths) + os.pathsep + environment["PATH"]
            subprocess.run(command, cwd=root, env=environment, check=True)
        lock["stages"][name] = {
            "fingerprint": stage_hash,
            "outputs": hash_paths(root, stage["outputs"]),
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path.write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")
        print(f"[done] {name}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    main()
