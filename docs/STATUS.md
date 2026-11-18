# Hot Shots Golf recompilation status

Updated 2026-11-17.

## Current milestone: initial native scaffold

The target is US `NPUA80864`. Sony's update manifest lists 1.03 as the latest update. The `HP9000-NPHA80248` package is the separate Asian `NPHA80248` release and is excluded from the US build.

### Verified inputs

- Base 1.00 PKG: complete, 3,241,175,824 bytes, 1,369 files.
- Official 1.01 and 1.02 update PKGs: complete and contain EBOOTs.
- Official US 1.03 update PKG: downloaded from Sony's listed URL, 14,416,384 bytes, contains a 14,343,104-byte EBOOT.
- Third-party 1.02 fix PKG: complete; its EBOOT decrypts successfully without a separate RAP.
- DLC fix PKG: 97 small EDAT files extracted separately.
- Duplicate fix packages under `mngolf6alldlcps3u/` are byte-identical to the root copies.

Sony's published SHA-1 values do not match the supplied/downloaded package bytes. Size, content ID, and PKG structure match. Both Sony CDN endpoints returned identical 1.03 bytes. This remains a provenance warning, not a claimed checksum pass.

### Baseline analysis

Profile: third-party fixed 1.02 EBOOT.

- Decrypted ELF SHA-256: `42bdddc5e419f7e18bcbecdf02eb24748dd1da911ea7257d86d8477e24777a8b`.
- ELF64, big-endian PowerPC, machine 21, eight program headers.
- Entry OPD `0xD2FC90`, code `0x10240`, module TOC `0xD8E1E0`.
- 36,026 OPD descriptors and 32,751 unique functions reported by `ppu_loader`.
- 33,221 functions sent to the lifter after boundary recovery.
- 445 imports across 34 libraries; 387 have names in ps3recomp's database.
- One embedded SPU ELF with 133 detected functions and 6,964/9,344 function bytes covered. The remaining text bytes are data/padding or 33 `.word` entries.
- Accepted executable range ends at `0xD17018`.
- The lifter recovered 703 jump-table dispatchers with 6,641 internal case targets.
- Generated 67 PPU/HLE source files, about 2.34 GB before compilation.
- Static strings identify the Clap Hanz `MG6`/`chlib` codebase, SPURS v2, `MG6_SpursJobQueue`, and `fx_spurs_noise.elf`. No PhyreEngine identification has been established.

REA `open_binary` rejects ELF machine 21. Its Rizin and objdump fallback commands are unavailable on this Windows host. These are tool coverage limits, not evidence of a malformed game executable. ps3recomp's PPC-aware tools completed the baseline analysis.

### Toolchain

- ps3recomp v0.19.0 at `ae92407bb1d899e3d32143e360fe6e6d4d8fa1b5`.
- RPCS3 0.0.43-20623-0ebb6369, asset SHA-256 verified.
- Ratchet PKG reader at `e609b33377ee29ee20dda92fbec2e7823633d722`, used locally without modification.
- Portable LLVM/Clang 23.1.5 from llvm-mingw 20261104, archive SHA-256 verified.
- CMake and Ninja installed in the project-local Python environment.

### Open blockers

- Official 1.00, 1.01, 1.02, and 1.03 retail EBOOTs require `UP9000-NPUA80864_00-0000111122223333.rap` in RPCS3's exdata directory. No RAP was present in the supplied files.
- The current baseline is therefore fixed 1.02, not official 1.03. Do not label it official 1.03-compatible until the decrypted 1.03 ELF has been compared.

### Next evidence gates

1. Finish PPU/SPU code generation and HLE registration.
2. Configure and compile the native executable.
3. Run a bounded boot and record the first unresolved API or guest-address blocker.
4. Establish VFS overlays using the completed base/update extraction.
5. Compare official 1.03 after the user supplies its license, then generate a separate target profile.

### Data extraction

The accelerated extraction completed for base 1.00, official update 1.02, and official update 1.03 under `work/game/`. The original packages remain unchanged.

## 2026-11-17 update: first boot blocker fixed

