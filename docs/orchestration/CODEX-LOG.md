# Codex backlog log

## 1. Window mode, save root, and logging

- Changed `port/main.cpp`, `port/cli_options.cpp`, and `docs/CLI.md`. The Windows backend creates hidden windows with `WS_EX_NOACTIVATE` and without `WS_VISIBLE`. Fullscreen uses a borderless window on the primary monitor. The existing `PS3_VERBOSE` switch enables the runtime's additional diagnostics at any positive level.
- Exported runtime patches `0005-d3d12-window-mode.patch` and `0006-ppu-fs-save-root.patch`. File operations on the local PS3 user's save directory and the save callbacks use the same tree under the configured root. Both patches passed `git apply --reverse --check` against the working tree.
- Ran `.venv/Scripts/python.exe tools/recomp_pipeline.py build` in Git Bash under the shared lock. `work/runtime/logs/build-fix-1.02-codex-1.log` ends with `[done] build`. Tested executable SHA-256 `53364d5a985e146358d6893fa0956dcd0023156afe791540dd0091771f813721`.
- Ran the prescribed hidden-desktop boot with `--hidden --fullscreen --savedata work/runtime/codex-save-check --verbose 1`. `boot-fix-1.02-codex-1.log` shows `Window: borderless client=2560x1440 visible=0 noactivate=1 foreground=0`, `[boot] savedata: work/runtime/codex-save-check`, and the verbose-only `[cellGcmSys] BindTile(index=0)`. The run reached the 20-second cap after the quit request.
- Ran a second hidden-desktop boot with `--hidden --windowed --width 960 --height 540 --exit-after 12` and verbose set to 0. `boot-fix-1.02-codex-1-windowed.log` shows `Window: windowed client=960x540 visible=0 noactivate=1 foreground=0` and exited 0. The verbose-only tile and Z-cull messages were absent.
- Compiled and ran `save-root-check.cpp` with the port's Clang toolchain. The harness uses the production path functions with synthetic roots. `save-root-codex-1.log` reports `PASS: save mount and cellSaveData share the root; sibling remains on HDD0.` The game did not reach a save operation in either boot.



## 2. Portable defaults

- Changed `port/main.cpp` and `docs/CLI.md`. The default firmware root is `dev_flash` next to the executable. Explicit relative paths retain their meaning from the launch directory. The process then uses the executable folder for internal relative paths.
- Launched the executable with no flags or port environment variables and no adjacent game folder. `boot-fix-1.02-codex-2-missing.log` begins `Game files not found.` and gives the expected folder. `check-portable-codex-2-missing.log` records exit 1 and no new files.
- The initial no-flags boot created `NVIDIA Corporation/umdlogs` under the launch working directory. Repeated with the working-directory fix, copied base data, and the fixed-profile ELF. `check-portable-codex-2-full.log` records the executable hash `e260235f2dfa96cbd38684050b37dab9b30ff810c9b31d340959f2f25a9ee34f`, `PASS: boot dispatched from the default executable-relative layout.`, and no entries in the alternate working directory or the isolated AppData and temporary directories. The NVIDIA directory was created beside the executable. The run reached the 20-second cap.
- Ran `llvm-readobj --coff-imports` and inspected the source for registry write APIs. The executable imports no direct registry write API. Registry activity and writes through Windows known-folder APIs in system DLLs or drivers were outside this check.
- The locked pipeline reported `[skip] build: inputs and outputs unchanged` for `build-fix-1.02-codex-2-portable.log`. The preceding shared build already included the portability fix.

### Requests for Claude

- The hidden fullscreen run in `boot-fix-1.02-codex-1.log` contains `0x887A0005`. The hidden windowed run and the default windowed portability run have no matching line in their allotted time. I did not build a control with the window patch removed.



## 3. Peripheral import names

Added 13 names to `external/ps3recomp/tools/nid_database.py` and exported `patches/runtime/0007-peripheral-nid-names.patch`. The patch leaves the existing SPURS addition out.

