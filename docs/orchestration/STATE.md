# Orchestration state

Updated 2026-11-17.

- role: pinned-lead-orchestrator
- owner: Claude (model `claude-fable-5-2`), Claude desktop Code tab session, taken over from the 2026-11-17 orchestrator handoff
- active workers: none now. Three subagent workers ran on 2026-11-17 and are finished: `aa95d6ef8ed237dce` (Opus, SPURS job lift), `a6bda65c18d1ed768` (Sonnet, cellSpurs handler), `adb1a583227ccef48` (Sonnet, CLI flags and title ID). Each owned a disjoint file set. The orchestrator ran every build and boot.
- ownership transfers: none since takeover.

## Milestone

Fix the first fatal boot blocker of the fixed 1.02 profile and show forward progress in a fresh bounded boot log. Status: met on 2026-11-17. Mechanism proven, fix applied to the runtime, rebuild and rerun recorded below. Next milestone: first SPURS job runs and the game advances past its first job wait.

## Authorized scope

- Read anything in `F:\Hotshots Golf`.
- Edit `external/ps3recomp/runtime/**` only as small patches, each exported to `patches/runtime/`.
- Edit `port/**`, `tools/**`, `docs/**`, `config/**`, `pipeline.toml`.
- Write new logs under `work/runtime/logs/` and new builds under `build/`.
- Publishing to a public GitHub repository was authorized by the project owner on 2026-11-17. Not authorized: download replacement game files, change permissions, install a toolchain, edit generated game code by hand, overwrite original packages.

## Owned files and resources

- `docs/orchestration/STATE.md` (this file)
- `patches/runtime/0001-hle-fast-path-toc-spill.patch`
- `external/ps3recomp/runtime/ppu/ppu_hle.cpp` (working-tree edit, uncommitted, pinned commit `ae92407` unchanged)
- `build/fix-1.02/` (current build) and `build/baseline-70290c23/` (copy of the handoff executable)
- `work/runtime/logs/boot-fix-1.02-*.log`, `work/runtime/logs/build-fix-1.02-tocspill.log`

## Build identity

| Build | Path | SHA-256 |
| --- | --- | --- |
| Handoff baseline | `build/baseline-70290c23/HotShotsGolfRecomp.exe` | `70290c23ad442ba8e595999acf359e38729af5b228396313dc9917ab3718ffbd` |
| TOC-spill fix | `build/fix-1.02/HotShotsGolfRecomp.exe` | see "Rebuild result" |

The baseline log `work/runtime/logs/boot-fix-1.02.log` is unchanged.

## Finding: first boot blocker

The handoff hypothesis (import descriptor or PLT slots pointing at raw stub bytes) is disproved for this site. Observed chain:

1. `func_007B5B70+0x7E9` is a C++ virtual call (`obj->vtbl[1]`) over a container of garbage pointers. It is not an import call, and the lift matches the disassembly.
2. The garbage comes from earlier NULL allocations. The first one is in a static constructor: `func_0088B444` calls the game allocator `0x780098`, which falls back to libc `malloc` (`0xA3E5E8` to `mspace_malloc` `0xA3BE4C`) and gets NULL.
3. `PS3_NULL_READ_STACK=1` shows r2 = 0 inside `mspace_malloc` at `lr=0x00A3BEAC`, right after its lock helper `0xA3A4DC` returns. The helper calls the `sys_lwmutex_lock` import and then runs `ld r2,0x28(r1)`.
4. `ps3_hle_call` has a fast path for `sys_lwmutex_lock` and `sys_lwmutex_unlock` that returned before the caller's r2 was written to `0x28(r1)`. The slot held 0, so r2 became 0, the heap state pointer read as NULL, and `mspace_malloc` took its failure branch without ever calling `sys_memory_allocate` (syscall 348 never appears in `PS3_SCTRACE_TID=1`).
5. Control experiment on the unmodified baseline executable: `PS3_LWMUTEX_TRACE=1` forces the full handler, which does write the slot. Result in `boot-fix-1.02-slowlock.log`: 0 NULL reads, writes or calls, 0 `bctr to NULL`, 4 `sys_memory` allocations, thread pool created with entry `0x00D61AD8`, `shader_PS3.xb` read, GCM commands emitted.

Fix: one store in the fast path of `ps3_hle_call` (`vm_write64(r1 + 0x28, r2)`), under the same `FLOW_NOSPILL` switch as the full path. No handler returns a fake `CELL_OK`.