The NULL-pointer cascade ending at `func_007B5B70+0x7E9` came from the runtime's `sys_lwmutex_lock` fast path skipping the import stub's TOC save, which made libc `malloc` return NULL. Fixed by `patches/runtime/0001-hle-fast-path-toc-spill.patch`. Current executable SHA-256 `f768037d2da3301312805d3ce244ce6c42f5b4914b2d46e6b5da54289b726c47`; the previous one is kept in `build/baseline-70290c23/`. Evidence, next blockers and release gates are in `docs/orchestration/STATE.md`.

## 2026-11-17 update 2: first SPURS job runs

The first SPURS job (`0x00CB3580`) is lifted and runs to completion, `cellSpursJobChainSetExceptionEventHandler` has a handler, and the title ID is read from `PARAM.SFO` (`NPUA80864`). The executable has command-line flags (see `docs/CLI.md`). The window still shows no game frame (0 draws). Next blockers and evidence: `docs/orchestration/STATE.md`.

## 2026-11-17 update 3: second SPURS instance starts

Two ps3recomp SPURS bugs are fixed: port bindings shared across instances, and a 32-entry job guard table. The game's `sgx-spurs-` instance now stays up and the host backend counts 2,048 draw calls in 20 s. The window is still one solid color. Two render jobs are not lifted yet. Evidence: `docs/orchestration/STATE.md`.

## 2026-11-17 update 4: six SPURS jobs lifted, base files found, GCM FIFO bug exposed

Six SPURS jobs are lifted and registered. The runtime now finds base-install files for this PSN title. With those files visible the game takes a different early path and the RSX command stream is misparsed, which removes the D3D12 device. That FIFO bug is the current first blocker. Evidence and the A/B run: `docs/orchestration/STATE.md`.

## 2026-11-17 update 5: first game frame

Two fixes in the GCM code stopped the GPU device loss: the default command buffer is now selected correctly, and the 1600x1080 display buffer is scaled into the 1280x720 window. The game then finishes its graphics system setup and draws its autosave notice. Only the blue channel is shown.

The frame does not appear on every boot. In two of four 20 second runs a game thread called through an unset function table and the window stayed black. 13 SPURS jobs are lifted, and two of them have been seen running. No menu, input, audio or gameplay yet.

## 2026-11-17 update 6: black boots fixed, title menu starts loading

The black boots came from the SPURS runtime sending an invented job-completion event next to the real one the sound job posts. The game used the invented counter as a table index and called through unrelated memory. The runtime now sends no invented event for a job chain whose jobs report for themselves. Four of four boots are clean, and the sound module registration error is gone.

`cellFsReadWithOffset` was missing and is now implemented. The game leaves the autosave notice, shows "Auto-loading..." and starts loading the title menu, course background and avatar archives.

Still open: only the blue channel is shown, one SPURS job used during the title load is not lifted, and the movie player imports (`cellSail`) are not implemented.

## 2026-11-17 update 7: correct colors, intro movie reached

The blue-only picture is fixed. The RSX vertex code ignored vertex arrays with stride 0, which the game uses for its 2D color values, so red and green came out as zero. See `docs/images/autosave-notice-2026-11-17.png`.

The SPURS job used by the title load is lifted (14 jobs, no dispatch misses). The game now shows the JAPAN Studio logo and starts its intro movie, where it stops: the movie player library (`cellSail`) is a stub. There is no video decoder in the port yet.

## 2026-11-17 update 8: title screen, New Game accepted

The game reaches its title screen ("New Game", "HSG Info") in about a minute. See `docs/images/title-screen-2026-11-17.png`. Four fixes got it there:

- `cellSail` now reports the full player event sequence and ends the intro movie at once, with the log line `[cellSail] no decoder: movie <uri> skipped`. No video is decoded.
- `sys_event_port_send` sets the event source of an unnamed port to `(pid << 32) | port id`. It sent 0, and the game drops movie player events whose source does not match.
- The job chain walker treats a jump-to-self command as a parked chain and polls it. It used to stop the chain after 4096 reads, after which no queued job ran and the title drew at 0.25 FPS.
- Invented job completion events go only to the queues of the chain's own SPURS instance. They went to every attached queue, including the sound engine's, which crashed its service loop once the chain above stayed alive.

