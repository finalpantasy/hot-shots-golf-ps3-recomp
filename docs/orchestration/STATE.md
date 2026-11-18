# Orchestration state

Updated 2026-11-17.

- role: pinned-lead-orchestrator
- owner: Claude (model `claude-fable-5-2`), Claude desktop Code tab session, taken over from the 2026-11-17 orchestrator handoff
- active workers (2026-11-17, end of day): none. Finished: `aa95d6ef8ed237dce` (Opus, SPURS job lifts, 13 jobs), `a26eab669c91f3810` (Opus, GCM FIFO fix, patch `0008`), `a6bda65c18d1ed768` (Sonnet, cellSpurs handler), `adb1a583227ccef48` (Sonnet, CLI flags and title ID). Codex works from `CODEX-GOAL.md`.
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

## 2026-11-17 run 3: SPURS instance ports and job guard table

Build SHA-256 `b99080d22afd02043799606c9690a4eae9ef23f262f407db1c290bdd42ed50e0`. Build log `build-fix-1.02-guards2.log`, boot log `boot-fix-1.02-guards2.log` (20 s, hidden desktop). Both fixes are in ps3recomp `libs/spurs/cellSpurs.c`, exported with the job chain handler as patch `0002-cellspurs-jobchain-handler-instance-ports-guard-table.patch`.

1. Port bindings were one global table. The game's `MG6_` SPURS instance binds static port 1, then its `sgx-spurs-` instance asks for port 1 too and got `0x8041070A` (busy). The game logged `failed to create SPURS printf server event` and shut that instance down, so its renderer never started. Bindings are now per instance. Limit: the SPU-side lookup `spurs_port_queue(port)` still takes the first instance that bound the port.
2. The job guard table held 32 guards. The game initializes 1,039 in this run and guard 33 failed with `0x80410901`. The table is now append-only with a hash index and room for 32,768.

| Marker | Run 2 | Run 3 |
| --- | --- | --- |
| `failed to create SPURS printf server event` | 1 | 0 |
| `terminate SPURS` | 1 | 0 |
| `JobGuardInitialize` succeeded | 32 | 1,039 |
| `failed to initialize job v2 guard` | not reached | 0 |
| window title draw count | 0 | 2,048 |
| captured window | one solid color | one solid color |
| `[null-call]` | 0 | 5 (`lr=0x007B56CC`) |
| `bctr to NULL` | 0 | 400 |

The draw count is the host backend's counter. The captured window is still a single color, so no guest frame is claimed. Label unchanged: Lifted, boot in progress.

### Next blockers from run 3

1. Two SPURS jobs on the `sgx-spurs-` instance are not lifted and miss on every dispatch: fingerprint `0xFDFFAAC1BCD5352E` (34,704 bytes, job `0x1192CC00`) and `0xCB9BD0241BB0DE67` (53,280 bytes, job `0x1192CB80`). Add them to `tools/spu_jobs.json` if they pass the lifter's strict checks.
2. `[null-call]` near `lr=0x007B56CC` on tid 1 with `r12=0x48000042`, 5 times, and 400 `bctr to NULL` lines. Cause not traced.
3. Unresolved imports, all outside the boot path so far: `cellHttp` (5), `sceNp` (2), `cellFont` (2), `cellFontFT` (1), `libgem` (1), `cellCamera` `0x0E63C444` (23 calls), `sys_crashdump` (1). Names are not identified.
4. The earlier thread pool `HOTREAD` lines are gone in this run.

### Exact next action

Lift the two `sgx-spurs-` jobs, then trace the NULL call at `lr=0x007B56CC`.

## Ownership split with Codex (proposed 2026-11-17, active once the owner starts Codex)

Codex works from `docs/orchestration/CODEX-GOAL.md` on the host, release and peripheral-module side and reports in `docs/orchestration/CODEX-LOG.md`. Claude keeps the boot path: SPU jobs, `libs/spurs`, `runtime/**`, `tools/**`, `pipeline.toml`, `port/CMakeLists.txt`, builds of record and commits. Builds and game runs are serialized with `work/runtime/BUILD.lock`.

## 2026-11-17 run 4: six jobs lifted, base-file fallback, GPU device loss (open)

Build SHA-256 starts `649c4bac`. Build log `build-fix-1.02-jobs6.log`; boot logs `boot-fix-1.02-jobs6.log` and `-jobs6b.log` (20 s each, hidden desktop). This build also contains Codex's in-progress window-mode change in `libs/video/rsx_d3d12_backend.c`, so it is not a clean single-variable build.