## Evidence logs

| Log | Run | Purpose |
| --- | --- | --- |
| `boot-fix-1.02.log` | handoff baseline | reference |
| `boot-fix-1.02-repro1.log(.err)` | baseline exe, 20 s | reproduction: same first unresolved targets `0xFBA10078`, `0x80C30024` at `lr=0x007B5BFC` |
| `boot-fix-1.02-sctrace.log` | baseline exe, 6 s, `PS3_SCTRACE_TID=1` | syscall order on tid 1 |
| `boot-fix-1.02-nullstack.log` | baseline exe, 4 s, `PS3_NULL_READ_STACK=1` | r2 = 0 in `mspace_malloc` |
| `boot-fix-1.02-slowlock.log(.out)` | baseline exe, 20 s, `PS3_LWMUTEX_TRACE=1` | control experiment |
| `boot-fix-1.02-tocspill.log(.out)` | patched exe, 20 s, handoff environment | acceptance run |

## Rebuild result

- Build: `tools/recomp_pipeline.py build`, exit 0, one translation unit recompiled (`ppu_hle.cpp`) and relinked. Log: `work/runtime/logs/build-fix-1.02-tocspill.log`.
- New executable: `build/fix-1.02/HotShotsGolfRecomp.exe`, SHA-256 `f768037d2da3301312805d3ce244ce6c42f5b4914b2d46e6b5da54289b726c47`.
- Two build attempts failed first. The pipeline could not launch tools by relative path (WinError 2), fixed in `tools/recomp_pipeline.py` by resolving the executable against the project root. Then the link was denied because a leftover game process from the first reproduction run (PID 177124) still held the executable; it was ended by PID.
- Acceptance run, 20 s, handoff environment, no debug switches (`boot-fix-1.02-tocspill.log`):

| Marker | Baseline | Patched |
| --- | --- | --- |
| `[null-call]` | 26 | 0 |
| `bctr to NULL` | 399 | 0 |
| unresolved indirect call | 2 (`lr=0x007B5BFC`) | 0 |
| `[sys_memory] allocate` | 0 | 4 |
| thread pool entries | `0x00000000` | `ThreadPool00`-`03`, entry `0x00D61AD8` |
| `shader_PS3.xb` opened | no | yes |

The boot gate is met. The run ends in RSX label writes and FIFO resyncs with the blockers listed below still present. No guest frame, menu or gameplay was verified.

## Known next blockers (from the control run, not yet worked)

1. `[hle] unresolved NID 0x5202E53B` in `cellSpurs` (stub `0x00BF5390`), unnamed in ps3recomp's database. SHA-1 NID hashing identifies it as `cellSpursJobChainSetExceptionEventHandler`.
2. SPURS job dispatch miss: fingerprint `0x3A3C233081147367`, 3,648 bytes, `eaBinary=0x00CB3580`. No lifted image, so the job is dropped. Dump saved at `analysis/spu-miss/spujob_3A3C233081147367_3648.bin`. `PORT_SPU_INPUTS` is empty by design, so this was expected to surface.
3. `[cellGcmSys] FIFO walker circling` resyncs (8 in 20 s) and many `[RSX] unknown method` lines. Guest rendering is not established.
4. `cellGame` reports `titleId='BLES00000'` instead of `NPUA80864`, and opens `/dev_hdd0/game/BLES00000/...`. `libs/system/cellGame.c` keeps that placeholder until a `PARAM.SFO` sets it; `work/game/base-1.00/PARAM.SFO` exists, so the lookup path is the thing to check.

## Acceptance gates

- Boot gate (this milestone): a 20 s boot of the patched build with the handoff environment and no debug switches shows no `[null-call]`, no `bctr to NULL`, no unresolved indirect call at `lr=0x007B5BFC`, and reaches at least the milestones of the control run.
- Labels follow `docs/recomp-process.md` section 6. Current label: Lifted, boot in progress. Renders, Menu and Playable are not claimed.
- Release gates added by the project owner on 2026-11-17 (apply before any public build):
  1. One executable. No separate builder executable; the launcher detects an existing build and starts the game, or offers a play button in the same binary.
  2. Portable by default. All files stay in the executable's folder. Deleting the folder removes the game.
  3. A plain tarball ships next to any AppImage.
  4. A CLI flag for everything: fullscreen, ROM or ELF path, build folder, VFS, HDD and save roots.
