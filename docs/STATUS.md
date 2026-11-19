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

## 2026-11-18 update 18: shots are played in a round

Scripted presses were held for 40 pad polls each, so presses close together read as one long press and the swing was cancelled. `PAD_SCRIPT_HOLD` now sets the hold length (patch `0032`). With 5-poll presses in groups of three, the game plays shots: the gauge runs, the ball is hit, a "Replay" prompt appears, and the remaining distance goes from 316 to 292 to 237 yards with the club changing from the driver to a 3 iron. Captures are `docs/images/round-tee-2026-11-18.png` and `docs/images/round-second-shot-2026-11-18.png`.

Still wrong: the close-up with the big ball has a black background, and one capture of it had a white background with purple grass. No real controller has been tried.

## 2026-11-18 update 19: a hole is finished, scene drawn in full

Patch `0031` fixes three rendering faults. The tee close-up was black because the game copies the previous frame from a display buffer the backend never filled; draws that sample a display buffer now read a copy of the backbuffer (`RSX_DISP_TEX`, on by default). Water, bunker rims and the ground were flat cyan because the shadow pass filled the vertex buffer and the 2048-draw limit, so the main pass was cut off. The vertex buffer now holds 1,572,864 vertices (768 MB, halved if the allocation fails) and the draw limit is 4096. The same overflow left frames with nothing to present; presented frames now match the game's flips within 2 per 2-second window.

With the whole scene drawn, views with 1800 to 2300 draws run at 19 to 32 FPS and lighter views at 40 to 60 FPS.

A scripted round (boot `swing3`, 440 seconds) finished hole 1, a par 4, at +4, showed the leaderboard and started hole 2. Captures are `docs/images/round-leaderboard-2026-11-18.png`, `docs/images/round-swing-2026-11-18.png` and `docs/images/tee-closeup-2026-11-18.png`.

Still wrong: the grass block under the ball is often drawn as a large stretched shape, in green, gray or black and white, covering the swing gauge. A few close-up frames are black because a depth restore reads zero. 8 draws were dropped in one run. The 768 MB buffer has not been tried on a machine with little memory. No real controller has been tried.

## 2026-11-18 update 20: the lie inset draws in its corner

The small picture of the ball's lie (grass or sand under the ball) was drawn stretched across the whole screen. The game draws it at 1277,777, 323 by 258 pixels on a 1600 by 1080 surface. That rectangle failed the bounds check against our 1280 by 720 backbuffer, so the draw fell back to a full-screen viewport. Draws to the display now scale their viewport from the guest surface size to the backbuffer (patch `0033`, `RSX_VP_SCALE=0` turns it off). Close-up frame rate is unchanged at 14 to 21 FPS. Capture: `docs/images/round-address-2026-11-18.png`.

Still wrong: whole frames come out black in about 2 of every 6 to 14 shots. The depth surface at `0x034C0000` was checked and is handled correctly, so it is not the only cause. In some runs the picture stops updating on the hole 1 intro while the game keeps running; this happened before `0033` too.

## 2026-11-18 update 21: audio checked from a recording

`AUDIO_WAV=<path>` now writes the final mix as a 32-bit float stereo 48 kHz WAV, with the header updated every 2 seconds so a killed run still leaves a readable file (patch `0034`). The device stays muted while recording.

A 150-second attract run gave 148.5 seconds of audio, so it keeps pace with real time. Music starts at 5.5 seconds. Level is RMS 0.048, peak 0.47, with no clipping and no clicks: the largest jump between samples is 0.196. Left and right are balanced (energy ratio 1.05, correlation 0.86). The spectrum shows harmonic music, not a tone or buzz. The 25 strongest peaks sit within 5.3 cents of musical pitches; a 44.1 versus 48 kHz mix-up would put them about 147 cents off. There is a 5-second silent gap at 32 to 36 seconds and shorter ones near 100 and 125 to 137 seconds; whether the original game has them was not checked.

