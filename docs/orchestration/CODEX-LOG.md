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



### Item 5 results

Changed `port/main.cpp`, `port/cli_options.h`, `port/cli_options.cpp`, and `docs/CLI.md`. Setup and guest dispatch use one executable.

| Check | Evidence |
|---|---|
| Locked build | `build-fix-1.02-codex-5.log` ends with `[done] build`. |
| Missing files | `first-run-codex-5.log` records exit 1 for the exe-only and missing-SFO cases, with no runtime folders created. |
| Default launch | The same log records dispatch with no flags for both adjacent layouts, an empty alternate launch directory, and empty isolated AppData and temp directories. Both guest runs hit the 20-second cap. |
| Overrides | A relative `--build-dir` and an explicit `PS3_GAME` layout dispatched the guest. The HDD0 flag took precedence over the environment variable. |
| Distribution | `llvm-readobj --coff-imports` on the tested executable lists Windows system DLLs. No AppImage exists in the build tree. |

The tests used the hidden desktop. An interactive Explorer launch and system DLL or driver registry writes remain unverified.



### Integrated verification

| Check | Evidence |
|---|---|
| Final build | `build-fix-1.02-codex-final.log` reports `[done] build`. Executable SHA-256 `bdb323670c5cb0dc9f44191bb03ec1a9e7dafd5895be231de6c37d307b99f53c`. |
| Peripheral calls | Two runs on the first-run test executable and a run on the final rebuild exited 0. `peripheral-boots-codex-final.log` reports `Unresolved NID lines: 0`, a hidden nonactivating window, and recorded calls to the camera, Move, font library, and font surface handlers. |
| Font errors and pixels | Updated the font error constants in `cellFont.h`, `cellFont.c`, and `cellFontFT.c` and refreshed patch `0009`. The final focused test verifies missing-file code `0x80540009` and nonzero glyph pixels with a local test font. |
| Static import audit | `peripheral-registration-audit-codex-5.log` shows 22 imports absent from the generated and port registration lists. The bounded boots produced no calls that went unresolved. |

The real firmware font was absent from the test layout, so title text remains unverified. The account lacks kernel trace permissions for registry and file activity by drivers or system DLLs. The host tests verified executable-relative paths and checked the alternate launch directory, isolated AppData directories, and direct registry imports.



### Item 4 follow-up on import coverage

The previous audit missed the context registration for `sceNpScoreGetRankingByRange`. Added handlers for the other 21 imports and verified the names of all 22 against the EBOOT table. Changes are in `port/stubs.cpp`, `cellHttp.*`, `sceNp.*`, `sceNpScore.c`, `cellGem.*`, and the NID database. Re-exported patches `0007` and `0009`.

| Check | Evidence |
|---|---|
| Registration | `peripheral-registration-audit-codex-coverage.log` reports `PASS: all 110 imported entries in the seven owned modules have an HLE registration.` |
| Handler contracts | `peripheral-check-codex-coverage.log` records passing HTTP transaction and cookie tests, NP offline status and score ABI checks, and Move output and error checks. Failed NP lookups preserve their output buffers. |
| Build and boot | The locked Git Bash pipeline ends with `[done] build`. `boot-fix-1.02-codex-coverage.log` exited 0. Its audit reports `All unresolved imports: []`. |

### Item 2 follow-up on Windows tracing

`logman start` for the Windows kernel registry provider returned `Access is denied` with code `-2147024891`. Driver and system DLL registry writes remain unverified. The installed RPCS3 tree has no local firmware font for the US font set, so verification of actual title text is still open.


### Item 2 follow-up on temporary files

The Windows CRT probe found a portability defect in the SDATA scratch path.

| Probe | Result |
|---|---|
| `portable-crt-codex.log` | `msvcrt tmpfile parent outside runtime: True`, with both `TMP` and `TEMP` under the runtime folder. |
| `portable-crt-proposal-codex.log` | An exclusive temporary file stayed in the specified directory and disappeared on close. |

### Requests for Claude

