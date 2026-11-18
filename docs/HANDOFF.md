# Pinned lead orchestrator handoff — Hot Shots Golf PS3 recomp

Prepared 2026-11-17. Recipient: Claude, continuing worker and integration owner. Delivery: shared workspace `F:\Hotshots Golf`.

## Your first actions: establish and pin the orchestrator

You are taking over as the **pinned lead orchestrator** for this project. Before changing code:

1. Read `AGENTS.md`, `docs/STATUS.md`, `docs/recomp-process.md`, `config/target.json`, and `pipeline.toml`.
2. Create `docs/orchestration/STATE.md` with `role: pinned-lead-orchestrator`, your owner/model, the current milestone, authorized scope, owned files/resources, active workers, acceptance gates, and the exact next action below. Keep that record current for the rest of the task. Do not silently transfer ownership.
3. Briefly restate the objective, the current build state, and the next action. Verify the executable and log named below exist. Do not re-interview decisions already recorded here or reinstall the working toolchain.
4. If your host permits orchestrated workers, delegate only bounded, independent, read-only questions and record their actual IDs. Otherwise work serially. Do not allow concurrent edits to the same files.

Do not commit, push, publish, download replacement game files, or change permissions.

## Objective and current milestone

Build a native static recompilation of US PS3 `NPUA80864`, Hot Shots Golf: World Invitational, from the user's own packages. The immediate goal is to fix the first fatal boot blocker and demonstrate forward progress in a fresh bounded boot log. A title menu, gameplay, or official 1.03 compatibility has not been established.

The native build already compiles and opens a D3D12 window. The first unresolved indirect call occurs at `func_007B5B70+0x7E9` (`lr=0x007B5BFC`). The current leading hypothesis is that PS3 import descriptor/PLT slots still point to raw stub bytes. **This is a hypothesis to prove, not a confirmed root cause.**

Exact next action:

1. Reproduce the 20-second boot and inspect `work/runtime/logs/boot-fix-1.02.log`.
2. Trace `func_007B5B70` and the descriptor chain. Determine whether it is an unpatched import slot, a different dynamic-module table, or a lifter/control-flow bug.
3. Only after proving the mechanism, implement the smallest correct fix. Use the real 445 imports and generated HLE handlers; do not hide failures behind generic `CELL_OK` stubs. `sp00nznet/tokyojungle/src/import_resolver.h` is a lead, not code to copy wholesale.
4. Rebuild and rerun the same boot. Compare the first unresolved target and subsequent milestones.

## Build identity and evidence

- Executable: `build/fix-1.02/HotShotsGolfRecomp.exe`
- Size: 446,453,760 bytes
- SHA-256: `70290c23ad442ba8e595999acf359e38729af5b228396313dc9917ab3718ffbd`
- Build completed with exit code 0 after the full-library-path fix in `port/CMakeLists.txt`.
- Boot log: `work/runtime/logs/boot-fix-1.02.log`
- Twenty-second timeout returned 124 as expected. D3D12 initialized on the RTX 4090 and opened a window; no menu was verified.
- Generated entry `func_00010240` exists in `generated/fix-1.02/recompiled/ppu_recomp_table.cpp`.
- There are 735 generated HLE mappings, so missing HLE generation is not the explanation.

Baseline analysis:

- 36,026 OPD descriptors; 32,751 unique loader functions; 33,221 functions lifted after boundary recovery.
- 445 imports across 34 libraries; 387 have names in ps3recomp's database.
- One embedded SPU ELF, 133 detected functions, 6,964/9,344 function bytes covered and 33 `.word` entries left explicit.
- 703 jump-table dispatchers with 6,641 internal case targets.
- Static strings identify Clap Hanz `MG6`/`chlib` and SPURS v2; no PhyreEngine identification was made.

## Inputs, versions, and constraints