A scripted Cross press (`PAD_SCRIPT`) on "New Game" is accepted: the game writes save `NPUA80864` (five data files), looks for saves of the previous game (`BCUS98115`), and loads the next scene. That scene has not been looked at yet.

Open: `cellOskExtUtility` imports `0x7C95FEB8` and `0x09565B21` are unresolved and are called after "New Game". The title runs at 8 to 20 FPS. A few squares in the title sky draw black or gray.

## 2026-11-17 update 9: a course draws

Left alone at the title, the game starts its attract demo, loads a course and draws a hole with its HUD. See `docs/images/demo-hole-2026-11-17.png`. The picture is wrong in several ways: lighting is too dark, the sky and part of the ground are black, and stray light-blue triangles appear.

- `cellSpursJq` (the SPURS job queue) is implemented: queues, ports, push, sync, shutdown and join, with one worker thread per queue that runs jobs through the existing SPU job dispatch. The demo pushes about 32 jobs a frame. All of them use one SPU binary at `0x00CAB400` (9536 bytes, fingerprint `B24195A9C86BC758`) that is not lifted yet, so each is logged as not run. `cellSpursJobQueuePort2Sync` has not been called at runtime, so its wait is untested.
- A job chain parked on a closed guard now waits until shutdown. It gave up after 20 seconds, which ended chains during the course load.

## 2026-11-17 update 10: foliage and sky fixed, no unresolved imports

- Foliage draws cut out. The D3D12 backend ignored the RSX alpha test; it now runs in the pixel shader.
- The title sky has no holes. A triangle strip split across vertex batches lost two triangles at each join.
- The two `cellOskExtUtility` imports are implemented (they record the input device lock). A 160 second boot logs 0 unresolved imports.
- The audio mixer produces sound: peak 0.20 in a muted run. Nobody has listened to the output.
- The build generates the HLE import table from the library sources, so the manual `gen_hle_nids.py` step is gone.

Open: course terrain is too dark, cause unknown. In the latest run the title took 140 seconds to appear (60 to 70 before), cause unknown. Menus after the title are not captured.

## 2026-11-18 update 11: scenes after the title draw

A scripted Cross on "Continue" is accepted and the next scene loads. That scene, and the attract demo's play before the title, drew black at first. Each gameplay frame starts with a shadow pass into a depth-only target, and the backend counted those draws as screen content, so it presented the shadow pass alone as a black frame. Depth-only draws no longer count as display draws (patch `0026`; `RSX_DEPTH_DISPLAY=1` restores the old rule).

Captures after the fix show course fly-bys and the demo's shot screen with the power gauge. Scripted input now counts game frames (`PAD_CLOCK=flips`), because load time varied by a factor of three with machine load.

Open: course terrain is too dark. The shot screen has a black background behind the golfer, and two captures show mostly sky; neither is compared with real hardware. Frame rate in play is 11 to 14 FPS. Line primitives are skipped.

## 2026-11-18 update 12: menus

Scripted Cross presses (`PAD_SCRIPT` on frame counts) go from the title through the clubhouse menu ("Single Player", "Challenge") to the Challenge course select, which lists Maple Leaf Golf Club. Text, portraits and the 3D clubhouse draw at 22 to 25 FPS. Log `boot-fix-1.02-play-1.log`: 0 unresolved imports, 0 NULL calls. Starting a round is the next thing to try.

## 2026-11-18 update 13: a round starts loading

More scripted presses pick the course, the character (Yuna) and the shot type, and confirm "Go to Course". The round then loads: course sound files open, the job queue runs (4064 jobs, 0 misses), and the frame has 1143 draws. It runs at about 1 frame per second with "Now Loading" still on screen for the 150 seconds watched. Frame rate falls as draw count rises everywhere (277 draws: 20 to 36 FPS; 394: 13; 600 to 900: 9 to 14), so frame time in the renderer is the next thing to fix.

