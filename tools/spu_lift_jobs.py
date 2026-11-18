#!/usr/bin/env python3
"""Lift raw SPURS job binaries embedded in a PPU ELF and register them by fingerprint.

build_spu_workloads.py --input only finds embedded SPU *ELFs*. A SPURS job
binary (job_start_w_crt layout) is a raw local-store image the title hands to
cellSpurs by EA and size, so the runtime's job dispatcher
(spu_workload_dispatch_job) fingerprints exactly those bytes with FNV-1a-64 and
looks the result up in the spu_workload registry. This tool:

  1. reads each job listed in the manifest out of the input ELF by EA and size,
     and checks its FNV-1a-64 fingerprint (and, if present, that the runtime
     SPU_DUMP_MISS dump is byte-identical);
  2. seeds functions with ps3recomp's find_spu_functions (raw mode, base 0,
     which is where spurs_job.c loads every job), keeps only the code ranges
     the manifest states, and adds the manifest's extra entries;
  3. lifts with ps3recomp's spu_lifter.py under a per-job symbol prefix;
  4. applies the same strict checks as ps3recomp's spu_program_pipeline.py
     (no unsupported instructions, no TODO, entry generated, every function
     inside a code range, every direct branch/call target has an entry), plus:
     every instruction in a code range that is left out of a function must be
     lnop/nop padding;
  5. writes <lifted>/<name>/spu_recomp.{c,h}, a registration TU (--out) that
     calls spu_workload_register_img() from a constructor, and an inventory.

Nothing is registered unless every job passes. Run after build_spu_workloads
(the spu stage), because that tool replaces the whole --lifted directory.
"""
import argparse, hashlib, json, os, re, shutil, struct, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PADDING = {"lnop", "nop"}


def fnv1a64(data):
    h = 1469598103934665603
    for x in data:
        h = ((h ^ x) * 1099511628211) & 0xFFFFFFFFFFFFFFFF
    return h


def num(v):
    return int(v, 0) if isinstance(v, str) else int(v)


def read_ea(elf, ea, size):
    """Bytes at [ea, ea+size) from a big-endian ELF64 PPU file's PT_LOAD filesz."""
    if elf[:4] != b"\x7fELF" or elf[4] != 2 or elf[5] != 2:
        raise ValueError("input is not a big-endian ELF64")
    phoff = struct.unpack(">Q", elf[0x20:0x28])[0]
    phentsize, phnum = struct.unpack(">HH", elf[0x36:0x3A])
    for i in range(phnum):
        p = elf[phoff + i * phentsize: phoff + (i + 1) * phentsize]
        ptype, _, off, vaddr, _, filesz = struct.unpack(">IIQQQQ", p[:0x28])
        if ptype == 1 and vaddr <= ea and ea + size <= vaddr + filesz:
            return elf[off + ea - vaddr: off + ea - vaddr + size], off + ea - vaddr
    raise ValueError(f"EA 0x{ea:X}+0x{size:X} is not inside one PT_LOAD file image")