Changes on the Claude side:

- Five more SPURS jobs lifted and registered by worker `aa95d6ef8ed237dce` (six in total): `CB9BD0241BB0DE67` (EA `0xD09F00`, 53,280 bytes), `FDFFAAC1BCD5352E` (`0xCDD880`, 34,704), `ABD49FC58F53F368` (`0xCF7100`, 9,488), `F523F26F69764538` (`0xCB4400`, 64,912), `1B6BDAC375C5438D` (`0xCC4200`, 13,840). They use a second job layout with no JOBCRT header; two contain inline switch tables, which `tools/spu_lift_jobs.py` now handles. None of the five has been seen running.
- `runtime/ppu/ppu_fs.cpp`: for HDD (PSN) titles, a file missing under `PS3_HDD0_ROOT/game/<title>/` resolves to the base install under the VFS root. Patch `0004`. Reason: in run 3 the base files (`xbdata/courseinfo`, input and shot tables, 90 failed opens) were not found, and the NULL calls at `lr=0x007B56CC` followed those failed loads. In run 4 there are 0 failed opens, 0 `[null-call]` and 0 `bctr to NULL`, but the run also stops earlier, so this is not yet proof of the fix.

Regression, cause not isolated: the D3D12 device is removed at the first pipeline state creation (`[VP] colour PSO FAIL (0x887A0005)`, log line 1881), the game never prints `=== SGX system initialize`, and no job dispatch after the first is reached. Reproduced in both runs. Candidates: the window-mode change, the base fallback changing which shader data the game loads, or GPU state on the machine at the time. The build before it (`b99080d2`) was not kept, so the comparison has to use `build/tocspill-f768037d/` or a rebuild with one change reverted.

### Exact next action

1. When `work/runtime/BUILD.lock` is free, run `build/tocspill-f768037d/HotShotsGolfRecomp.exe` for 15 s on the hidden desktop. If it also logs `887A0005`, the cause is the machine's GPU state, not the code.
2. Otherwise rebuild with the window-mode change reverted, then with the base fallback reverted, one at a time, keeping each executable in its own folder.
3. From now on copy every build of record to `build/<name>-<sha8>/` before the next build.

## 2026-11-17 run 5: device loss isolated to the base-file fallback path

One build (`build/ab-e260235f/`, SHA-256 starts `e260235f`), two 20 s hidden-desktop boots that differ only in `PS3_NO_HDD_BASE_FALLBACK` (new switch in `ppu_fs.cpp`, patch `0004`). Logs: `boot-fix-1.02-ab-fallback-on.log`, `-off.log`.

| Marker | Fallback on (default) | Fallback off |
| --- | --- | --- |
| failed file opens | 0 | 36 |
| `887A0005` device removed | 10 | 0 |
| `=== SGX system initialize` | not reached | reached |
| lifted job `F523F26F69764538` entered | not reached | 3 times |
| SPURS dispatch misses | not reached | 32, four new fingerprints |

Reading: the window-mode change is not the cause. With the base files visible the game takes a different early path, the RSX FIFO is parsed as garbage (`bind_texture` and `draw_arrays` with nonsense arguments, FIFO walker "circling" at `get=0x00400500 put=0x00600654`), and the D3D12 device is removed at the first pipeline state creation. With the fallback off the game runs on missing data, which is the wrong state, but it gets further into SPURS. The fallback stays on by default because the files exist on a real console; the switch is for finding SPU jobs until the FIFO bug is fixed.

### Next blockers

1. GCM FIFO parse with base files present: find which `cellGcm` call sets up the command buffer the walker misreads (start from the first `SetDefaultCommandBuffer` and the first "FIFO walker circling" line in the fallback-on log).
2. Four more SPURS jobs miss with the fallback off: `49C1D6C47E80AF43` (24,720 bytes), `5DA195169669A5FF` (72,464), `80435D36E623FAA0` (19,488), `82D0BE145EC28AEE` (17,424). Dumps are in `analysis/spu-miss/`.
3. Of the five jobs lifted in run 4, only `F523F26F69764538` has been seen entering. No job return code was logged for it.

### Exact next action

Trace blocker 1. In parallel, a worker lifts the four jobs in blocker 2.

## 2026-11-17 run 6: first guest frame, 13 jobs lifted

Worker `a26eab669c91f3810` (finished) found two causes for the device loss, both in `external/ps3recomp/libs/video/` and exported as `patches/runtime/0008-gcm-fifo-default-ctx-repoint.patch`:

- `cellGcmSetDefaultCommandBuffer` did not point `gCellGcmCurrentContext` back at the default context, so the FIFO walker read a stale buffer. `GCM_DEFAULT_CTX_REPOINT=0` restores the old behavior for comparison.
- `scanout_auto_present` copied the 1600x1080 display buffer into the 1280x720 back buffer without scaling. `guest_fb_present` still has the same unclamped copy and is not fixed.

Worker `aa95d6ef8ed237dce` (finished) lifted 7 more SPURS jobs, 13 in total (`tools/spu_jobs.json`). Not lifted: `0xCB1F80` (never dispatched) and `0xCAD980` (data inside code at `0x2C18`).

Evidence:

- Build `build/gcm-4198df92/`, log `boot-fix-1.02-gcm-3.log`: `887A0005` 0 (was 10), FIFO walker circling 0 (was 8), `=== SGX system initialize` reached and completed, window title `draws: 5`. The capture the first capture (since replaced) is the game's autosave notice over a course background. It is the first guest frame. Only the blue channel is shown.
- Build `build/frame1-3d6db76d/` (13 jobs plus both fixes), log `boot-fix-1.02-frame1.log`: `887A0005` 0, FIFO walker 0, SGX initialize completed, `dispatch MISS` 0, 4 job entries. The capture is black. Thread 11 called a null pointer 5 times from `func_00936F24+0x19FE` and then 393 times from `func_007625E8+0x2C9`, each through `r12=0x48000084` (a code word used as a function descriptor), followed by garbage virtual calls.

The black result is intermittent. Same markers per log: `gcm-2` 400 `bctr to NULL` (bad), `gcm-3` 0 (good), `codex-4` 0, `frame1` 400 (bad). Two of four runs fail, so the cause is a race and not the 7 new jobs alone. In the bad runs `r5` and `r28` hold `0x1218EA80`, the `soc-job` job chain.

