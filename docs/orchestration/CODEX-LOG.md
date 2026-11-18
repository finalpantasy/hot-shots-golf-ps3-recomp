# Codex backlog log

## 1. Window mode, save root, and logging

- Changed `port/main.cpp`, `port/cli_options.cpp`, and `docs/CLI.md`. The Windows backend creates hidden windows with `WS_EX_NOACTIVATE` and without `WS_VISIBLE`. Fullscreen uses a borderless window on the primary monitor. The existing `PS3_VERBOSE` switch enables the runtime's additional diagnostics at any positive level.
- Exported runtime patches `0005-d3d12-window-mode.patch` and `0006-ppu-fs-save-root.patch`. File operations on the local PS3 user's save directory and the save callbacks use the same tree under the configured root. Both patches passed `git apply --reverse --check` against the working tree.
- Ran `.venv/Scripts/python.exe tools/recomp_pipeline.py build` in Git Bash under the shared lock. `work/runtime/logs/build-fix-1.02-codex-1.log` ends with `[done] build`. Tested executable SHA-256 `53364d5a985e146358d6893fa0956dcd0023156afe791540dd0091771f813721`.
- Ran the prescribed hidden-desktop boot with `--hidden --fullscreen --savedata work/runtime/codex-save-check --verbose 1`. `boot-fix-1.02-codex-1.log` shows `Window: borderless client=2560x1440 visible=0 noactivate=1 foreground=0`, `[boot] savedata: work/runtime/codex-save-check`, and the verbose-only `[cellGcmSys] BindTile(index=0)`. The run reached the 20-second cap after the quit request.
- Ran a second hidden-desktop boot with `--hidden --windowed --width 960 --height 540 --exit-after 12` and verbose set to 0. `boot-fix-1.02-codex-1-windowed.log` shows `Window: windowed client=960x540 visible=0 noactivate=1 foreground=0` and exited 0. The verbose-only tile and Z-cull messages were absent.
- Compiled and ran `save-root-check.cpp` with the port's Clang toolchain. The harness uses the production path functions with synthetic roots. `save-root-codex-1.log` reports `PASS: save mount and cellSaveData share the root; sibling remains on HDD0.` The game did not reach a save operation in either boot.