def lift_one(job, elf, args, stage, tools):
    from find_spu_functions import detect_functions
    from spu_disasm import disassemble_spu
    from build_spu_workloads import debase_includes

    ea, size, entry = num(job["ea"]), num(job["size"]), num(job["entry"])
    blob, file_off = read_ea(elf, ea, size)
    fp = fnv1a64(blob)
    want = int(job["fingerprint"], 16)
    if fp != want:
        raise ValueError(f"fingerprint 0x{fp:016X} != manifest 0x{want:016X}")
    digest = hashlib.sha256(blob).hexdigest()
    name = f"spujob_{fp:016X}"
    prefix = name + "_"
    image_id = 0x10000000 | int(digest[:7], 16)   # spu_program_pipeline's convention
    rec = dict(name=name, ea=f"0x{ea:08X}", file_offset=f"0x{file_off:X}", size=size,
               sha256=digest, fingerprint=f"{fp:016X}", image_id=image_id,
               entry=entry, status="discovered")

    dump = job.get("runtime_dump")
    if dump:
        dump_path = ROOT / dump
        if dump_path.is_file():
            if dump_path.read_bytes() != blob:
                raise ValueError(f"runtime dump {dump} differs from the ELF bytes")
            rec["runtime_dump"] = "identical"
        else:
            rec["runtime_dump"] = "absent (not compared)"

    ranges = sorted((num(a), num(b)) for a, b in job["code_ranges"])
    for (a, b), (c, _) in zip(ranges, ranges[1:]):
        if b > c:
            raise ValueError("overlapping code ranges")
    if any(a % 4 or b % 4 or a < 0 or b > size or a >= b for a, b in ranges):
        raise ValueError("code range outside the image or misaligned")
    if not any(a <= entry < b for a, b in ranges):
        raise ValueError("entry is outside the code ranges")

    def in_code(x):
        return any(a <= x < b for a, b in ranges)

    seeds, _ = detect_functions(blob, 0, verbose=False, raw=True)
    bounds = sorted({(max(s, a), min(e, b)) for s, e in seeds for a, b in ranges
                     if max(s, a) < min(e, b)})
    rec["dropped_seeds"] = [f"0x{s:X}" for s, e in seeds if not any(
        max(s, a) < min(e, b) for a, b in ranges)]
    starts = sorted({s for s, _ in bounds})
    for x in (num(v) for v in job.get("extra_entries", [])):
        if x % 4 or not in_code(x):
            raise ValueError(f"extra entry 0x{x:X} is outside the code ranges")
        if any(s <= x < e for s, e in bounds):
            raise ValueError(f"extra entry 0x{x:X} is inside an existing function")
        rng_end = next(b for a, b in ranges if a <= x < b)
        end = min([s for s in starts if s > x] + [rng_end])
        bounds.append((x, end))
    bounds.sort()
    if entry not in {s for s, _ in bounds}:
        bounds.append((entry, min([s for s, _ in bounds if s > entry] +
                                  [next(b for a, b in ranges if a <= entry < b)])))
        bounds.sort()

    outdir = stage / name
    outdir.mkdir()
    (outdir / "image.bin").write_bytes(blob)
    (outdir / "functions.json").write_text(json.dumps([dict(start=s, end=e) for s, e in bounds]))
    cmd = [sys.executable, str(tools / "spu_lifter.py"), str(outdir / "image.bin"),
           "--base", "0", "--functions", str(outdir / "functions.json"),
           "--symbol-prefix", prefix, "--report", str(outdir / "lift.json"),
           "--output", str(outdir)]
    res = subprocess.run(cmd, capture_output=True, text=True)
    (outdir / "lift.log").write_text(res.stdout + res.stderr)
    if res.returncode:
        raise ValueError("lifter failed; see lift.log")

    # ---- strict checks (spu_program_pipeline.py's, plus padding-only gaps) ----
    diag = json.loads((outdir / "lift.json").read_text())
    if diag["unsupported"]:
        raise ValueError(f"unsupported instructions emitted: {diag['unsupported']}")
    fstarts = {s for s, _ in diag["functions"]}
    if entry not in fstarts:
        raise ValueError("lifter did not generate the entry")
    if any(not any(a <= s < e <= b for a, b in ranges) for s, e in diag["functions"]):
        raise ValueError("generated function extends beyond the code ranges")
    missing = (set(diag["call_targets"]) | set(diag["branch_targets"])) - fstarts
    if missing:
        raise ValueError("direct branch/call targets lack entries: " +
                         ", ".join(f"0x{x:X}" for x in sorted(missing)))
    src = (outdir / "spu_recomp.c").read_text(encoding="utf-8", errors="ignore")
    if "/* TODO spu:" in src:
        raise ValueError("unresolved instruction or branch emitted by lifter")
    covered = set()
    for s, e in diag["functions"]:
        covered.update(range(s, e, 4))
    insns = {i.addr: i for i in disassemble_spu(blob, base_addr=0)}
    gaps = []
    for a, b in ranges:
        for x in range(a, b, 4):
            if x not in covered:
                if insns[x].mnemonic not in PADDING:
                    raise ValueError(f"code at 0x{x:X} ({insns[x].mnemonic}) is in no function")
                gaps.append(x)
    hdr = (outdir / "spu_recomp.h").read_text(encoding="utf-8", errors="ignore")
    if f"{prefix}spu_func_{entry:08X}(" not in hdr:
        raise ValueError("generated header is missing the entry symbol")
    for fn in ("spu_recomp.c", "spu_recomp.h"):
        debase_includes(str(outdir / fn))

    code_bytes = sum(b - a for a, b in ranges)
    rec.update(status="registered", functions=len(diag["functions"]),
               code_ranges=[[f"0x{a:X}", f"0x{b:X}"] for a, b in ranges],
               code_bytes=code_bytes, lifted_bytes=len(covered) * 4,
               padding_words_unlifted=len(gaps), data_bytes=size - code_bytes,
               unsupported=0, call_targets=len(diag["call_targets"]),
               branch_targets=len(diag["branch_targets"]))
    return rec, prefix