Move the Windows scratch stream in `cellFsSdataOpen` to `PS3_HDD1_ROOT`, which defaults to `hdd1` beside the executable. Keep the existing I/O failure path when the scratch file cannot be created.
```diff
--- a/runtime/ppu/ppu_fs.cpp
+++ b/runtime/ppu/ppu_fs.cpp
@@ Insert before cellFsSdataOpen @@
+#ifdef _WIN32
+static FILE* open_sdata_scratch()
+{
+    const char* root = ps3_env_once("PS3_HDD1_ROOT");
+    if (!root || !*root) return tmpfile();
+
+    static std::atomic<unsigned> next_file{0};
+    for (unsigned attempt = 0; attempt < 64; ++attempt) {
+        char path[1024];
+        const int length = snprintf(path, sizeof path, "%s/.sdata-%lu-%u.tmp",
+                                    root, (unsigned long)GetCurrentProcessId(),
+                                    next_file.fetch_add(1, std::memory_order_relaxed));
+        if (length < 0 || (size_t)length >= sizeof path) return nullptr;
+        const int fd = _open(path, _O_RDWR | _O_CREAT | _O_EXCL | _O_BINARY | _O_TEMPORARY,
+                             _S_IREAD | _S_IWRITE);
+        if (fd < 0) {
+            if (errno == EEXIST) continue;
+            return nullptr;
+        }
+        FILE* stream = _fdopen(fd, "w+b");
+        if (!stream) _close(fd);
+        return stream;
+    }
+    return nullptr;
+}
+#endif
@@ Inside the NPD branch of cellFsSdataOpen @@
-        FILE* tf = tmpfile();
+#ifdef _WIN32
+        FILE* tf = open_sdata_scratch();
+#else
+        FILE* tf = tmpfile();
+#endif
```




### Item 5 follow-up on startup validation

The Windows launcher checks the selected ELF against the fixed 1.02 size and SHA-256 before it creates runtime directories. It holds a read handle through the loader call. The launcher also checks the title ID from `PARAM.SFO`. Changes are in `port/main.cpp` and `docs/CLI.md`.

| Check | Evidence |
|---|---|
| Input pin | `profile-pin-codex.log` confirms that the compiled title ID, ELF size, and digest match `config/target.json` and the local file. |
| Locked build | `build-fix-1.02-codex-profile.log` reports `[done] build`. Tested executable SHA-256 is `11307e9341e52e609dffbbc48c2477eac4dd362797387b1e95c54e42e14e9d57`. |
| First run | `first-run-codex-profile.log` verifies exit 1 for a same-size ELF with a different digest and for a mismatched title ID. Neither case created runtime directories. Both supported default layouts and the explicit build-folder layout dispatched. |
| Full data | `boot-fix-1.02-codex-profile-full.log` exited 0 on the hidden desktop. `profile-boot-codex.log` confirms guest dispatch and zero unresolved import lines. |

The SDATA temporary-file fix still needs to land in the shared runtime. System registry tracing remains unavailable to this account, and the installed firmware directory still lacks the US font.

### Item 1 follow-up on patch replay

A replay against pinned ps3recomp commit `ae92407bb1d899e3d32143e360fe6e6d4d8fa1b5` failed at patch `0006`. Patch `0004` already includes its save-root hunk. The test used `git read-tree HEAD` and `git apply --cached` with a scratch index and object store.

`patch-replay-proposed-codex.log` records a successful replay of all 13 patches with the duplicate removed from a scratch copy of `0004`. The resulting source matches the worktree for the filesystem, D3D12, NID database, and peripheral files checked. The shared patch still needs the change below.

### Requests for Claude

Keep the save-root change in `0006` and trim the duplicate from `0004`. The following patch changes only the protected patch file, so it needs your review and application.