## 2026-11-18 update 14: renderer time cut, the round stall is a guest wait

Profiling (`RSX_PROF=1`) found two costs in the renderer. The D3D12 debug layer was on by default, and every shader was compiled at run time on the command thread: 88 compiles, 50.8 seconds per run. The debug layer is now opt-in (`D3D12_DBG=1`) and compiled shaders are cached in memory and on disk (patch `0027`). In the same demo scene the frame body went from 24.6 ms to 10 to 12 ms, and the demo from about 11 FPS to 15 to 28 FPS.

The 1 frame per second in a real round is not render time. The renderer is idle for more than 2 of every 2.3 seconds and 95 percent of process time is in waits, so the game is blocked on something once per frame. That is being traced now.

Open: the sampler table fills at 2048 entries in a round, after which new sampler states fall back to defaults. Large flat cyan water surfaces appear in one capture.

## 2026-11-18 update 15: the round reaches the first tee

The wait was in the job chain walker. Once per frame the main thread waits for a counter job that sits behind about 100 jobs of one SPU program (`0x00CB1F80`, about 10 ms each). The chain alternates job and guard entries, and the walker ran every job one at a time. That was the stall. It now hands jobs to 4 parallel lanes (patch `0028`; `JC_PARALLEL=1` restores the old order, up to 8 lanes). Only sync, end, abort, flush and job-list entries wait for earlier jobs. No public source was found that says whether a guard entry waits for earlier jobs on hardware, so that part is a reading, not a checked fact.

The round now gets past "Now Loading" to the first tee: the golfer, the ball and the shot HUD are drawn (`docs/images/tee-shot-2026-11-18.png`). Two things are wrong. The course behind them is nearly black, and the game runs at about 3.5 frames per second with 7600 to 8700 draws per frame. The renderer is still idle for most of each frame, so the limit is the same SPU job, not drawing. No swing input has been sent yet.

## 2026-11-18 update 16: lifted SPU code was built without optimization

The pipeline runs clang with `--driver-mode=cl`. In that mode clang ignores `-O2` ("argument unused during compilation"), so the lifted SPU jobs were compiled with no optimization and the slow scalar helper versions. `port/CMakeLists.txt` now passes `/clang:-O2` and `-msse4.1` for those sources. Job `0x00CB1F80` went from about 11.7 ms to 0.22 ms per run, and the round went from about 3.3 to about 15 rendered frames per second (36 to 38 in the hole fly-through). The job queue still reports 131040 of 131040 done with 0 misses. Job output was not compared byte for byte.

The same ignored flag means the runtime library and the lifted PPU code are also built without optimization. That is the next thing to fix and measure.

The course is still drawn wrong in the round: the fly-through shows the sky and mountains above a flat cyan plane where the terrain should be.

## 2026-11-18 update 17: everything is now built optimized, course is lit

The ignored optimization flag applied to the whole build. `port/CMakeLists.txt` now passes `/clang:-O2` to the runtime and `/clang:-O1` to the lifted PPU files when the cl driver is in use. One file, `ppu_recomp_063.cpp` (68 MB), did not finish at `-O1` in 9 minutes and stays unoptimized.

Measured in one boot of the new build: the title runs at about 60 FPS, the demo flyover at 46 to 52 FPS with 686 to 902 draws, and the round at 18 to 34 FPS with 734 to 1704 draws. The first tee is reached in under 220 seconds; it took about 470 before. The marker line is all zeros.

The dark terrain is fixed (patch `0030`). The game draws a shadow map into a depth-only surface and the ground shader reads it as a depth texture with a comparison. The backend dropped depth texture formats, so the shader read 0 and the sunlight term went to 0. The same patch stops the sampler table from filling: the unused border color was part of the sampler key.

Scripted Cross presses in the round start the swing gauge and the club moves. The presses were 120 frames apart, too slow to finish a shot, so no ball has been hit yet. The tee close-up still has a black background. That frame has no color clear and seems to expect the previous frame's picture to persist, which is not proven.
