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

Chain shutdown fix verified: build `build/stop-c1a9d00d/`, `boot-fix-1.02-stop-1..5.log`, 5 of 5 runs with 0 `failed to regist module`, 0 `bctr to NULL`, 0 `null-call`, 0 `887A0005`. Patch `0002` re-exported.

## 2026-11-17 run 10: title screen, New Game accepted

- Sail worker `ab6124b51bf7bd01e` finished: `libs/codec/cellSail.*`, patch `0021`. Movie is skipped with a logged line.
- `runtime/syscalls/sys_event.c`: unnamed port source is `(pid << 32) | port id`, patch `0022`. Without it `func_00877D40` drops every cellSail event.
- `libs/spurs/cellSpurs.c`, patch `0002` re-exported: (a) a NEXT or RESET_PC that targets its own slot is polled, not counted idle. Chain "chlib/spu/Spu.cpp" parks that way and was killed after 4096 reads ("malformed?"), title at 0.25 FPS. (b) `jc_signal_done` pushes only to queues owned by the chain's SPURS instance (`s_jobchains[].spurs_ea`). With (a) alone, 2 of 2 boots crashed in `func_00936F24` (400 `bctr to NULL`) because chlib job counters reached sgx queue 3. (c) The idle bound now prints the last 32 commands walked.
- Evidence: build `build/own-d5b1fd2d/`, logs `boot-fix-1.02-own-1..2.log`, 90 s, `PAD_SCRIPT=62:0x4000,70:0x4000,78:0x4000,84:0x4000`. Both runs: 0 `bctr to NULL`, 0 `null-call`, 0 `failed to regist`, 0 `malformed`. Run 1: title at 7.93 FPS, Cross accepted, `SAVE complete for 'NPUA80864'`, `AutoLoad2 BCUS98115`, new chlib chain created. Run 2 (slower boot): "Now Loading" after the first press.
- Earlier build `build/title-11307e93/` (sys_event fix only): title in 2 of 3 runs at 60 s; the third was still at "Auto-loading...".

### Next blockers

1. Unresolved `cellOskExtUtility` NIDs `0x7C95FEB8`, `0x09565B21`, called after New Game. `cellOskDialog] Abort()` follows. Passed to Codex by mailbox.
2. What the game shows after New Game is not captured yet. Needs timed multi-capture in `ghost_shot.py`.
3. Title FPS 8 to 20, and black or gray squares in the title sky.
4. `gen_hle_nids.py --all` is not rerun by the pipeline when only HLE sources change.

### Exact next action

Add timed captures to the scratch `ghost_shot.py`, run 150 s with Cross presses, view the frames after New Game.

## 2026-11-17 run 11: course demo reached, job queue missing

- 145 s boot with no effective input (`boot-fix-1.02-ng-1.log`, capture `docs/images/demo-hole-2026-11-17.png`): after the title the attract demo loads a course and draws the hole HUD (hole 5, par 4, 394 y, "Back to Title", "DEMO"). The 3D view is dark green ground with one object; camera or lighting is wrong or the scene is incomplete.
- Unresolved in that load: seven `cellSpursJq` NIDs (`_cellSpursCreateJobQueue` and attribute setters). Worker `a9895e8f5ee5e7f9c` (Opus, reason: SPURS job-queue semantics plus guest ABI reading) owns `libs/spurs/cellSpursJq.*`, patch `0023`.
- `jg_wait` gave up on a guard closed for 20 s ("chain gives up" in the log). Changed to wait until shutdown. In tree, not yet verified by a boot; the worker's builds include it.
- Coordinator does not edit `libs/spurs/**` while the worker runs.

## 2026-11-17 run 12: job queue in, course geometry draws

- Worker `a9895e8f5ee5e7f9c` finished: `libs/spurs/cellSpursJq.*` rewritten, patch `0023`. NID table regenerated with `--all` (11 new registrations). Verified call shapes are in the worker's notes in `cellSpursJq.c`. Not verified: Port2Sync wait (never called in 150 s), meaning of Create's r8 and stack arguments, PushJobBody r6/r7.
- Evidence `boot-fix-1.02-jq-1.log`: `seq=4096 (queue done=4067 ran=0 MISS=4067)`; 0 `bctr to NULL`, 0 `null-call`, 0 `garbage vcall`; 1 unresolved NID `0x7C95FEB8` (cellOskExtUtility). Capture: hole 7 demo with waterfall, bunkers, trees.
- Job `0x00CAB400` (9536 bytes, `B24195A9C86BC758`) is the only one the queue pushes and is a dispatch MISS. Worker `aa354238187c29d59` (Sonnet) owns `tools/spu_*` and `port/spu/**` to lift it.
- Sky squares at the title: frame capture `work/runtime/rsxcap-title/frame_12` (RSX_CAP) shows three 6-vertex quads, ops 255 to 257, fp `0x014F0381`, texture 1024x512 fmt 0x88 at `0xC87B3200`, blend key `0x522118B` (alpha blend). Cause not found. The game renders to a 1600x1080 target.

