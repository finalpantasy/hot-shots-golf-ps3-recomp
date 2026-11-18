# Codex goal: host, release and peripheral-module side

You are the second engineer on a PS3 static recompilation of Hot Shots Golf: World Invitational (`NPUA80864`, fixed 1.02 profile) in `F:\Hotshots Golf`. Claude is the lead orchestrator and owns the boot path. You own the host, release and peripheral-module side. Keep working through the backlog below without waiting for instructions. Stop only when the backlog is empty or you hit a real blocker.

Read first: `AGENTS.md`, `docs/orchestration/STATE.md`, `docs/CLI.md`, `docs/recomp-process.md`.

## Goal

Every release gate in `STATE.md` is met and verified, and no call to a peripheral system module reaches `[hle] unresolved NID`.

## Your files (Claude does not edit these)

- `port/main.cpp`, `port/cli_options.*`, `port/stubs.cpp`, `docs/CLI.md`
- `external/ps3recomp/libs/video/**` for window mode only (fullscreen, hidden, size). Do not change RSX command handling.
- `external/ps3recomp/libs/` modules for `cellHttp`, `sceNp`, `cellFont`, `cellFontFT`, `libgem`, `cellCamera`, `sys_crashdump`
- `external/ps3recomp/runtime/ppu/ppu_fs.cpp` for the save-data root mapping only
- `external/ps3recomp/tools/nid_database.py` (add names only)
- `patches/runtime/0005-*` and higher, `docs/orchestration/CODEX-LOG.md`

## Claude's files (do not edit)

`port/spu/**`, `port/CMakeLists.txt`, `pipeline.toml`, `tools/**`, `external/ps3recomp/libs/spurs/**`, `external/ps3recomp/runtime/**` except the one `ppu_fs.cpp` change, `docs/orchestration/STATE.md`, `docs/STATUS.md`, `README.md`, patches `0001` to `0004`. If you need a change there, write the diff into `CODEX-LOG.md` under "Requests for Claude".

## Backlog, in order

1. Wire the parsed but unwired flags: `--fullscreen`, `--savedata`, `--verbose`. Make `--hidden` create the window without `WS_VISIBLE` and without taking focus. The CLI worker's proposed runtime diff is summarized in `STATE.md` (window mode function in `libs/video/rsx_d3d12_backend.c`, a `PS3_SAVEDATA_ROOT` mapping in `ppu_fs.cpp`).
2. Verify portable defaults: with no flags and no environment variables, every path resolves under the executable's folder, nothing is written to AppData, the registry or the working directory, and missing game files give a plain message and a nonzero exit. Record the test in `CODEX-LOG.md`.
3. Name the unresolved imports. NIDs are the first 4 bytes of SHA-1 over name plus suffix (`tools/nid_database.py: compute_nid`). Library per NID comes from `analysis/fix-1.02/EBOOT.imports.json`. Current list: `cellHttp` `0x1395D8D1 0x224E1610 0x71714CDC 0xCAC9FC34 0xD7471088`; `sceNp` `0x45F8F3AA 0xF9732AC8`; `cellFont` `0x40D40544 0x90B9465E`; `cellFontFT` `0x7A0A83C4`; `libgem` `0x92CC4B34`; `cellCamera` `0x0E63C444` (called 23 times in 20 s); `sys_crashdump` `0xB20F87B3`. Use public PS3 SDK function name lists (RPCS3 source on GitHub is a good one) and confirm each by hash.
4. Implement each named import as a real handler that returns what a PS3 with no network, no camera and no Move controller returns (the documented error code, not a blanket `CELL_OK`), and that writes its output parameters. `cellFont` needs real behavior, since the game will draw text with it.
5. One executable: design the first-run flow so the single `.exe` detects extracted game files in its folder and starts, or tells the user where to put them. No second builder executable. Write the design in `CODEX-LOG.md` before coding it.

## Rules

- No fake success. No handler that returns `CELL_OK` while ignoring its arguments. Keep failures visible in the log.
- Builds and game runs are shared resources. Before either, create `work/runtime/BUILD.lock` containing `codex` and the time; if it exists, wait and retry. Delete it when done. One heavy process at a time, below-normal priority, nothing over 10 minutes.
- Build with `.venv/Scripts/python.exe tools/recomp_pipeline.py build` from Git Bash. Never system Python. Do not install or reinstall toolchains. Do not remove `--driver-mode=cl` or the library ordering in `port/CMakeLists.txt`.
- The game must never appear on the monitor or take focus. Launch it only with `python ~/.claude/skills/ghost-godot/ghost_launch.py <exe> <args>` (hidden desktop), 20 s cap. Kill only processes you started, by PID (`taskkill /PID <pid> /T /F`). Never kill by name.
- Boot environment: `PS3_VFS_ROOT=work/game/base-1.00`, `PS3_HDD0_ROOT=work/runtime/hdd0`, `PS3_HDD1_ROOT=work/runtime/hdd1`, `PS3_SAVEDATA_ROOT=work/runtime/gamedata`, `PS3_VERBOSE=0`, ELF `work/extracted/fix-1.02/USRDIR/EBOOT.elf`, logs to `work/runtime/logs/boot-fix-1.02-codex-<n>.log`.
- `external/ps3recomp` holds uncommitted patches from both of us. No `git stash`, `checkout`, `reset` or `clean` there. Export your changes with `git diff -- <your files> > patches/runtime/000N-<name>.patch`.
- Do not `git commit`, push or publish. Claude commits. The repository is public: no real names, emails or user-profile paths in any file.
- Never add game files, lifted game code, keys or shader microcode to tracked paths.
- American English. Plain words in docs.

## Mailbox

You and Claude share `work/mailbox/` (rules in its `README.md`). Read `work/mailbox/to-codex.md` before each backlog item and before every build or game run. Write to Claude in `work/mailbox/to-claude.md`: file-ownership requests, findings Claude needs, and blockers.

## Reporting

After each backlog item, append to `docs/orchestration/CODEX-LOG.md`: what changed (files), how you verified it (command and the log line that proves it), what is not verified, and any request for Claude. Then start the next item.