```diff
--- a/patches/runtime/0004-ppufs-hdd-title-base-fallback.patch
+++ b/patches/runtime/0004-ppufs-hdd-title-base-fallback.patch
@@ -1,8 +1,7 @@
 diff --git a/runtime/ppu/ppu_fs.cpp b/runtime/ppu/ppu_fs.cpp
-index 37e3745..6426da8 100644
 --- a/runtime/ppu/ppu_fs.cpp
 +++ b/runtime/ppu/ppu_fs.cpp
-@@ -134,12 +134,25 @@ static void guest_strcpy(char* dst, uint32_t gaddr, size_t cap)
+@@ -134,12 +134,13 @@ static void guest_strcpy(char* dst, uint32_t gaddr, size_t cap)
  /* Defined in runtime/syscalls/sys_fs.c -- shared by all three path
   * translators. (extern "C" is ill-formed at block scope.) */
  extern "C" void ps3_vfs_ps3game_fallback(char* path, size_t cap);
@@ -13,22 +12,10 @@
  static void host_path(char* out, size_t cap, const char* guest)
  {
      const char* rel = guest;
-+    /* Match the directory used by cellSaveData for the local PS3 user. */
-+    static const char save_mount[] = "/dev_hdd0/home/00000001/savedata";
-+    const size_t save_mount_len = sizeof(save_mount) - 1;
-+    if (strncmp(guest, save_mount, save_mount_len) == 0
-+        && (guest[save_mount_len] == '/' || guest[save_mount_len] == '\0')) {
-+        const char* save_root = ps3_env_once("PS3_SAVEDATA_ROOT");
-+        if (save_root && *save_root) {
-+            snprintf(out, cap, "%s%s", save_root, guest);
-+            for (char* p = out; *p; p++) if (*p == '\\') *p = '/';
-+            return;
-+        }
-+    }
      /* /dev_hdd0 overlays the installed game-update dir (a disc title patched to
       * e.g. v1.30 runs the update's EBOOT and reads its patchN.farc from
       * /dev_hdd0/game/<title>/), mirroring the PS3/RPCS3 layout: base data on
-@@ -150,6 +163,30 @@ static void host_path(char* out, size_t cap, const char* guest)
+@@ -150,6 +151,30 @@ static void host_path(char* out, size_t cap, const char* guest)
      if (hdd0_root && strncmp(guest, "/dev_hdd0/", 10) == 0) {
          snprintf(out, cap, "%s/%s", hdd0_root, guest + 10);
          for (char* p = out; *p; p++) if (*p == '\\') *p = '/';
```



### Item 5 follow-up on log output

Changed `port/main.cpp` so `--log` opens one file and duplicates the output descriptor for standard error. Updated `docs/CLI.md`.

| Check | Evidence |
|---|---|
| Same-CRT probe | `log-sink-crt-codex.log` reports that separate descriptors lost a record and the shared descriptor preserved all three records. |
| Locked build | `build-fix-1.02-codex-log-sink.log` reports `[done] build`. |
| Full-data hidden boot | The rebuilt executable exited 0 with zero unresolved NIDs. `log-sink-streams-codex.log` confirms the combined file retained both the D3D12 stderr marker and guest-dispatch stdout marker. The former was missing in the earlier combined boot log. |

The shared tree still needs the patch-stack deduplication and SDATA scratch fix. Registry tracing and title text with the firmware font remain unverified.

### Release audit at the ownership boundary

The Windows build, first-run checks, and bounded hidden boots passed, with registrations for all 110 imports in the seven owned modules.

| Gate still open | Evidence |
|---|---|
| Clean patch replay | Patch `0004` still duplicates the save-root hunk in `0006`. Removing the duplicate in a scratch copy allowed all 13 patches to apply. |
| Portable SDATA writes | `cellFsSdataOpen` still calls `tmpfile()`. The CRT probe reproduced a scratch file outside the runtime folder. |
| Windows registry and driver writes | Windows denied the registry trace. The current account still lacks trace privileges. |
| Actual title text | The local runtime and RPCS3 trees lack the firmware font. A focused test rendered glyphs with a test font. |

The first two fixes are filed under Requests for Claude.

### Items 1 and 2 follow-up on patch replay and SDATA