Current profile is **third-party fixed 1.02**, not official 1.03. Sony lists 1.03 as latest. Official retail EBOOTs need `UP9000-NPUA80864_00-0000111122223333.rap`, which was not supplied; fixed 1.02 decrypts successfully. Do not call this official 1.03 compatibility.

- `HP9000-NPHA80248` is the separate Asian Everybody's Golf 6 release and is excluded.
- Sony's 1.03 package has matching size/content ID but its published and downloaded SHA-1 differ. Both Sony CDN endpoints served identical bytes. Preserve this as a provenance warning.
- Base/update files are fully extracted under `work/game/`.
- Runtime VFS is `work/runtime/hdd0/game/NPUA80864`, containing official 1.02 plus fix/DLC overlays.
- Original packages are unchanged. Keep all packages, assets, RAP/licenses, generated game code, and shader microcode out of source control.

Toolchain:

- ps3recomp v0.19.0 at `ae92407bb1d899e3d32143e360fe6e6d4d8fa1b5` in `external/ps3recomp`.
- PKG reader at `e609b33377ee29ee20dda92fbec2e7823633d722` in `external/rac8-act-decomp`.
- RPCS3 0.0.43-20623-0ebb6369 in `external/rpcs3`; its archive SHA-256 was verified.
- LLVM-MinGW 20261104 in `external/llvm-mingw`; archive SHA-256 was verified.
- Project Python environment: `.venv`. Use `.venv/Scripts/python.exe`, not system Python for extraction or pipeline stages.

REA `open_binary` rejects PowerPC machine 21, its Rizin/objdump providers are unavailable on Windows, and Windows PTY capture is unavailable. Use ps3recomp's working PPC tools and bounded Bash runs; do not repeat those provider calls.

## Reproduction and pipeline

Use the current generation lock, `config/generated.lock`. Standard stages:

```bash
.venv/Scripts/python.exe tools/recomp_pipeline.py analyze spu lift build
```

The build stage should skip unchanged work. Do not remove the target-specific `--driver-mode=cl` or the full library paths after objects in `port/CMakeLists.txt`; they are required for this clang-cl/MinGW combination. `PORT_SPU_INPUTS` is intentionally empty to avoid the strict registrar rejecting the partial SPU image.

Reproduce the boot with:

```bash
PATH="$PWD/external/llvm-mingw/bin:$PATH" \
PS3_VFS_ROOT="$PWD/work/game/base-1.00" \
PS3_HDD0_ROOT="$PWD/work/runtime/hdd0" \
PS3_HDD1_ROOT="$PWD/work/runtime/hdd1" \
PS3_SAVEDATA_ROOT="$PWD/work/runtime/gamedata" \
PS3_TITLE="Hot Shots Golf: World Invitational" \
PS3_VERBOSE=0 SPU_DUMP_MISS="$PWD/analysis/spu-miss" \
timeout --signal=TERM 20s build/fix-1.02/HotShotsGolfRecomp.exe \
  "$PWD/work/extracted/fix-1.02/USRDIR/EBOOT.elf" \
  > work/runtime/logs/boot-fix-1.02.log 2>&1
```

## Dead ends to avoid

- Do not parse encrypted PKG item tables as plaintext. Use the working PKG reader.
- Do not use system Python for full extraction; it lacks accelerated crypto and is much slower.
- Do not retry official EBOOT decryption without the required RAP or silently substitute fixed 1.02 for official 1.03.
- Do not remove the current CMake library ordering or reintroduce unquoted absolute include/link flags.
- Do not treat `bctr to NULL` and instruction-word call targets as proof that broad no-op vcalls are safe. Keep failures visible.
- Do not report function counts as playability or host UI as guest rendering.

## Expected return

Return actual changes made, commands/tests run with results, new evidence, remaining blockers, and the exact next action. If execution is unavailable, return a proposed minimal patch with application/testing instructions and mark execution `NOT_RUN`. Preserve all original files and this project's current build. The next meaningful checkpoint is a new boot log demonstrating progress beyond `func_007B5B70+0x7E9`, not a narrative explanation alone.
