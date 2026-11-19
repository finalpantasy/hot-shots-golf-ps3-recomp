# Modern PC features roadmap

Target set on 2026-11-18: 120+ FPS, 4K output, HD textures, upscaling and frame generation. The course runs at about 27 to 30 FPS at 1280x720 today.

## What the code allows

- The game draws a 1600x1080 display surface and the backend scales it to the window. Larger `--width`/`--height` values may already raise the main pass resolution. The shared depth buffer is fixed at 2048x2048, so 4K needs it resized.
- Frames are paced by a 60 Hz ticker in `port/main.cpp` built on `GetTickCount64`, which steps in 15.6 ms units. Nobody has yet measured whether game logic slows down when FPS drops. Until that is known, 60 is the game's rate, and going past it means frame generation.
- PS3 rendering has no motion vectors. DLSS, FSR 2/3 and XeSS need them, so they are not near-term. FSR 1, NVIDIA Image Scaling and CAS work without them. So does driver frame generation (AMD AFMF 2, NVIDIA Smooth Motion).
- Textures upload in `vp_upload_tex_slot` in `rsx_d3d12_backend.c`, which is where a hash-keyed dump and DDS replacement can hook in.

## Milestones

| # | Milestone | Size | Risk | Proof |
|---|---|---|---|---|
| 1 | Measure: per-thread profile, `RSX_PROF=2`, logic-vs-FPS timing, captures at 1080p, 1440p and 4K | S | Low | Report naming the hottest thread and the resolution limits |
| 2 | Even frame pacing (QPC ticker at 59.94 Hz), borderless window, forced 16x anisotropic filtering, FXAA | S | Low | Frame-time spread under 1 ms on the title; sharper ground in A/B captures |
| 3 | 4K output: depth sized to the backbuffer, screen-copy mapping fixed, pixel-position shaders checked | M | Medium | 1080p and 4K captures of tee, putt and swing match, with no clipping |
| 4 | Steady 60 on the course: `ppu_recomp_063` above -O0, draw recording off the present thread | M-L | Medium | 450 s round holds 60 FPS (1% low at or above 55) |
| 5 | Effect passes (bloom, depth of field, shadows) rendered at the internal scale | M | Medium-high | No seams at 2x and 3x |
| 6 | FSR 1 / CAS upscale pass; 120 FPS through driver frame generation | S-M | Low | 1440p internal to 4K output; 120 FPS shown with AFMF or Smooth Motion |
| 7 | Texture dump and replace by hash, DDS loader | M | Medium | A replaced course texture shows in game at higher resolution |
| 8 | Ultrawide through a guest aspect patch and HUD anchoring | L | High | 21:9 capture with no stretching |

## Milestone 1 results (2026-11-19)

| Measure | Result |
|---|---|
| Course, steady, 1080p window | About 39 FPS |
| Renderer thread per frame on the course | 4.3 ms reading commands, 7.4 ms recording (about 6 ms of it CPU vertex fetch for about 200,000 vertices), 9.1 ms draining, 0.1 ms present, 18.7 ms idle |
| CPU by thread on the course (share of one core) | Renderer 48%, main PPU 37%, SPURS job chain 27%, four SPURS lanes about 12% each |
| 1920x1080 | Runs, no clipping, same FPS as 720p |
| 2560x1440 and 3840x2160 | Run, but drawing stops at x=2047 because the shared depth buffer is 2048x2048 |
| Game logic tied to frame rate | Unclear. One unmatched comparison gave a different swing power at 58 FPS and 9.5 FPS |

No thread is at 100%. The renderer waits about 60% of each frame for the game, and the game waits for the renderer, so their work runs one after the other. Overlapping them is the first speed target, CPU vertex fetch the second. Resolution does not change FPS, so 4K is blocked only by the depth buffer size.