Seen in every run since SGX initialize was reached: `*** sgxbus.c(934) : failed to regist module`, printed right after the `soc-job` chain is created and run. Also `[hle] unresolved NID 0xA03EF587` (`libgem`, Codex's list) and `open FAIL` for `default.csv` (2).

### Next blockers

1. Thread 11 race: find what `func_00936F24` reads at `r9=0x1219BAC0` and who should have written it. Start with the `soc-job` chain and the `failed to regist module` message, since both involve `0x1218EA80`.
2. Blue-only frame: red and green are zero in the presented image. Check the surface format and channel order in the scanout copy and the swap chain format in `rsx_d3d12_backend.c`.
3. Seven newest jobs have not been seen running. Only two images entered in `frame1` (`494131663`, `311961058`).
4. `spurs_port_queue` still returns the first instance's binding.

### Exact next action

Run `build/frame1-3d6db76d/` five times for 20 s each and record good or bad per run, to get the failure rate. Then trace `func_00936F24` around `+0x19FE` in `generated/fix-1.02/recompiled` to find the object whose function table is unset.

## 2026-11-17 run 7: black boots traced to the invented job event

Failure rate on `build/frame1-3d6db76d/`: 4 of 5 runs (`boot-fix-1.02-rate-1..5.log`) had `bctr to NULL`; the frame is black or partial in those.

Cause: `jc_signal_done` in `libs/spurs/cellSpurs.c` invents the job-completion event. It sends `data2 = lap counter` to every attached queue. The game's loop in `func_00936F24` (`sgx-audio-thr`) uses `data2` as an index into a table of 128-byte entries at `jc+0x200` and calls the entry's callback. The `soc-job` chain is a service loop, so the counter passes the end of the table (129 entries) and the loop calls through whatever memory lies beyond it (`r12=0x48000084`).

What the job really posts (run with `SPU_MBOXTRACE=1`, log `boot-fix-1.02-mbox-1.log`): outbound mailbox = the answer (for example `0x400`, `0xB4D0`, `0x8A10`, `0x2000`), interrupt mailbox = `0x50000000 | index`. `0x50` is `throw_event` on SPU port 16, and port 16 is the dynamic port of queue 3 (`AttachLv2EventQueue(queue=3) port=16`). Index was 0 for the 25 setup queries and 1 for the audio loop.

Change (in tree, patch not exported yet): when a job posted an interrupt mailbox word, send `data2 = word & 0xFFFFFF`, `data3 = outbound mailbox`, only to the queue bound to that port. `SPURS_FAKE_JOB_EVENT=1` restores the old behavior. The dropped answers may also explain `sgxbus.c(934) : failed to regist module`; not confirmed.

Active worker: `a815d8ff935f4a9cb` (Opus, blue-only frame, owns `libs/video/**` except window code, builds under `BUILD.lock` as `blue-worker`, will export patch `0009`).

## 2026-11-17 run 8: black boots fixed, game reaches the title menu load

Run 7's first two attempts did not work: the SPU user-event hook consumes the interrupt mailbox word before `jc_signal_done` can see it, and it already delivers the real event to the right queue. The invented event was simply extra. Final change in `libs/spurs/cellSpurs.c` (patch `0002`, re-exported): `spurs_port_queue` sets a thread-local flag when a job's own event is delivered; `jc_signal_done` then marks the chain and sends no invented events for it. `SPURS_FAKE_JOB_EVENT=1` restores the old behavior.

Also added `cellFsReadWithOffset` (`sys_fs` NID `0x0D5B4A14`) in `runtime/ppu/ppu_fs.cpp`, patch `0010-ppufs-read-with-offset.patch`. The game reads its `.xb` archives with it.

Evidence, build `build/evt3-7c4f6c46/`, logs `boot-fix-1.02-evt3-1..4.log`: 4 of 4 runs have 0 `bctr to NULL`, 0 `null-call`, 0 `887A0005`, and `sgxbus.c(934) : failed to regist module` is gone. The game leaves the autosave notice, shows "Auto-loading...", then opens `title.US_01.xb`, `coursebg_menu.xb` and the avatar archives.

### Next blockers

1. Job `0xCAD980` (fingerprint `79D3C33093353269`, 17904 bytes) is dispatched 24 times in 20 s and is not lifted. Worker `ae1d90fb014b205b9` (Opus) owns `tools/spu_*` and `port/spu/**` for this.
2. Blue-only frame: worker `a815d8ff935f4a9cb` (Opus), patch `0020` (`0009` is the peripheral handlers patch).
3. `cellSail` imports unresolved: `0x018281A8` `cellSailGraphicsAdapterGetFrame2`, `0x44A20E79` `cellSailGraphicsAdapterUpdateAvSync`, `0x5F7C7A6F` `cellSailPlayerSetParameter`, `0x1C9D5E5A` (not named). Passed to Codex by mailbox.
4. The new chain `0x12E74800` still gets invented events on queue 1 (`d2` counts 0 to `0x1D`); correct only if its jobs never post their own.

### Exact next action

When both workers report: rebuild, run 5 boots of 30 s, view the captures, then update docs and push.

## 2026-11-17 run 9: colors fixed, 14 jobs, intro movie reached

- Blue-only frame fixed by worker `a815d8ff935f4a9cb` (finished). Cause: `libs/video/rsx_vertex_fetch.c` treated an enabled vertex array with stride 0 as disabled and used the constant (0,0,0,1). RPCS3 reads element 0 for every vertex. The game's 2D pass sends color and color scale that way, so red and green were multiplied by 0. Patch `0020-rsx-vertex-stride0-single-element.patch`; `RSX_STRIDE0_CONST=1` restores the old behavior. Build `build/blue-414d453c/`, capture `docs/images/autosave-notice-2026-11-17.png`. Not checked: the game samples its 1600x1080 offscreen target with remap `0xAA6C` and the D3D12 backend ignores remap on that path (`rsx_d3d12_backend.c:5013`).
- Job `0xCAD980` lifted by worker `ae1d90fb014b205b9` (finished): 14 jobs, `dispatch MISS` 0 in `boot-fix-1.02-jobs14-1..3.log`. The "data inside code" was a 5-entry switch table the tool already handles.
- The game now shows the JAPAN Studio logo and starts its intro movie through `cellSail` (`PlayerBoot`), where it stalls on unresolved imports. Worker `ab6124b51bf7bd01e` (Opus, `sail-worker`) owns `libs/codec/cellSail.*`, patch `0021`.
- `sgxbus.c(934) : failed to regist module` came back in 1 of 3 runs. Cause found: `cellSpursShutdownJobChain` cleared `running` without stopping the walker thread, so the next `RunJobChain` started a second walker on the same chain. Fix in tree (stop flag checked in the guard wait and the command loop; `Join` waits for the thread). Verification runs: `boot-fix-1.02-stop-1..5.log`.
- Boot speed varies from 2 to 63 FPS between runs while workers load the machine. Not investigated.