### Exact next action

When the lift worker reports: check the course capture again (lighting, sky, triangles may depend on the job), then commit and push.

## 2026-11-17 run 13: workers out

- `boot-fix-1.02-ccap-1.log` (build `build/jq-a8ba648b/`, 165 s, no input): demo hole 8 at 25.59 FPS, 490 draws: green, flag, trees, sky. Bugs: opaque black boxes around foliage, terrain too dark. Captures in `work/runtime/rsxcap-course/frame_01..04`.
- Worker `a5185470777d90621` (Opus, reason: shader and RSX state debugging) owns `libs/video/**`, patch `0024`: foliage boxes, dark terrain, title sky squares.
- Worker `aa354238187c29d59` (Sonnet) still owns `tools/spu_*`, `port/spu/**` for job `0x00CAB400`.
- Coordinator edits none of those; both workers build under `BUILD.lock`.

## 2026-11-17 run 14: job 15 lifted, demo plays a shot

- Worker `aa354238187c29d59`: job `0x00CAB400` (`B24195A9C86BC758`) lifted, 15 jobs in `tools/spu_jobs.json`. `boot-fix-1.02-job15-1.log` (180 s): `[cellSpursJq] done=16352 ran=16352 MISS=0`, 0 `dispatch MISS`, 0 `bctr to NULL`, 0 `null-call`, 0 `garbage vcall`. Captures show the demo golfer on the tee and a ball in flight with "264.0y / Carry 236.3y".
- `tools/spu_lift_jobs.py` must be run before `recomp_pipeline.py build` after editing `spu_jobs.json`; the pipeline does not run it.
- A second queue job appeared in one run: `16CB89234CCC254E`, 5568 bytes, 32 pushes. Same worker resumed to lift it as job 16.

## 2026-11-17 run 15: job 16 lifted, not exercised

- Worker `aa354238187c29d59` finished: `16CB89234CCC254E` added as job 16 (`ea 0x00CB1F80`, EA inferred from the EBOOT file offset, not from a log line). `boot-fix-1.02-job16-1.log` (170 s): 0 `dispatch MISS`, `ran=8160 MISS=0`, error markers 0, but the job was never pushed in that boot, so the lift has not run. All 16 dumps in `analysis/spu-miss` are now in `tools/spu_jobs.json`.
- Rendering worker `a5185470777d90621` still out.

## 2026-11-17 run 16: alpha test, strip join, keyboard calls, generated HLE table

- Rendering worker `a5185470777d90621` finished, patch `0024` (`libs/video/rsx_d3d12_backend.c`, `rsx_fp_decompiler.c`, `rsx_texture_layout.c` and its test). The patch applies on HEAD plus `0005`, `0008`, `0020`.
  - Foliage boxes fixed: the backend never applied the RSX alpha test. It now runs in the shader on color 0 alpha, with texture alpha kill, and fragment constants arrive per draw. Off switches: `NO_ALPHATEST=1`, `NO_ALPHAKILL=1`, `FP_CONSTBUF=0`.
  - Title sky squares fixed: a strip split over several 256-vertex batches in one draw lost two triangles at each join. Batches are joined now. Off switch: `RSX_STRIP_JOIN=0`.
  - Dark terrain is open. Ground program `0x015DC881` multiplies sunlight by a shadow-map sample on unit 12, which the game never binds in the captured frames. Whether that causes the darkness is not verified. The before and after course captures are different holes.