With the owner's approval, removed the duplicate save-root hunk from patch `0004`. Patch `0006` retains the mapping. On Windows, `cellFsSdataOpen` now uses an exclusive, delete-on-close file under the configured HDD1 root. Patch `0011` contains the runtime change.

| Check | Evidence |
|---|---|
| Clean runtime patch replay | `patch-replay-live-codex.log` records 14 patches applied in order against `ae92407bb1d899e3d32143e360fe6e6d4d8fa1b5`. All ten checked source files matched the worktree. |
| Live scratch helper | `sdata-helper-codex.log` records placement under HDD1, collision handling, binary readback, and removal on close. The harness compiled the helper directly from `ppu_fs.cpp`. |
| Locked build | `build-fix-1.02-codex-sdata-portable.log` ends with `[done] build` and the pipeline exited 0. |
| Hidden boot | `boot-fix-1.02-codex-sdata-portable.log` reached guest dispatch and exited 0 with no unresolved NIDs. It used the subsequent shared build, SHA-256 starting `904c42a5`. |

The bounded boot did not show an encrypted SDATA open. The focused check covers the stream used by that branch.

### Item 3 follow-up on keyboard imports

Added both names to `tools/nid_database.py` and refreshed patch `0007`. `nid_database.py --compute` returned `0x7C95FEB8` for `cellOskDialogExtInputDeviceLock` and `0x09565B21` for `cellOskDialogExtInputDeviceUnlock`. `--lookup` returned both under `cellOskExtUtility`. [PS3 Developer Wiki export table](https://www.psdevwiki.com/ps3/Ps3.xml)

### Requests for Claude

Implement and verify the keyboard input lock and unlock handlers in the OSK runtime. Both unresolved calls occur after New Game in the integration run. Rebuild the HLE registration table after adding the handlers.

### Item 2 follow-up on Windows portability

A no-flags launch with the normal Windows environment reached guest dispatch on the hidden desktop, used the executable-relative game, HDD0, HDD1, and save roots, and left the alternate working directory empty. The harness requested termination at 17 seconds.

Collected kernel file and registry events with `logman`. Filtering on the game PID with `Get-WinEvent` produced `etw-portable-events-codex.log` and `etw-portable-writes-codex.log`.

| Release check | Result |
|---|---|
| AppData | The trace links 798 successful write operations to AppData. The process opened paths under the Direct3D and NVIDIA shader caches. |
| Registry | Two `SetValueKey` events succeeded. A read-only lookup found the values for `conhost.exe` and `HotShotsGolfRecomp.exe` under Windows Background Activity Moderator. |
| Game-owned paths | The launcher opened the expected executable-relative roots. Three successful file writes mapped to the distribution folder. |

The portability gate fails. Some file paths could not be resolved. The CLI reference now documents the external writes, and Microsoft limits implicit Direct3D cache controls to developer mode. [Direct3D ShaderCacheControl](https://learn.microsoft.com/en-us/windows/win32/api/d3d12/nf-d3d12-id3d12device9-shadercachecontrol)

### Item 4 follow-up on the US firmware font

An isolated RPCS3 copy extracted the font from Sony's PS3 4.93 update before reporting a teardown error. Verified its checksum and staged the TTF in the ignored `work/runtime/firmware-codex/dev_flash` folder. The harness drew glyphs with that face. `peripheral-real-font-codex.log` reports nonzero glyph pixels. [Sony PS3 system software](https://www.playstation.com/en-us/support/hardware/ps3/system-software/)

`boot-fix-1.02-codex-firmware.log` shows two FreeType library initializations, zero font-open failures, and zero unresolved NIDs. It exited 0. Title-screen text still needs verification.

### Requests for Claude

- Check the rendered text on the next title-capable hidden run with `--dev-flash work/runtime/firmware-codex/dev_flash`.
- Investigate the graphics cache writes in the video backend and decide how the release gate should handle Windows Background Activity Moderator records.

The latest clean replay in `patch-replay-osk-verified-codex.log` applies all 15 patches and matches the ten checked worktree files. Patch `0007` carries the new keyboard names, and patch `0002` carries the separate SPURS name.

### Item 4 follow-up on HLE registration during builds

The latest job-15 boot calls both unresolved keyboard imports after opening the title asset. A fresh run of `gen_hle_nids.py --all` matches all 1,296 registrations in the lift table and includes neither keyboard handler. The runtime definitions are still needed.

### Requests for Claude

Use the existing CMake generator by default so builds pick up new handlers as soon as their source files change. Keep the curated table as an explicit option and exclude it from the general lift source list to avoid linking both definitions of `ppu_hle_register_all`.

`hle-cmake-proposal-codex.log` records four passes in an isolated CMake/Ninja fixture that used the current generator. It tested a stale lift table, module edits, module addition and removal, and the curated override. `git apply --check` passed. The full port build still needs verification after application.

```diff
--- a/port/CMakeLists.txt
+++ b/port/CMakeLists.txt
@@ -62,6 +62,7 @@
     "${RECOMP_DIR}/*.c"
     "${RECOMP_DIR}/*.cpp"
 )
+list(REMOVE_ITEM RECOMP_SOURCES "${RECOMP_DIR}/ppu_hle_nids.cpp")
 if(NOT RECOMP_SOURCES)
     message(FATAL_ERROR
         "${RECOMP_DIR} has a ppu_recomp.h but no .c or .cpp beside it. The "
@@ -89,7 +90,11 @@
 # it. A port may keep a hand-curated one beside its lift; otherwise generate
 # the canonical every-module table, which is what the toolkit's own boot
 # harness uses.
-if(EXISTS "${RECOMP_DIR}/ppu_hle_nids.cpp")
+option(USE_CURATED_HLE_NID_TABLE "Use the HLE table in the lift directory" OFF)
+if(USE_CURATED_HLE_NID_TABLE)
+    if(NOT EXISTS "${RECOMP_DIR}/ppu_hle_nids.cpp")
+        message(FATAL_ERROR "USE_CURATED_HLE_NID_TABLE requires ppu_hle_nids.cpp in RECOMP_DIR")
+    endif()
     set(HLE_NID_TABLE "${RECOMP_DIR}/ppu_hle_nids.cpp")
     message(STATUS "HLE NID table:   ${HLE_NID_TABLE}")
 else()
--- a/pipeline.toml
+++ b/pipeline.toml
@@ -48,13 +48,11 @@
   "work/extracted/fix-1.02/USRDIR/EBOOT.elf",
   "analysis/fix-1.02/EBOOT.functions.json",
   "analysis/fix-1.02/EBOOT.imports.json",
-  "external/ps3recomp/tools/ppu_lifter.py",
-  "external/ps3recomp/tools/gen_hle_nids.py"
+  "external/ps3recomp/tools/ppu_lifter.py"
 ]
 outputs = ["generated/fix-1.02/recompiled"]
 commands = [
-  ["${python}", "${ps3recomp}/tools/ppu_lifter.py", "${eboot}", "--functions", "analysis/fix-1.02/EBOOT.functions.json", "--hle-stubs", "analysis/fix-1.02/EBOOT.imports.json", "--code-end", "0xd17018", "--chunks", "64", "--output", "generated/fix-1.02/recompiled"],
-  ["${python}", "${ps3recomp}/tools/gen_hle_nids.py", "--all", "--out", "generated/fix-1.02/recompiled/ppu_hle_nids.cpp"]
+  ["${python}", "${ps3recomp}/tools/ppu_lifter.py", "${eboot}", "--functions", "analysis/fix-1.02/EBOOT.functions.json", "--hle-stubs", "analysis/fix-1.02/EBOOT.imports.json", "--code-end", "0xd17018", "--chunks", "64", "--output", "generated/fix-1.02/recompiled"]
 ]
 
 [[stages]]
```

### Item 4 follow-up on font surface clipping

Changed `cellFont.c` and `cellFont.h` so glyph writes and transfer dimensions respect the guest surface's scissor rectangle. Refreshed the font hunks in patch `0009`.

| Check | Evidence |
|---|---|
| Guest ABI check with the PS3 font | `font-scissor-red-codex.log` reproduces writes outside a one-pixel scissor. `font-scissor-green-codex.log` verifies the exact pixel and transfer dimensions, an empty scissor, and a full-surface draw. |
| Locked Git Bash build | `build-fix-1.02-codex-font-scissor.log` reports `[done] build`. |
| Hidden boot with firmware | `boot-fix-1.02-codex-font-scissor.log` exited 0 with two FreeType initializations, no font-open failures, and no unresolved NIDs within the cap. The milestone log records renderer binding. The run ended before glyph rendering. |
| Runtime patch replay | `patch-replay-font-scissor-owned-codex.log` applied all 16 patches and matched seven selected worktree files, including the font and OSK sources. The rendering worker's pending video edits differ from the exported stack. |

### Requests for Claude

The two handlers in patch `0025` write a lock flag that no input path reads. Add a check that lock blocks an external keyboard event and unlock lets it through. The handlers also need the registration build change before verifying New Game dispatch.

### Items 2 and 4 follow-up on the remaining release gates

`osk-registration-codex.log` shows that `gen_hle_nids.py --all` emits both keyboard registrations from patch `0025`, while the current build's table has zero. Claude accepted the proposed build change. New Game dispatch and functional input locking still need verification.

The read-only registry check in `bam-control-verified-codex.log` found no Background Activity Moderator value for a 2.5-second control that imports only `Sleep` and `ExitProcess`. The game trace records two successful registry value writes and 798 successful AppData file writes, so the strict portability gate requires a release decision on Windows and driver activity. Title-screen text still needs a longer hidden run.

### Item 2 follow-up on Windows cache paths

Changed `port/main.cpp` so the Windows launcher uses a process-local profile and temp directory under `<build dir>/cache/profile`. It sets those paths after validating the game files. The folder can be removed with the rest of the build.

| Check | Evidence |
|---|---|
| Controlled launch | `etw-profile-writes-codex.log` associated 802 Direct3D writes and one NVIDIA cache write with paths inside the staged distribution after setting the launch environment. |
| Default launch after the change | `etw-profile-default-writes-codex.log` recorded 757 successful Direct3D cache writes inside the staged distribution, zero mapped writes to external AppData, and an empty launch directory. The launcher used the normal Windows environment and no flags. |
| Windows and driver activity | The default trace recorded one successful registry value write for `conhost.exe`. It also associates successful writes with NVIDIA files under `ProgramData`. Several file events could not be mapped to a path. |
| Build and setup | `build-fix-1.02-codex-profile-cache.log` ends with `[done] build`. `first-run-profile-cache-codex.log` shows exit 1 for missing game data and confirms the staged folder contains only the executable. |

The strict zero-write gate remains open. `docs/CLI.md` documents the new cache location and the Windows and driver records observed outside it.

### Item 4 follow-up on the shared HLE build

Claude applied the CMake generator change in `5365ae6`. The locked build prints `HLE NID table: generated (every module)` and its generated table registers both keyboard calls. `patch-replay-profile-codex.log` applies all 17 runtime patches, including `0024` and `0025`, and matches seven checked source files.

The firmware-enabled title run reports no font-open failures or unresolved NIDs. The title uses texture art. The focused glyph tests verify the font handler, and a rendered firmware glyph in the game still needs verification. The OSK lock flag still has no input path reading it.

### Requests for Claude

- Record milestones on the next firmware-backed run that exercises keyboard or font calls. Check both keyboard NIDs and a frame containing `cellFontRenderCharGlyphImage` output.

### Item 2 follow-up on the build directory override

`check-cache-build-dir-verified-codex.log` confirms that a hidden launch from a separate working directory with a relative `--build-dir` used the selected folder for HDD0, HDD1, saves, and six nonempty Direct3D cache files. The boot exited 0. The launch directory stayed empty, and the executable directory contained only the executable.

### Items 3 and 4 follow-up on the remaining peripheral imports

`peripheral-coverage-current-codex.log` confirms source-level registrations for all 110 imports in the seven assigned libraries. The audit checked the generated table, the port overrides, and the NP score context registrations. It found these additional imports without a registration in the checked paths.

| Library | NID | Export |
|---|---|---|
| `cellOskExtUtility` | `0x75370397` | `cellOskDialogExtSetInitialScale` |
| `cellOskExtUtility` | `0xE800F586` | `cellOskDialogExtRegisterForceFinishCallback` |
| `cellSail` | `0x1872331B` | `cellSailGraphicsAdapterPtsToTimePosition` |
| `cellSail` | `0x3DD9639A` | `cellSailAuReceiverInitialize` |
| `cellSail` | `0x4AE979DF` | `cellSailSoundAdapterPtsToTimePosition` |
| `cellSail` | `0xED58E3EC` | `cellSailAuReceiverFinalize` |
| `cellSail` | `0xF25F197D` | `cellSailSoundAdapterGetFormat` |
| `cellSail` | `0xF5747E1F` | `cellSailPlayerSetAuReceiver` |
| `cellSail` | `0xFFD58AA4` | `cellSailGraphicsAdapterGetFormat` |

Added the two keyboard names in `tools/nid_database.py` and refreshed patch `0007`. `osk-additional-nid-names-codex.log` confirms both hashes and lookups. All 17 patches replayed in `patch-replay-osk-names-codex.log`. The database already has the seven media names. A search of the available boot logs found no unresolved call to these nine NIDs. [RPCS3 keyboard exports](https://github.com/RPCS3/rpcs3/blob/0ebb63697666a54b44a4de69ef222c4ecee0001a/rpcs3/Emu/Cell/Modules/cellOskDialog.cpp) · [RPCS3 media exports](https://github.com/RPCS3/rpcs3/blob/0ebb63697666a54b44a4de69ef222c4ecee0001a/rpcs3/Emu/Cell/Modules/cellSail.cpp)

`font-and-keyboard-dispatch-codex.log` records `cellFontOpenFontset`, `cellFontRenderCharGlyphImage`, and both registered keyboard calls reaching dispatch in `milestone-flips.log`. It reports zero font-open failures and zero unresolved calls. The focused firmware fixture verifies pixel writes and clipping. Live glyph pixels and functional locking remain open.

### Requests for Claude

- Keep the two keyboard and seven media registration gaps with their module owners. Use the listed exports if a later game path reaches them.

### Item 4 follow-up on live font pixel verification

Added `font:glyph-pixels-written` to `cellFont.c` and refreshed patch `0009`. The event records a glyph only after a nonzero alpha value is written to the guest surface.

| Check | Evidence |
|---|---|
| Focused check with the firmware font | `font-glyph-milestone-red-codex.log` records zero events before the change. `font-glyph-milestone-green-codex.log` records exactly two events after real writes and zero for the empty scissor. |
| Locked Git Bash build and patch replay | `build-fix-1.02-codex-glyph-milestone.log` ends with `[done] build`. `patch-replay-glyph-milestone-codex.log` applies all 17 patches and matches the checked font, NID database, and filesystem sources. |
| Bounded hidden boot | `boot-fix-1.02-codex-glyph-milestone.log` exited 0 with the staged firmware and zero unresolved calls. `milestones-fix-1.02-codex-glyph-milestone.tsv` records `cellFontOpenFontset`. The run ended before the first glyph call. |

### Requests for Claude

- Keep `PS3_MILESTONE_OUT` enabled on the next firmware-backed hidden run of build `4adc6547`. Check the recorded events after the intro.

### Item 2 follow-up on ProgramData

`knownfolder-programdata-codex.log` shows that `SHGetKnownFolderPath` resolves `ProgramData` outside the redirected profile even when the process has its own `PROGRAMDATA` and `ALLUSERSPROFILE` values. Tested both inherited values and values set after process startup. The check covers Windows shell path resolution.

The latest default-launch trace still records a successful registry value write for `conhost.exe` and file activity associated with NVIDIA paths under `ProgramData`. The strict gate remains unmet. The release decision is whether those Windows and driver records are permitted.