Nobody has listened to it yet, and only the attract demo was recorded.

## 2026-11-18 update 22: controller and keyboard mapping tested

The pad code was split into `pad_xinput_to_host()` and `pad_keyboard_apply()` so a test can feed it fake controller and key states (patch `0035`). The test `libs/input/tests/test_pad_real_input.c` passes. It covers every button, both triggers, stick extremes and the dead zone, the packet lengths for pressure and sensor modes, unplugging a pad while a button is held, and every keyboard key, including losing window focus.

One defect was fixed: XInput sticks never reached 0, and full up read as 1 instead of 0.

| PS3 | Controller (XInput) | Keyboard |
|---|---|---|
| Cross, Circle, Square, Triangle | A, B, X, Y | Z, X, A, S |
| L1, R1 | LB, RB | Q, W |
| L2, R2 | LT, RT | 1, 2 |
| Start, Select | Start, Back | Enter, Tab |
| D-pad and left stick | D-pad, left stick | Arrow keys |

The keyboard is read only while the game window has focus. A controller on XInput slot 1 or higher becomes PS3 port 1, which leaves port 0 on the keyboard; one controller is normally slot 0. Nothing has been tried with a physical controller, and the scripted swing was not rechecked on this build because the picture stalled in that run (see update 20).

## 2026-11-18 update 23: black frames and picture stalls fixed

Black frames were real: the presented image was black, not just the capture. When the command buffer was backed up across a ring wrap, the drain ran past a flip marker, so one present got the scene without its HUD and the next got the HUD over black. Presents now happen at the flip marker itself (`RSX_FLIP_MARK`). Split presents went from 5 to 41 per run to 0 to 2.

The picture stopped because the flip at the ring wrap let the game restart at the start of the ring while the backend was still in its first half. The backend never reached the old lap's last flip, and the game waited for it forever. At the wrap the game now waits, with a time limit, until the backend is past the half (`GCM_FLIP_WRAP_WAIT`). This cause was read from the stalled state, not caught in a trace. Stalls hit about 6 of 12 runs before and 0 of 4 after.

Batches that fill up after already holding a display draw are now run and the backbuffer kept (`RSX_FULL_SPLIT`), so no draws are dropped. Each fix has a switch that turns it off with `=0`. All three are in patch `0036`.

Check on a build with every patch through `0036` (boot `round36`, 450 seconds): no black frames, no stall. Scripted presses played hole 1 from the tee to a putt 2.6 feet from the hole: 319, 302, 208, 70.8 and 5.4 yards remaining, then 6.5 feet. The title runs at 59 FPS; course views with 1700 to 3500 draws run at 12 to 28 FPS. Captures: `docs/images/round-approach-2026-11-18.png`, `docs/images/round-putt-2026-11-18.png`.

Still open: every run has a 45 to 55 second load with no flips; heavy course views run at 12 to 17 FPS.

## 2026-11-18 update 24: course views twice as fast, three holes reached

Patch `0037` cuts the renderer's per-draw work: vertex fetch is planned once per draw, shader lookups compare program bytes before hashing, texture descriptors and pipeline states are reused when they match the previous draw, and indexed strips are converted once. Each change has a switch to turn it off. In runs alternating the switches off and on, on one build with the PC's CPU 68 to 72% busy, heavy course views went from 12 to 14 FPS to 22 to 24 FPS, and the backend's recording time fell from 40 to 44 ms to 15 to 16 ms per frame. `RSX_SPEED_CHECK` runs the old and new code side by side; it found no differences over 5.2 million vertices.

Patch `0038` makes the SPURS job-guard counter atomic; a notify could be lost when the game thread and the job-chain thread updated it at the same time.

Codex replaced the 4 ms sleep in the FIFO drain loop (`port/main.cpp`) with a wait that wakes when commands arrive. The game polls for each marker during loads, so the loads were paced by that sleep.

