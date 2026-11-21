# Command-line options

Run `HotShotsGolfRecomp [options] [path/to/EBOOT.elf]`.

Command-line flags take precedence over environment variables. Default paths start next to the executable or in the folder selected with `--build-dir`.

Options that take a value accept `--flag value` or `--flag=value`. Use the equals form when the value starts with `--`.
Explicit relative paths resolve from the launch directory. The process uses the build folder for internal relative paths.

On Windows, the launcher sets the game process's profile and temp paths under `<build dir>/cache/profile`. Windows and graphics drivers can still write system records outside the build folder.

| Flag | Environment | Default | What it does | Status |
|---|---|---|---|---|
| `--elf <file>` | none | `<game-dir>/USRDIR/EBOOT.elf` | PPU ELF to boot. A bare path with no flag does the same. | wired |
| `--build-dir <dir>` | none | Executable folder | Base folder for game discovery and runtime storage. | wired |
| `--game-dir <dir>` | `PS3_VFS_ROOT` | `<build dir>/game` or `<build dir>` | Game folder (VFS root). Holds `PARAM.SFO` and `USRDIR/`. | wired |
| `--hdd0 <dir>` | `PS3_HDD0_ROOT` | `<build dir>/hdd0` | Host folder for `/dev_hdd0`. | wired |
| `--hdd1 <dir>` | `PS3_HDD1_ROOT` | `<build dir>/hdd1` | Host folder for `/dev_hdd1`. | wired |
| `--savedata <dir>` | `PS3_SAVEDATA_ROOT` | `<build dir>/savedata` | Root for the save tree. | wired |
| `--dev-flash <dir>` | `PS3_DEV_FLASH` | `<build dir>/dev_flash` | Firmware folder. | wired |
| `--title <text>` | `PS3_TITLE` | `TITLE` from `PARAM.SFO` | Window caption. | wired |
| `--fullscreen` | none | off | Cover the primary monitor with a borderless window on Windows. | wired |
| `--windowed` | none | on | Start in a window. | wired (default) |
| `--width <px>` | none | 1280 | Render surface and windowed client width. | wired |
| `--height <px>` | none | 720 | Render surface and windowed client height. | wired |
| `--aspect <mode>` | `RSX_ASPECT` | `stretch` | `fit` centers a 16:9 image with black bars instead of stretching it. | wired |
| `--verbose <n>` | `PS3_VERBOSE` | 0 | Use 0 for normal logs or 1 through 9 to enable additional runtime diagnostics. | wired |
| `--rsx-shader-cache <dir or 0>` | `RSX_SHADER_CACHE` | `<build dir>/shader_cache_d3d12` | Windows D3D12 bytecode cache directory. A value of 0 disables disk caching. | wired |
| `--rsx-disp-tex <0 or 1>` | `RSX_DISP_TEX` | 1 | Sample the D3D12 display buffer as a texture on Windows. A value of 0 uploads from guest memory. | wired |
| `--rsx-disp-depth-tex <0 or 1>` | `RSX_DISP_DEPTH_TEX` | 1 | Sample the D3D12 display depth buffer as a texture. | wired |
| `--rsx-disp-depth-keep <0 or 1>` | `RSX_DISP_DEPTH_KEEP` | 1 | Preserve display depth across offscreen passes that use a separate depth surface. | wired |
| `--rsx-keep-display <0 or 1>` | `RSX_KEEP_DISPLAY` | 1 | Restore saved display color when a D3D12 batch starts without a guest color clear. | wired |
| `--rsx-vp-scale <0 or 1>` | `RSX_VP_SCALE` | 1 | Scale the guest viewport to the D3D12 backbuffer on Windows. | wired |
| `--rsx-flip-mark <0 or 1>` | `RSX_FLIP_MARK` | 1 | Present completed D3D12 draws at the flip marker on Windows. | wired |
| `--gcm-flip-wrap-wait <0 or 1>` | `GCM_FLIP_WRAP_WAIT` | 1 | Wait for the RSX walker when the flip command buffer wraps. | wired |
| `--gcm-fifo-kick <0 or 1>` | `GCM_FIFO_KICK` | 1 | Wake the frame clock on a FIFO kick. Set to 0 to wait 4 ms between checks. | wired |
| `--rsx-full-split <0 or 1>` | `RSX_FULL_SPLIT` | 1 | Submit full D3D12 batches that contain display draws on Windows. | wired |
| `--rsx-vs-memo <0 or 1>` | `RSX_VS_MEMO` | 1 | Reuse recently decoded vertex shader slots. | wired |
| `--rsx-pso-reuse <0 or 1>` | `RSX_PSO_REUSE` | 1 | Reuse pipeline state from the render prepass. | wired |
| `--rsx-tex-memo <0 or 1>` | `RSX_TEX_MEMO` | 1 | Reuse texture lookups within a frame. | wired |
| `--rsx-srv-dedup <0 or 1>` | `RSX_SRV_DEDUP` | 1 | Reuse matching shader resource descriptor tables. | wired |
| `--rsx-vtx-fast <0 or 1>` | `RSX_VTX_FAST` | 1 | Use the per-draw vertex fetch plan. | wired |
| `--rsx-strip-ix <0 or 1>` | `RSX_STRIP_IX` | 1 | Use indices for triangle strips, fans, and polygons. | wired |
| `--rsx-prof <0–2>` | `RSX_PROF` | 0 | D3D12 timings. Use 1 for a summary or 2 for a breakdown. | wired |
| `--rsx-speed-check <n>` | `RSX_SPEED_CHECK` | 0 | Compare optimized and original draw results. For vertex and strip checks, sample one in every n. Use with `--rsx-prof` to see the counts. | wired |
| `--mute` | `PS3_MUTE` | off | Silence Windows audio output. Mixing and WAV capture stay active. | wired |
| `--audio-wav <file>` | `AUDIO_WAV` | off | Record the mixed stereo audio as a 48 kHz floating-point WAV file. | wired |
| `--tex-dump <dir>` | `TEX_DUMP` | off | Save stable textures for HD pack creation. | wired |
| `--tex-replace <dir>` | `TEX_REPLACE` | off | Load matching PNG or DDS replacement textures. | wired |
| `--tex-replace-mb <MB>` | `TEX_REPLACE_MB` | 768 | GPU memory budget for replacement textures. | wired |
| `--jc-parallel <0–8>` | `JC_PARALLEL` | 4 | SPURS job-chain lanes. Values of 0 and 1 both select serial execution. | wired |
| `--pad-script-hold <polls>` | `PAD_SCRIPT_HOLD` | 40 | Positive number of pad polls to hold each scripted press. | wired |
| `--log <file>` | none | console | Save standard output and errors in one file. A bare name goes in `<build dir>/logs`. | wired |
| `--hidden` | none | off | Create a hidden window that cannot take focus on Windows. | wired |
| `--exit-after <sec>` | none | off | Quit cleanly (same path as the console's Quit Game) after this many seconds. | wired |
| `--help` | none | | Print the option list. | wired |
| `--version` | none | | Print the version. | wired |

`--fullscreen` and `--windowed` cannot be used together.

Relative `RSX_SHADER_CACHE` and `AUDIO_WAV` environment values resolve from the build folder. Relative `--rsx-shader-cache`, `--audio-wav`, `--tex-dump`, and `--tex-replace` arguments resolve from the launch directory. `--audio-wav` creates any missing parent directories and recording replaces a file at the selected path.

The local PS3 user's saves live in `dev_hdd0/home/00000001/savedata` under the save root. The older `PS3_GAMEDATA_ROOT` variable also works when no save root is specified.

The US font set uses `data/font/SCE-PS3-RD-R-LATIN2.TTF` under the firmware folder. Supply it from a local firmware dump.

## Game files

Put the extracted US game files in the `game` folder next to the executable. The folder needs `PARAM.SFO` and `USRDIR/EBOOT.elf` from the inputs for the selected fixed 1.02 or official 1.03 build. The launcher also checks for both files directly next to the executable. An alternate game root can contain the same layout under `PS3_GAME`.

The executable expects the US title ID `NPUA80864` in `PARAM.SFO`. On Windows it checks the ELF against the selected profile's SHA-256 in the project manifest before running the lifted code. Missing or incompatible startup files produce a setup message and exit code 1. A fresh Explorer console waits for Enter so the message stays visible.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Normal exit, `--help`, `--version`, or `--exit-after` |
| 1 | Startup failed because of game files, paths, or runtime initialization |
| 2 | Bad command-line option |