| Library | NID | Export |
|---|---|---|
| `cellHttp` | `0x1395D8D1` | `cellHttpClientSetSslCallback` |
| `cellHttp` | `0x224E1610` | `cellHttpClientSetRecvTimeout` |
| `cellHttp` | `0x71714CDC` | `cellHttpClientSetSendTimeout` |
| `cellHttp` | `0xCAC9FC34` | `cellHttpClientSetUserAgent` |
| `cellHttp` | `0xD7471088` | `cellHttpClientSetConnTimeout` |
| `sceNp` | `0x45F8F3AA` | `sceNpCustomMenuRegisterActions` |
| `sceNp` | `0xF9732AC8` | `sceNpCustomMenuActionSetActivation` |
| `cellFont` | `0x40D40544` | `cellFontEndLibrary` |
| `cellFont` | `0x90B9465E` | `cellFontRenderSurfaceInit` |
| `cellFontFT` | `0x7A0A83C4` | `cellFontInitLibraryFreeTypeWithRevision` |
| `libgem` | `0x92CC4B34` | `cellGemGetImageState` |
| `cellCamera` | `0x0E63C444` | `cellCameraGetBufferInfoEx` |
| `sys_crashdump` | `0xB20F87B3` | `sys_crash_dump_set_user_log_area` |

Checked the [RPCS3 module declarations](https://github.com/RPCS3/rpcs3/tree/0ebb63697666a54b44a4de69ef222c4ecee0001a/rpcs3/Emu/Cell/Modules), then used the project's `compute_nid` and `NIDDatabase.load_builtins` against `analysis/fix-1.02/EBOOT.imports.json`. `work/runtime/logs/nid-verify-codex-3.log` reports `PASS: 13 hashes, EBOOT library names, and built-in lookups agree.` The patch passed reverse application checking. Runtime dispatch is part of item 4.



## 4. Peripheral handlers

Registered the handlers in `port/stubs.cpp`. The changes cover `cellHttp`, `sceNp`, `cellCamera`, `cellGem`, `cellFont`, `cellFontFT`, and `sys_crashdump` in the ps3recomp libraries. The port selects offline HTTP and disables the virtual camera in `port/main.cpp`.

The handlers validate HTTP client settings, return offline NP and device statuses, write camera and Move output records, store crash log registrations, and use local TTF files to render glyphs into guest surfaces. The first hidden boot reached nine of the 13 named imports and exposed a later Move import, `0xA03EF587`. Confirmed it as `cellGemPrepareCamera` with the project hash and import table. The same run showed that the game requests font set `0x209`, so the font handler now maps it to the Latin face.

| Check | Evidence |
|---|---|
| Runtime patches | Updated `0007-peripheral-nid-names.patch` and added `0009-peripheral-handlers.patch`. Both passed reverse apply checking. |
| Locked Git Bash build | `build-fix-1.02-codex-4b.log` ends with `[done] build`. |
| Focused Clang harness | `peripheral-check-codex-4c.log` has `PASS: disconnected camera and Move statuses and guest outputs.` and `PASS: font library lifecycle, PPC float arguments, surface ABI, and nonzero glyph pixels.` It exercised all 14 registrations with guest-layout buffers and a local test TTF. |
| Hidden desktop boots | `boot-fix-1.02-codex-4b.log` and `boot-fix-1.02-codex-4c.log` had zero unresolved imports. Both aborted before the later Move and font calls. |

The actual game font pixels and the later call sites still need a run that advances past the abort.

### Requests for Claude

- Check the repeatable guest abort through `0x0077FFCC` and `0x007F266C` in both reruns.
- The NID database scans C filenames and can replace the curated `libgem` label with `cellGem`. The ownership rule limits my change to names. Keep an existing entry when this scan finds the same NID.

  ```diff
  -                    self.add(module, m.group(1))
  +                    name = m.group(1)
  +                    if compute_nid(name) not in self._by_nid:
  +                        self.add(module, name)
  ```



## 5. Single executable design

The Windows executable starts the fixed 1.02 profile when it finds the startup files. If either file is missing, display the expected locations and return exit code 1 before creating runtime folders or allocating guest memory. Keep the message open when Explorer opens a new console for the process.

| Part | Rule |
|---|---|
| Runtime folder | Use the executable folder by default. Override it with `--build-dir`. |
| Discovery | Look for `PARAM.SFO` and `USRDIR/EBOOT.elf` in the `game` subfolder, then in the runtime folder itself. |
| Overrides | Honor explicit game and ELF paths, the existing positional ELF form, and the `PS3_GAME` layout under an explicit game root. |
| Firmware | Provide `--dev-flash` for optional firmware. |
| Distribution | The Windows executable contains the lifted code and links to Windows system DLLs. The tarball gate applies if a release ships an AppImage. |