- Coordinator: `cellOskDialogExtInputDeviceLock` and `Unlock` added to `libs/misc/cellOskDialog.c` (patch `0025`). They record the lock state; no host keyboard uses it yet.
- Coordinator: Codex's `port/CMakeLists.txt` change applied. The build generates the HLE NID table (`HLE NID table: generated (every module)`); the copy in the lift directory is used only with `-DUSE_CURATED_HLE_NID_TABLE=ON`. The `pipeline.toml` half is not applied, so the lift stage still writes the unused copy.
- Build `build/cont-675c97e1/`, `boot-fix-1.02-cont-1.log` (160 s, muted, `PS3_DEV_FLASH` set to Codex's staged firmware folder): 0 unresolved NID (was 1 to 2), 0 `bctr to NULL`, 0 `null-call`, 0 `887A0005`. 146 `[audio-peak]` lines, highest peak 0.1964, so the mixer produces sound; nobody has listened to it.
- In that run the title appeared after 140 s, not 60 to 70 s, and the scripted Cross at 90 s missed it. Cause not known (machine load or this build).
- Boot script now sets `PS3_MUTE=1` and `AUDIO_PEAK=1`. Boots before 22:42 were not muted.

### Exact next action

Read `boot-fix-1.02-cont2-1.log` and its captures (Cross at 170 s) to see what follows the title, and find out why the title arrived late.


## 2026-11-17 run 17: late title is not this build

- `boot-fix-1.02-cont2-1.log` (240 s, Cross at 170 s): black frames with 400 to 840 draws from 120 s to 220 s, title at 240 s, so the press missed again. 0 unresolved NID, 0 `bctr to NULL`.
- `boot-fix-1.02-noflash-1.log` (no `PS3_DEV_FLASH`): same late load, so the staged firmware folder is not the cause.
- `boot-fix-1.02-oldexe-1.log` (previous build `build/job16-*`, same muted settings): also still loading at 100 s. The new build is not the cause.
- Left: machine load (CPU at 70 percent, Codex builds and other projects running, the game runs at BelowNormal priority) or `PS3_MUTE=1`. Not separated yet.
- A fixed-time `PAD_SCRIPT` cannot hit the title while load time varies by a factor of three.

### Exact next action

Make scripted input wait for a frame count or draw count, not wall time, then capture what follows the title.

## 2026-11-18 run 18: Continue accepted, next scene is black

- `PAD_CLOCK=flips` with `PAD_SCRIPT=2500:0x4000` presses Cross on the title whatever the load time. `boot-fix-1.02-flips-1.log` and `-flips2-1.log` (300 s and 430 s): "Continue" is accepted, "Now Loading" shows for about 40 s, then the window is black with 470 to 900 draws per frame at 8 to 11 FPS. 0 unresolved NID, 0 `bctr to NULL`, 0 `null-call`.
- Milestone log `work/runtime/logs/milestone-flips.log`: `cellOskDialogExtInputDeviceLock` 1, `Unlock` 1, `cellSpursJobQueuePort2Sync` 1, `Port2Destroy` 1, `ShutdownJobQueue` 1, `JoinJobQueue` 1. These paths now have run once without a fault.
- Demo capture in the same run shows clean foliage and a player portrait.
- Worker `aa6ea4961e5ca21b1` (Opus, reason: RSX state and shader debugging) owns `libs/video/**`, patch `0026`: why the scene after Continue is black. Coordinator edits nothing there.

### Exact next action

On the worker's report: check its captures, commit `0026`, update README status.

## 2026-11-18 run 19: shadow pass no longer presented as a frame

- Worker `aa6ea4961e5ca21b1` finished, patch `0026-rsx-menu-scene.patch` (`libs/video/rsx_d3d12_backend.c`, applies on HEAD + 0005 + 0008 + 0020 + 0024). Depth-only draws (`no_color`, or `cmask==0`) are excluded from the three display checks. Off switch `RSX_DEPTH_DISPLAY=1`. Capture manifest prints `zeta=`, `nocolor=`, `disp=` per draw.
- Evidence: `work/runtime/rsxcap-menu/run1/frame_08` (683 shadow draws, 1-color backbuffer), `run2/frame_00..03`, `after1` (frames 09 to 18 colored). Last run, build sha8 `3915fbac`: `bctr=0 nullcall=0 regist=0 stars=0 unresNID=0 unresCall=0 garbage=0 887A=0 lines=13415`.
- Not verified: a black capture at 240 s with the title's draw count (fade?), two mostly-sky captures, black background on the shot screen, 11 to 14 FPS in play, line primitive (prim 2) skipped.

### Exact next action

Send input after Continue to learn what that scene is (menu or round), and look at play frame rate.

## 2026-11-18 run 20: menus reached

- `boot-fix-1.02-play-1.log` (425 s, build sha8 `3915fbac`, `PAD_SCRIPT=2500,4000,4300,4600,4680,4750` all Cross on flips): title, clubhouse menu ("Single Player", "Challenge"), Challenge course select (Maple Leaf Golf Club, Beginner Rank) at 22 to 25 FPS. `bctr=0 nullcall=0 unresNID=0 887A=0`. Capture committed as `docs/images/course-select-2026-11-18.png`.
- The first press landed during the attract demo in this run, not on the title; the later presses did the menu work. Which press did what is not mapped.

### Exact next action

Add presses after flip 4750 to pick the course and start a round; a run is capped at 10 minutes, so the round start must fit in about 430 s.

## 2026-11-18 run 21: round loads at 1 FPS

- `boot-fix-1.02-round-1.log` (560 s): course select, character select (Yuna, Novice), shot type, confirmation with "Go to Course", then 40 s black at 394 draws, then "Now Loading" at the cap. Capture `docs/images/character-select-2026-11-18.png` (not in the README yet).
- `boot-fix-1.02-round2-1.log` (560 s, Cross every 120 flips from 2500, 17 of 25 fired): round loading from 380 s; from 410 s 1118 to 1243 draws at 1.05 FPS with "Now Loading" on screen. Log shows `soc-job` chain, `course01.sgh/.sgb`, voice `ca00.sgb`, job queue `seq=4096 done=4064 ran=4064 MISS=0`. `bctr=0 nullcall=0 unresNID=0 887A=0`.
- Worker `a488a7d74f9958cfa` (Opus, reason: profiling the D3D12 backend) owns `libs/video/**`, patch `0027`: where frame time goes at high draw counts. Coordinator edits nothing there.

### Exact next action

On the worker's report: verify FPS in the demo and the round, commit `0027`, then retry the round and send swing input.

## 2026-11-18 run 22: patch 0027, stall is in the guest

- Worker `a488a7d74f9958cfa` finished, patch `0027-rsx-frame-time.patch` (applies on 0005/0008/0020/0024/0026): `RSX_PROF=1` profiler; debug layer opt-in (`D3D12_DBG=1` or `D3D12_IQ=1`); shader bytecode cache by HLSL hash in memory and in `build/fix-1.02/shader_cache_d3d12` (`RSX_SHADER_CACHE=0` off, or a folder path); hashed sampler lookup; inlined vertex float read.
- Numbers (demo, same scene): render_frame 24.6 ms to 10 to 12 ms; shader compiles 88 (50.8 s) to 1 (42 ms) with 78 disk and 58 memory hits; about 11 FPS at 860 draws to 15 to 28 FPS at 750 to 960 draws.
- Round: 1100 to 1130 draws, about 0.85 FPS, walker idle 2275 to 2890 ms per 2.3 s window, 95% of process time in ntdll waits. None of the round's draws count as display draws, so nothing is presented. Last marker line: `bctr=0 nullcall=0 regist=0 stars=0 unresNID=0 unresCall=0 garbage=0 887A=0 lines=7695`.
- Not verified: title and menus not compared in captures after 0027; sampler table hits its 2048 limit in the round; flat cyan water in `final2-1.png`; `port/main.cpp` idles with `Sleep(4)` (Codex's file).
- The shader cache folder sits beside the executable. Release gate 2 (portable) is satisfied by that location; Codex should confirm it against its write trace.
- Worker `a85b98713035368ac` (Opus, reason: guest thread and SPURS wait diagnosis) owns `runtime/**`, `libs/spurs/**`, `libs/sync/**`, `libs/video/**`, patches `0023` re-export and `0028`: what the guest waits on each frame in the round. Coordinator edits none of those.

### Exact next action

On the worker's report: verify the round gets past "Now Loading", commit, then send swing input.

## 2026-11-18 run 23: round reaches the tee, patch 0028

- Worker `a85b98713035368ac` finished. Cause: main thread (tid 1) spins in `func_00871E30` (`sys_timer_usleep(1)`) until the counter at obj+0x304 equals obj+0x300; the counter job sits behind a SYNC with about 100 jobs of binary `0x00CB1F80` (9 to 10 ms each) on chain `0x11041700`, and the walker ran them serially.
- Fix in `libs/spurs/cellSpurs.c`: parallel lanes (default 4, `JC_PARALLEL=1` serial, max 8). SYNC, END, ABORT, FLUSH, JOBLIST wait for earlier jobs; NEXT, RESET_PC, CALL, RET, GUARD and parking do not. Closed guards still wait until shutdown.
- Patches: `0028-round-stall.patch` (`ppu_loader.cpp`, `sys_timer.c`, `cellGcmSys.c` GCM_REF_PACE_US/GCM_REFPROF hunk, `cellSpurs.c`; base HEAD+0002 for cellSpurs, HEAD+0008+0027 for cellGcmSys) and `0023` re-exported with JQ_PROF.
- Result: 1.0 FPS to about 3.5 FPS (7 to 8 rendered frames per 2 s, 7600 to 8700 draws), wait episodes 890 ms to 165 ms, tee shot reached at about 470 s wall time. Capture `docs/images/tee-shot-2026-11-18.png`. Last marker line: `bctr=0 nullcall=0 regist=0 stars=0 unresNID=0 unresCall=0 garbage=0 887A=0 lines=18834`.
- Not verified: GUARD semantics on hardware; why RSX_PROF's presented-frame counter reads 0; black course background; `JC_PARALLEL=5`; swing input; patch replay by Codex.

### Exact next action

Two workers, serialized by BUILD.lock: (1) why job `0x00CB1F80` costs 10 ms per run; (2) black course in the round and the presented-frame counter. Then swing input.

Workers started 03:25 (both Opus; reasons: SPU lifter and SPURS timing across systems; shader and RSX state diagnosis):
- `afb1e7562b35a3ce0` owns `libs/spurs/**`, `runtime/spu/**`, `tools/spu*`, lifted SPU output; output `0029-spu-job-speed.patch`.
- `aef6cb937ffc4a2cd` owns `libs/video/**`; output `0029` or `0030-rsx-course-lighting.patch`.

## 2026-11-18 run 24: SPU code was unoptimized

- Worker `afb1e7562b35a3ce0` finished. clang under `--driver-mode=cl` ignores `-O1/-O2/-O3` (coordinator re-checked with `-###`: only `/O2` or `/clang:-O2` reach cc1; `-ffp-contract=off` and `-std=` are ignored too, `-fwrapv`, `-fno-strict-aliasing`, `-w`, `-msse4.1` are honored). `port/CMakeLists.txt` now gives SPU sources `/clang:-O2;-msse4.1`.
- Job `0x00CB1F80`: 11.1 to 11.8 ms to 218 to 252 us. Round: about 3.2 to about 15 rendered frames/s; `done=131040 ran=131040 MISS=0`. Logs `boot-fix-1.02-jprof1-1.log` (before), `boot-fix-1.02-spuo2b-1.log` (after). Patch `0029-spu-job-speed.patch` adds `SPURS_JOB_PROF=1` timers (off by default).
- Not verified: byte compare of job output; draws per frame rose from 7600 to about 28000 in the round, cause unknown; presented-frame counter still 0; fly-through shows a flat cyan plane instead of terrain.
- Open: runtime library (`-O2` ignored) and lifted PPU code (`-O3` ignored) are built at -O0. Coordinator is timing one PPU file at `/clang:-O1` before changing flags; the change waits for the rendering worker `aef6cb937ffc4a2cd` so its builds are not disturbed.

### Exact next action

When the rendering worker reports: commit its patch, then turn on optimization for the runtime and PPU code, full rebuild, boot, compare.

## 2026-11-18 run 25: whole build optimized, patch 0030

- Worker `aef6cb937ffc4a2cd` finished: `0030-rsx-course-lighting.patch` (base HEAD + 0005 + 0008 + 0024 + 0026 + 0027). Depth texture formats 0x90 to 0x93 were dropped in `d3d12_bind_texture`; depth-only pass had no surface size; shadow compare units go through `rsx_fp_decompile_buffered_shadow_ex`; sampler key no longer includes unused border color (2048 to 41 to 57 samplers). `RSX_DEPTH_TEX=0` turns the depth-texture part off. New switches `RSX_CAP_MINDRAWS`, `RSX_CAP_NODISP`.
- Coordinator: `port/CMakeLists.txt` adds `/clang:-O2 -msse4.1` directory-wide and `/clang:-O1` for lifted PPU files under the cl driver; `PORT_PPU_O0_FILES` (default `ppu_recomp_063.cpp`) stay at -O0 because that file ran past the 9 minute build cap. Full rebuild took two capped passes. Build `46b71d5b`. Old exe kept at `build/O0-backup/`.
- Boot `opt2` (round script, 91 Cross presses 120 flips apart, `RSX_PROF=1`): title 62 FPS at 275 draws; demo 46 to 52 FPS; round 18 to 34 FPS at 734 to 1704 draws; tee by 220 s. Marker `bctr=0 nullcall=0 regist=0 stars=0 unresNID=0 unresCall=0 garbage=0 887A=0 lines=20395`. Swing gauge and club respond to Cross.
- Not verified: a completed shot (presses too far apart); tee close-up black background; presented-frame counter in some phases; cyan water and bunker edges; menus FPS on this build; 063 at -O1.

### Exact next action

Rendering worker on the tee close-up background and cyan surfaces; coordinator runs a swing with presses about 20 to 40 flips apart.

## 2026-11-18 run 26: shots played in a round

- `0032-pad-script-hold.patch` (`libs/input/cellPad.c`, upstream file was unmodified before): `PAD_SCRIPT_HOLD=<polls>`, default 40.
- Boot `swing2` (`PAD_SCRIPT_HOLD=5`, menu presses every 120 flips from 2500, then triples every 300 flips from 5700 with spacing 20/30/40/50/60 flips): shots hit, Remaining 316 to 292 to 237 y, club 1W to 3I, "Replay" prompt, POWER 100%. Marker `bctr=0 nullcall=0 regist=0 stars=0 unresNID=0 unresCall=0 garbage=0 887A=0 lines=17649`. Strip: scratchpad `swing2-strip.png`.
- This build included worker `ac91f4a86f53392c4`'s in-progress `libs/video` edits (it owns `libs/video/**`, output `0031-rsx-scene-persist.patch`: tee close-up background, cyan surfaces, present counter).
- Not verified: white background with purple grass in `swing2-1-t280.png`; which press spacing gives a good impact; real controller; holing out.

### Exact next action

On the rendering worker's report: check captures, commit 0031, re-run the swing script to see the close-up. Then: finish a hole by script, compile `ppu_recomp_063.cpp` at -O1 outside the build cap if allowed, refresh the handoff.

## 2026-11-18 run 27: hole 1 finished, patch 0031

- Worker `ac91f4a86f53392c4` (Opus) finished. `0031-rsx-scene-persist.patch` (`libs/video`, base HEAD + 0005/0008/0024/0026/0027/0030): `RSX_DISP_TEX` (display-buffer samples read a backbuffer copy), vertex buffer 1,572,864 vertices (768 MB), draw limit 4096, `batch_room` early offscreen flush. Its captures: scratchpad `persist\`.
- Boot `swing3` (same script as `swing2`, 41 triples, 440 s): hole 1 par 4 finished +4, leaderboard, hole 2 tee. Marker all zero, 20368 log lines. Strip: scratchpad `swing3-strip.png`.
- Open faults: lie block under the ball drawn as a large stretched shape (present before 0031 per the worker); black close-up frames from a zero depth restore; 8 dropped draws in 2 batches; heavy views 19 to 32 FPS.
- Not verified: 768 MB buffer on low-memory machines; same-course FPS against the old build; real controller.

### Exact next action

Start a rendering worker on the stretched lie block and the black depth-restore frames (owns `libs/video/**`, output `0033`). Tell Codex to add 0031 and 0032 to the patch replay and expose `RSX_DISP_TEX`, `PAD_SCRIPT_HOLD`, `JC_PARALLEL`, `RSX_SHADER_CACHE` as CLI flags. Refresh the handoff.

- Rendering worker `af92c80089099214a` (Opus) started 06:55: owns `external/ps3recomp/libs/video/**`, output `0033-rsx-lie-block.patch` (stretched lie block, black depth-restore frames, 8 dropped draws).
- 07:55 two more workers (Sonnet): audio `a5f6aa7a3f3cb0508` owns `libs/audio/**`, output `0034-audio-wav-capture.patch` (`AUDIO_WAV=<path>` capture and analysis); input `acd0d1afbac103c9a` owns `libs/input/**`, output `0035-pad-real-input.patch` (XInput and keyboard mapping test). Boots serialize on `BUILD.lock`.

## 2026-11-18 run 28: lie inset fixed, patch 0033

- Worker `af92c80089099214a` finished. `0033-rsx-lie-block.patch` (`libs/video/rsx_d3d12_backend.c`, on top of 0031): display draws scale the viewport from the guest surface size (1600x1080) to the backbuffer (`RSX_VP_SCALE=0` off). Debug switches added: `RSX_CAP_SECS`, `RSX_CAP_CB`, `VP_INFO`, `DSCONV_DBG=<addr>`. Final build sha8 `bbac1f19`, marker all zero. Sheets: scratchpad `lie\lie13sheet.png`.
- Open: black whole frames about 2 per 6 to 14 shots (`lie13-1-t235.png`, `t255`), not only depth restore (lie6 t250, 3405 draws); render stall on hole 1 intro in lie2, lie3, lie12 (game keeps running); 8 dropped draws.
- 08:2x rendering worker `a37c2a0a271fb1eb9` (Opus) started: owns `libs/video/**`, output `0036-rsx-black-frames.patch` (black frames, hole 1 intro stall, dropped draws).

## 2026-11-18 run 29: audio recorded and checked, patch 0034

- Worker `a5f6aa7a3f3cb0508` finished. `0034-audio-wav-capture.patch` (`libs/audio/cellAudio.c`): `AUDIO_WAV` writes a float stereo 48 kHz WAV, header fixed every ~2 s and at `cellAudioQuit`. Analysis: scratchpad `audio\` (`run1.wav`, `spec.png`). No defect found. A Python with numpy is at `%LOCALAPPDATA%\Python\bin\python.exe` (system `python` has PIL, no numpy).
- Not verified: listening, comparison with the original, in-round sound effects, device frame drops.

## 2026-11-18 run 30: real input mapping, patch 0035

- Worker `acd0d1afbac103c9a` finished. `0035-pad-real-input.patch` (`libs/input/cellPad.c`, new `libs/input/tests/test_pad_real_input.c`, on top of 0032). Test rebuilt and run by the coordinator: `test_pad_real_input: ok`.
- Coordinator boot `padchk` (exe built 08:16 by the rendering worker, includes its in-progress edits): picture froze on an attract-demo hole 4 tee from before 220 s to 420 s while audio kept running; flips stopped, so PAD_SCRIPT menu presses never fired. Sent to rendering worker `a37c2a0a271fb1eb9` as a repro of the stall.
- Not verified: scripted swing on a build with 0035 (worker's `padreal` run ended on the tee, inconclusive); physical controller.

## 2026-11-18 run 31: black frames and stalls fixed, patch 0036

- Worker `a37c2a0a271fb1eb9` finished. `0036-rsx-black-frames.patch` (`libs/video/cellGcmSys.c`, `libs/video/rsx_d3d12_backend.c`, on top of 0031 and 0033): `RSX_FLIP_MARK` (present at the flip marker), `GCM_FLIP_WRAP_WAIT` (bounded wait at the flip wrap), `RSX_FULL_SPLIT` (run full batches holding a display draw). Debug: `RSX_STALL_DBG`, `GCM_MARKER_DBG`. Worker logs `boot-fix-1.02-blk13-1.log` to `blk16-1.log`.
- Coordinator build `all36` (sha8 `d1eb1479`, every patch through 0036) and boot `round36` (450 s, swing script): no black frame, no stall, hole 1 played to a 2.6 ft putt; marker all zero, 17409 lines. Strip: scratchpad `round36-strip.png`. Also confirms scripted swings work with 0035.
- Open: 45 to 55 s load with no flips in every run; heavy views 12 to 17 FPS; stall cause inferred, sample 4 runs.

### Exact next action

Profile heavy course views (3000+ draws at 12 to 17 FPS) and the 45 to 55 s no-flip load. Ask Codex for patch replay of 0031 to 0036 and CLI flags for the new switches. Refresh the handoff.
- Workers started: speed `libs/video/**` (Opus, output 0037); load time, other `libs/**` except video/input/audio (Sonnet, output 0038).
- 10:50 load worker `a0258e126d503484f` finished, no patch: both no-flip loads are the `Sleep(4)` FIFO drain tick in `port/main.cpp:233` (Codex owns it); fix sent to Codex: `cellGcm_fifo_kick_wait(4)` as in `runtime/ppu/tests/boot_main.cpp:491`. Owner repeated: every launch muted and hidden; sent to Codex.

## 2026-11-18 run 32: speed patch 0037, guard atomic 0038, faster loads

- Worker `ac83fab0854188da0` finished. `0037-rsx-speed.patch` (`rsx_d3d12_backend.c`, `rsx_vertex_fetch.c/.h`): `RSX_VTX_FAST`, `RSX_VS_MEMO`, `RSX_SRV_DEDUP`, `RSX_PSO_REUSE`, `RSX_TEX_MEMO`, `RSX_STRIP_IX` (each `=0` off), `RSX_PROF=2`, `RSX_SPEED_CHECK=<n>`. A/B logs `boot-fix-1.02-xOff1-1.log` to `xOn2-1.log`.
- Coordinator `0038-spurs-guard-atomic.patch` (`libs/spurs/cellSpurs.c`, base = tree after 0028): `pending` atomic in `cellSpursJobGuardNotify`, `jg_wait`.
- Codex applied `cellGcm_fifo_kick_wait(4)` in `port/main.cpp` (load worker `a0258e126d503484f` found the 4 ms tick).
- Boot `round37` (build 2a459f40, 450 s swing script): hole 1 holed, hole 2 done, hole 3 tee; marker all zero, 25477 lines. Bad: black t248, t328; inverted colors t312; window title empty. Strip: scratchpad `round37-strip.png`.
- Regression worker started (Opus): owns `libs/video/**`, output `0039-rsx-regress.patch`.

## 2026-11-18 run 33: swing black frames are old, not a regression

- Worker `a2845cc475f943a16` finished, no patch. Black captures (41 shots, every 6 s): current 5, 0037 off 6, `GCM_FIFO_KICK=0` 5, round36 build 3. `RSX_CAP`: 42 of 150 presented frames black in swing runs. Cause: no-clear golfer frames get a black clear; depth at guest 0x0 is GPU-only so the 0x034C0000 copy reads 0. Evidence scratchpad `regress\` (`around.png`, `cap1\`, `cap36\`, sheets).
- Swing-frames worker started (Opus): owns `libs/video/**`, output `0039-rsx-swing-frames.patch` (persistent color surfaces without clear, GPU depth copy, hole 2 reflection rectangle).

## 2026-11-18 run 34: swing black frames fixed, patch 0039

- Worker `ad4be5c8a2b3ae6f2` finished. `0039-rsx-swing-frames.patch` (`rsx_d3d12_backend.c`): `RSX_DISP_DEPTH_TEX`, `RSX_DISP_DEPTH_KEEP`, `RSX_KEEP_DISPLAY` (each `=0` off); debug `RSX_ZWATCH`, `RSX_DISPZ_DBG`. Black 4/41 (sw1) to 0/41 (sw4); sheets scratchpad `swing\sw1-sheet.png`, `sw4-sheet.png`. CPU 95% during sw4.
- Open: inverted impact frames (2 per run, present with and without 0039); hole 2 upside-down rectangle; sw2 ran at 7 FPS once, cause unknown.

- 2026-11-18 14:46 worker ab8788e0d2ec2dc5b (Opus): game CPU and RAM use, patch 0041; no edits to libs/video (owned by ac8e17dd1bf56697f, 0040) or port/**. Cleanup: 211 stale build/run/scratch folders deleted, 129 GB.


- 2026-11-18 16:06 run 35 (worker ac8e17dd1bf56697f, imp9): impact negative flash is the game's blend (1-dst); hole 2 rectangle fixed by 0039 (0 of hole-2 shots); 0040 debug-only switches committed.

- 2026-11-18 16:57 run 36 (v41): 0041 CPU/RAM verified in a scripted round, hole 3 at ~300 s, marker zero, leftover 0. Worker ab8788e0d2ec2dc5b done.

- 2026-11-18 18:08 run 37 (worker abc7d181f8e400f2c): 0042 vertex packing, course private 1886 -> 1494 MB, same FPS/CPU; committed.

- 2026-11-18 18:43 run 38 (c43, worker a38f8763427d8f029): 0043 committed; 1 of 4 patched runs exited silently at ~255 s (open). UCS-2 port half sent to Codex.

- 2026-11-18 19:16 run 39 (worker a44c8e1b9e6089462): silent exit = external taskkill by another chat matching ghost_launch; 0044 exit trace committed.

- 2026-11-18 20:02 run 40 (menu survey, worker a1665996013dc4b22): title, main menu, Multiplayer, Customize, Shop, Select Character, Changing Room render ok. Hang A: load after Select Character (mn8) stops flips. Hang B (once): second Cross during Continue load. Yes/No dialog over main menu has empty message text. Worker a38911612677fdaa8 on hangs (0045).

- 2026-11-18 22:10 run 41 (worker a38911612677fdaa8, hg3-hg19): Hang A = SPURS job-chain registry leak (32 slots, never freed); 0045 reclaims on join and adds HANG_WD; hg11/hg14 load past Select Character, hg17 New Game to hole 4. Hang B not reproduced (cellSail movie close race, open).

- 2026-11-18 23:20 run 42 (workers a31c31a590fb370df, a239724824915f09e): blank menu text = no firmware font in test runs (harness now sets PS3_DEV_FLASH; port fallback sent to Codex). Missing letters = stale glyph atlas (sparse tex_csum); 0046 dense hash for 8-bit 1-2 channel textures. Roadmap doc added; measurement worker a7fd3791c3e3081e2 started.

- 2026-11-19 01:10 run 43 (workers a7fd3791c3e3081e2 measure, adb95aae5ec966cb7 texrep): course ~39 FPS, walker idles ~60% (guest/walker serialized), 4K clips at x=2047 (2048 depth); 0047 texture dump/replace committed; Real-ESRGAN in work/tools.

- 2026-11-19 03:00 run 44 (worker aef1995516fcec7da): HD pack v1, 541 textures 4x/2x via realesrgan-x4plus (tools/make_hd_pack.py), indexed 541 replaced 1150, 0 failures; needs TEX_REPLACE_MB=3072. At 720p grass is softer, not sharper; first-load stalls 23.9 s total over 300 s (PNG). Next: judge at 4K, DDS packs, detail-preserving terrain.