With all three, a 450-second scripted round (boot `round37`) holed out on hole 1, finished hole 2 and reached hole 3, where the same script on the previous build was still putting on hole 1. Capture: `docs/images/round-holed-2026-11-18.png`.

New problems in that run: two black captures mid-hole and one frame with inverted colors (purple grass, orange sky). A worker is narrowing down which change causes them. The window title no longer shows FPS.

## 2026-11-18 update 25: correction, the swing still has black frames

Update 23 said a 450-second run had no black frames. That run took a capture every 16 seconds. With captures every 6 seconds, both the `round36` build and the current build show black frames during swings: 3 and 5 of 41 captures. A backbuffer dump showed 42 of 150 presented frames black, in runs of 60 to 120 frames from address to impact. So the black frames fixed in update 23 were one cause, not the only one, and the speed and load changes did not cause these.

Cause, found by a worker: during the swing the game draws one background frame, then for several frames draws only the golfer on top of it, starting without a clear and restoring depth from a saved copy at `0x034C0000`. The backend clears the color target to black at the start of those frames, and its main depth buffer lives only on the GPU, so the saved copy reads as zero and every later draw fails the depth test. The inverted-color frames at impact may be the game's own flash effect; that is not proven. A worker is changing the backend to keep surfaces across frames and to copy depth on the GPU.

The upside-down rectangle at the bottom left of hole 2 is probably the river's reflection render showing on screen; it is not fixed.

## 2026-11-18 update 26: swing frames no longer go black

Patch `0039` copies the real depth buffer when the game saves it for the swing, stops a bloom pass from clearing the shared depth buffer mid-frame, and keeps display surfaces across frames that start without a clear. Switches: `RSX_DISP_DEPTH_TEX=0`, `RSX_DISP_DEPTH_KEEP=0`, `RSX_KEEP_DISPLAY=0`. Over two 450-second runs with a capture every 6 seconds, black captures went from 4 of 41 to 0 of 41. The two runs reached different points of the round, so they are not the same scenes. In-round frame rate was about 22 FPS with the system CPU 95% busy.

Still wrong: 2 frames per run at impact have inverted colors (purple grass, orange sky). The upside-down rectangle on hole 2 is not fixed.

## 2026-11-18 update 27: impact flash and hole 2 rectangle

The inverted frames at impact are the game's own effect. The last draw of those frames is a white full-screen quad with blend source ONE_MINUS_DST_COLOR and destination ZERO, so the game asks for a negative of the screen for about 8 frames, and the backend draws what it asks. Blend, color and depth state decode correctly. This has not been compared against hardware or RPCS3.

The upside-down rectangle on hole 2 was fixed by patch `0039`. Before it, three fragment programs read display depth from guest memory that was never written, so a depth-faded quad showed as a rectangle. In a 524-second run with a capture every 6 seconds (`imp9`), the round reached hole 3, hole 2 showed the river with no rectangle, and no capture was black. With the three `0039` switches off, the rectangle comes back.

Patch `0040` adds debug switches only, all off by default: `RSX_BLEND_LOG`, `RSX_SURF_LOG`, `RSX_CAP_NEWVP`, `RSX_CAP_SURF`, `RSX_CAP_SRCBLEND`, `VDATA_DBG`.

## 2026-11-18 update 28: less CPU and RAM (patch 0041)

The main game thread spent 40 to 70% of its time in a tight `usleep(30)` loop while waiting for the GPU. After 200 microseconds of polling it now sleeps on a timer, and the GPU fence and SPURS job completion wake it early. The vertex buffer starts at 128 MB and grows to 768 MB the first time a scene needs it. Switches: `RT_IDLE_WAIT=0`, `RT_VB_GROW=0`, `RT_IDLE_SPIN_US=<n>`.

A/B on one build with the switches off, then on: title 1.68 to 1.12 cores and 1,671 to 1,149 MB private; menu 1.98 to 1.40 cores; course 3.03 to 2.59 cores at about 27 to 30 FPS. Course RAM did not change, because a course fills most of the buffer. A scripted 450-second round on the new build reached hole 3 at about 300 seconds, with no stall and nothing left running after exit.