- Release gate status today: the executable has no DLL dependencies beyond Windows system libraries. It takes one positional ELF path and reads `PS3_VFS_ROOT`, `PS3_HDD0_ROOT`, `PS3_HDD1_ROOT`, `PS3_SAVEDATA_ROOT` and `PS3_TITLE` from the environment. No CLI flags exist yet, and portable defaults are not verified.

## Exact next action

1. Lift and register the 3,648-byte SPURS job at `0x00CB3580` (dump in `analysis/spu-miss/`), since the dropped job is the first thing the game waits on.
2. Implement `cellSpursJobChainSetExceptionEventHandler` (NID `0x5202E53B`) as a real handler that records the handler, not a blanket `CELL_OK`.
3. Fix the `PARAM.SFO` lookup so `cellGame` reports `NPUA80864`.
4. Rerun the same 20 s boot and compare against `boot-fix-1.02-tocspill.log`.

## 2026-11-17 integration run (after the worker tasks)

Build `build/fix-1.02/HotShotsGolfRecomp.exe`, SHA-256 `b398216b23766dec1cdb1515b00a1665f425ec919d21a941b05f0bfde2c092f5`. The TOC-spill build is kept at `build/tocspill-f768037d/`. Build log: `work/runtime/logs/build-fix-1.02-integrate2.log`. Boot log: `work/runtime/logs/boot-fix-1.02-integrate2.log` (20 s, handoff environment, run on a hidden desktop so no window appears on the monitor).

Changes in this build:

- SPURS job `0x00CB3580` (3,648 bytes, fingerprint `0x3A3C233081147367`) lifted by `tools/spu_lift_jobs.py` from `tools/spu_jobs.json` and registered in `port/spu/spu_jobs_register.c`.
- `cellSpursJobChainSetExceptionEventHandler` (NID `0x5202E53B`) implemented in ps3recomp `libs/spurs/cellSpurs.c`. It stores the handler and argument per job chain. Nothing invokes the handler yet. Patch `0002`.
- `port/main.cpp` calls `cellGame_init_from_paramsfo` and stops with an error if the SFO has no title ID. Patch `0003`. The first integration build (`...-integrate1.log`) stopped at startup because that function had no `return`; fixed by the orchestrator.
- CLI flags and portable defaults in `port/cli_options.*`, documented in `docs/CLI.md`. `--fullscreen`, `--savedata` and `--verbose` are parsed but not wired; `--hidden` is untested.
- `ppu_hle_nids.cpp` regenerated with `gen_hle_nids.py --all`: 1,239 handlers from 93 modules.

| Marker | TOC-spill build | This build |
| --- | --- | --- |
| SPURS dispatch miss | 1 | 0 |
| `[spurs-job] ENTER` and `job 0 done` | 0 | 1 each |
| unresolved NID `0x5202E53B` | 1 | 0 |
| `BLES00000` in log | yes | 0 lines (`NPUA80864` 16 lines) |
| `[null-call]`, `bctr to NULL` | 0 | 0 |
| FIFO walker resyncs | 8 | 1 |
| window title draw count | not captured | `draws: 0`, window is one solid color |

Label is unchanged: Lifted, boot in progress. No guest frame was drawn.

### Next blockers from this run

1. Seven new unresolved NIDs, unnamed in `analysis/fix-1.02/imports_named.json`: `0x1395D8D1`, `0x224E1610`, `0x71714CDC`, `0xD7471088`, `0xCAC9FC34`, `0x45F8F3AA`, `0xF9732AC8`. Library and names are not identified yet.
2. `[HOTREAD] spinning on 0x1103C1EC (=0)` at `cia=0x00D61AD8 lr=0x0077A26C`, 850 lines: the thread pool workers wait on a word that never becomes nonzero.
3. Shader files such as `../Library/chlib/render/shader/PS3/cloud_f.fpo` and `default.csv` fail to open. Whether the game expects them on disk or inside an archive is unknown.
4. Rendering: 11 `[RSX] unknown method` lines, 0 draws.
5. Release gates: `--fullscreen`, `--savedata`, `--verbose` need the runtime change proposed by the CLI worker (window mode in `libs/video/rsx_d3d12_backend.c`, a `PS3_SAVEDATA_ROOT` mapping in `ppu_fs.cpp`). The portable default layout has not been run.

### Exact next action

Identify the library of the seven NIDs from the import stubs in the log lines just before each `unresolved NID`, name them with `compute_nid` candidates, and trace the writer of `0x1103C1EC` to learn what the thread pool is waiting for.