def write_registry(path, regs, register_fn):
    L = [f"/* {path.name} -- GENERATED by tools/spu_lift_jobs.py from tools/spu_jobs.json.",
         " * Registers each lifted SPURS job binary with the spu_workload registry under the",
         " * FNV-1a-64 fingerprint of the job image (the bytes cellSpurs passes to",
         " * spu_workload_dispatch_job: eaBinary, sizeBinary<<4) and binds its",
         " * indirect-branch table under a distinct image id. The job runs through",
         " * spu_run_spurs_job, which copies the image to LS 0 and enters it there. */",
         '#include "spu_workload.h"', "", "extern void spu_begin_image(int image_id);", ""]
    for r, prefix in regs:
        L.append(f"extern void {prefix}spu_func_{r['entry']:08X}(spu_context*);")
        L.append(f"extern void {prefix}spu_recomp_register(void);")
    L += ["", f"void {register_fn}(void)", "{"]
    for r, prefix in regs:
        L.append(f"    /* EA {r['ea']}, {r['size']} bytes, sha256 {r['sha256'][:16]}... */")
        L.append(f"    spu_begin_image({r['image_id']}); {prefix}spu_recomp_register();")
        L.append(f"    spu_workload_register_img(0x{r['fingerprint']}ULL, {prefix}spu_func_{r['entry']:08X}, "
                 f"{r['image_id']}, \"{r['name']}\");")
    L += ["    spu_begin_image(0);", "}", "",
          "/* Before the game creates any job chain. */",
          f"__attribute__((constructor)) static void {register_fn}_ctor(void)", "{",
          f"    {register_fn}();", "}", ""]
    path.write_text("\n".join(L), encoding="utf-8", newline="\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest", default="tools/spu_jobs.json")
    ap.add_argument("--lifted", default="port/spu", help="directory receiving <name>/spu_recomp.c")
    ap.add_argument("--out", default="port/spu/spu_jobs_register.c")
    ap.add_argument("--register-fn", default="port_spu_jobs_register_all")
    ap.add_argument("--ps3recomp", default="external/ps3recomp")
    args = ap.parse_args()

    tools = (ROOT / args.ps3recomp / "tools").resolve()
    sys.path.insert(0, str(tools))
    manifest = json.loads((ROOT / args.manifest).read_text(encoding="utf-8"))
    elf = (ROOT / manifest["input"]).read_bytes()
    lifted = (ROOT / args.lifted).resolve()
    out = (ROOT / args.out).resolve()
    if out.parent != lifted:
        raise SystemExit("--out must be directly inside --lifted")
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", args.register_fn):
        raise SystemExit("--register-fn must be a C identifier")
    lifted.mkdir(parents=True, exist_ok=True)

    stage = Path(tempfile.mkdtemp(prefix="spu_jobs.stage-", dir=lifted.parent))
    report = dict(schema_version=1, generator="spu_lift_jobs", manifest=args.manifest,
                  input=manifest["input"], input_sha256=hashlib.sha256(elf).hexdigest(),
                  jobs=[], complete=False)
    regs, failed = [], False
    try:
        for job in manifest["jobs"]:
            try:
                rec, prefix = lift_one(job, elf, args, stage, tools)
                regs.append((rec, prefix))
                report["jobs"].append(rec)
            except (ValueError, OSError, KeyError) as error:
                failed = True
                report["jobs"].append(dict(ea=job.get("ea"), fingerprint=job.get("fingerprint"),
                                           status="unsupported", reason=str(error)))
        ids = [r["image_id"] for r, _ in regs]
        fps = [r["fingerprint"] for r, _ in regs]
        if len(set(ids)) != len(ids) or len(set(fps)) != len(fps):
            failed = True
            report["error"] = "image id or fingerprint collision"
        report["complete"] = not failed
        # Replace previous outputs of this tool only.
        for old in lifted.glob("spujob_*"):
            if old.is_dir():
                shutil.rmtree(old)
        for name in (out.name, "spu_jobs_inventory.json"):
            (lifted / name).unlink(missing_ok=True)
        if not failed:
            for r, _ in regs:
                shutil.move(str(stage / r["name"]), str(lifted / r["name"]))
            write_registry(out, regs, args.register_fn)
        (lifted / "spu_jobs_inventory.json").write_text(json.dumps(report, indent=2) + "\n")
    finally:
        shutil.rmtree(stage, ignore_errors=True)

    for r in report["jobs"]:
        if r["status"] == "registered":
            print(f"[spu_lift_jobs] {r['name']} EA {r['ea']} {r['size']} B: {r['functions']} functions, "
                  f"{r['lifted_bytes']}/{r['code_bytes']} code bytes lifted "
                  f"({r['padding_words_unlifted']} padding words), image id {r['image_id']}")
        else:
            print(f"[spu_lift_jobs] EA {r['ea']}: FAILED: {r['reason']}", file=sys.stderr)
    if failed:
        print("[spu_lift_jobs] nothing registered", file=sys.stderr)
        return 1
    print(f"[spu_lift_jobs] wrote {out.relative_to(ROOT)} ({len(regs)} job(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