## 2026-11-18 update 29: packed vertices cut course RAM (patch 0042)

Each vertex used to take 256 bytes, 16 slots whatever the shader read. Patch `0042` stores only the attributes the vertex program reads, about 115 bytes per vertex on a course, and the vertex buffer grows in steps to at most 384 MB instead of 768 MB. Each SPU job also builds its 256 KB local store in place instead of in a separate zeroed buffer. Switches: `RSX_VB_PACK=0`, `RSX_VB_PACK_CAP_MB=<n>`, `RSX_VB_PACK_STATS=1`, `SPU_JOB_REUSE=0`.

A/B over a 450-second scripted round on one build, packing off, then on: course private memory 1,886 to 1,494 MB, working set 1,626 to 1,223 MB, peak private 1,920 to 1,615 MB, title 1,177 to 1,010 MB. CPU and FPS did not change (about 2.3 cores and 32 FPS on the course). Hole 1 and hole 2 render the same either way; the runs are not frame-identical, so this is a visual match, not a pixel match.

## 2026-11-18 update 30: offline imports from Codex (patch 0043)

Patch `0043` applies three of Codex's proposals: seven offline `sceNpTus` imports, five `cellSsl` getters, and syscall 988 returning `CELL_ENOSYS` for a null buffer instead of reading address zero. Only the `cellL10n.c` half of the UCS-2 proposal is in; its registrations belong in `port/stubs.cpp`, which Codex owns.

Four 400-second scripted rounds ran on the patched build. Three ran the full time with every marker at zero; two of those reached hole 3 or later. One exited silently at about 255 seconds on hole 1, with no crash line in the log and no Windows error event. An unpatched run did not exit. The cause is unknown, so this exit is an open question, not a known regression.

## 2026-11-18 update 31: the silent exit was an outside kill (patch 0044)

The run that stopped at about 255 seconds in update 30 did not exit on its own. A process search by another tool on the same PC matched this run's launcher and ended it by PID, which also ended the game. Patch `0043` is not involved.

Patch `0044` adds an exit trace, on by default (`RT_EXIT_TRACE=0` turns it off, `RT_EXIT_TRACE_FILE=<path>` copies it to a file). Every way out of the process now logs one `[exit-trace]` line with time and thread: guest `sys_process_exit` with its caller, `exit`, `ExitProcess`, abort, unhandled exceptions, host quit, window close messages, Present failures and D3D12 device removal. A run killed from outside shows only the start-up line. Three more 400-second rounds ran to the end with no early exit.

## 2026-11-18 update 32: menus no longer hang the course load (patch 0045)

After Select Character or the Changing Room, the course load stopped and the screen froze. The SPURS job-chain table had 32 slots and never freed one. Select Character and the Changing Room create a job chain for each model and shut it down when the model goes away, but the slot stayed taken. Chain 33 was refused. `CreateJobChainWithAttribute` still returned success, so the game waited on work that never ran. At most 24 chains were alive at once, so the leak caused the hang, not a lack of slots.

Patch `0045` frees a chain's slot when the game joins it after shutdown, once its walker thread has exited, and raises the table to 256 slots (`JC_RECLAIM=0` restores the old behavior). A full table now logs `registry full ... this chain will NOT run`. It also adds `HANG_WD=<seconds>`: when no frame has been shown for that long, it prints every guest thread's wait and every job-chain walker. It is off unless set.

Two runs through Select Character loaded and played the round, with chains past number 32 running. A New Game round reached hole 3 and went on to load hole 4 without a stall. Nothing froze. Hang B (a second Cross during the Continue load) did not happen in two tries. It is still open. The likely cause is a timing race in the movie player when the press lands while the intro movie is closing, since in the one failing run the player closed the stream but never finished shutting down.
