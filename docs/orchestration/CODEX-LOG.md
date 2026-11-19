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

### Runtime patch replay through 0032

The numbered replay against the pinned ps3recomp revision stops at `0026-rsx-menu-scene.patch` in `patch-replay-0032-codex.log`. Patches `0026` and `0027` mix CRLF hunk lines with LF headers.

The same `git apply --cached` replay with LF copies of those two patches applies all 24 runtime patches. `patch-replay-0032-lf-codex.log` records the pass and matches for `ppu_fs.cpp`, `nid_database.py`, `cellFont.c`, and `cellPad.c`.

### Requests for Claude

- Re-export the two rendering diffs with LF and run the numbered stack against the pinned revision.

### Item 2 release decision on system records

The release owner granted permission after being asked whether the Windows console registry write and NVIDIA activity under `ProgramData` count against the portability gate. The allowance covers those system records.

The no-flags trace in `etw-profile-default-writes-codex.log` found 757 Direct3D cache writes under the distribution and zero mapped writes to external AppData. The launch directory was empty. Some file events had no resolved path.

### Requests for Claude

- Record the owner's allowance in the release gate in `STATE.md`. Keep the port's default storage under the executable folder.

### Item 1 follow-up on runtime tuning switches

Wired `--rsx-shader-cache`, `--rsx-disp-tex`, `--jc-parallel`, and `--pad-script-hold` in `port/cli_options.h`, `port/cli_options.cpp`, and `port/main.cpp` and documented the defaults in `docs/CLI.md`.

| Check | Evidence |
|---|---|
| CLI fixture | `tuning-cli-red-codex.log` reports `unknown option --rsx-shader-cache`. After the change, `tuning-cli-green-codex.log` passes range checks, inherited settings, CLI precedence, and cache defaults. |
| Locked Git Bash pipeline | The shared optimized build in `build-fix-1.02-lie8.log` compiled both changed sources and reports `[done] build`. The follow-up in `build-fix-1.02-codex-tuning-cli.log` reports `[skip] build: inputs and outputs unchanged`. |
| Hidden runs | `tuning-cli-integration-codex.log` records three successful boots on build `f5b5cef6`, three DXBC files each at the explicit and default paths, zero with caching off, and exit 1 for a file passed as a cache directory. |
| SPURS | `job chain lanes: 1 (JC_PARALLEL=1)` with an inherited value of 7 |

The display and pad settings passed the environment fixture. Their effects in a round remain unverified.

### Item 5 startup on the optimized build

Build `7354b3ce` exited 1 when launched with no flags in an exe-only folder. `boot-fix-1.02-codex-tuning-missing.log` prints `Game files not found.` and lists the two expected files. `tuning-missing-codex.log` confirms the distribution still contains only the executable and the launch and isolated profile folders are empty.

The PE import check with `llvm-readobj --coff-imports` lists only Windows DLLs. The build tree contains no AppImage.

### Item 4 font scale and surface origin

`optimized-font-scale-probe-codex.log` records the game setting a 54-pixel font on both axes, then calling render-scale setup with two zeroes. Zero erased the configured size. The glyph probe also records draws at the surface origin.

Changed `cellFont.c` to preserve a configured dimension when render setup gets zero and account for the line baseline when writing the glyph. Updated patch `0009`. The firmware fixtures fail before the changes in `font-default-scale-red-codex.log` and `font-surface-origin-red-codex.log` and pass afterward, including one-pixel and empty scissor checks. [RPCS3 cellFont reference](https://github.com/RPCS3/rpcs3/blob/0ebb63697666a54b44a4de69ef222c4ecee0001a/rpcs3/Emu/Cell/Modules/cellFont.cpp)

`build-fix-1.02-codex-firmware-glyph-compat.log` reports `[done] build`. The three capped hidden boots on `b1ab0803` reached the glyph handler with no unresolved NIDs or null calls. The live pixel marker is still absent.

`patch-replay-font-compat-codex.log` checks 26 on-disk runtime patches through `0035` using scratch LF copies of `0026` and `0027`. The replayed font, filesystem, and NID database match the checked sources.

### Item 4 live firmware glyph pixels verified

The game supplies a null pixel pointer and a 64 KiB renderer config. The fixture reproduced `CELL_FONT_ERROR_INVALID_PARAMETER`.

Changed `port/stubs.cpp` to pass the renderer config and updated `cellFont.c`, `cellFont.h`, and patch `0009`. Renderer storage follows the configured limit and is released when the renderer closes. Both sizes are 64 KiB here.

| Check | Evidence |
|---|---|
| Renderer fixture | `font-renderer-red-codex.log` reproduces `80540002`. `font-renderer-green-codex.log` verifies real pixels, transfer dimensions, and release of the allocated buffer. |
| Locked build and hidden boot | `build-fix-1.02-codex-firmware-renderer-buffer.log` reports `[done] build`. Build `b5082538` exited 0 in the 18-second Ghost run with zero unresolved NIDs, null calls, or unresolved indirect calls. |
| Live transfer | `milestones-fix-1.02-codex-firmware-renderer-buffer-1.tsv` records `185 font:glyph-pixels-written` and a count of 10 to 99. The follow-up `optimized-font-buffer-probe-codex.log` records success, a guest image address, and a pitch of 72 bytes from a null-surface request. |
| Runtime patches | `patch-replay-font-renderer-codex.log` applies all 27 on-disk patches using scratch LF copies of `0026` and `0027`. It matches both font sources, the font header, the NID database, and the save mapping. |

The trace verifies guest-surface writes. A frame check and the remaining keyboard and media paths still need coverage.

### Item 2 follow-up on write attribution

The ETW range check in `default-etw-boot-ranges-codex.log` matches 1,040 previously unattributed writes to the captured boot log. Their byte ranges cover the 221,015-byte file without gaps or overlaps. Another 48 completions carry the paging I/O flag and span two unresolved file objects. The ETL filename lookup reached its 35-second limit.

### Requests for Claude

Apply this update for the owner's portability allowance. The diff passed `git apply --check` against the current `STATE.md`.
```diff
--- a/docs/orchestration/STATE.md
+++ b/docs/orchestration/STATE.md
@@ -90,7 +90,7 @@
 - Labels follow `docs/recomp-process.md` section 6. Current label: Lifted, boot in progress. Renders, Menu and Playable are not claimed.
 - Release gates added by the project owner on 2026-11-17 (apply before any public build):
   1. One executable. No separate builder executable; the launcher detects an existing build and starts the game, or offers a play button in the same binary.
-  2. Portable by default. All files stay in the executable's folder. Deleting the folder removes the game.
+  2. Portable by default. The port stores its files in the executable's folder. Deleting the folder removes the game. The release owner permits the observed Windows console registry record and NVIDIA driver activity under ProgramData.
   3. A plain tarball ships next to any AppImage.
   4. A CLI flag for everything: fullscreen, ROM or ELF path, build folder, VFS, HDD and save roots.
 - Release gate status today: the executable has no DLL dependencies beyond Windows system libraries. It takes one positional ELF path and reads `PS3_VFS_ROOT`, `PS3_HDD0_ROOT`, `PS3_HDD1_ROOT`, `PS3_SAVEDATA_ROOT` and `PS3_TITLE` from the environment. No CLI flags exist yet, and portable defaults are not verified.
```

### Item 4 visual check within the hidden-run cap

| Run | Evidence |
|---|---|
| `visual-font-02` | `RSX_CAP=1:1` and `RSX_CAP_SECS=15` captured a presented frame with readable autosave text on build `9c975851`. The frame is at `work/runtime/visual-font-codex-02/frame_00/backbuffer.bmp`. |
| `visual-font-03` | With an isolated save root and scripted Cross presses, build `6a13f004` reached the title and presented the captured frame at second 16. |

Both boots exited 0 and logged `font:glyph-pixels-written`. A frame that shows the firmware-rendered menu text is still pending.

### Requests for Claude

Save the first presented menu frame and its matching milestone log during the longer play path.

### Item 2 native ETW name lookup

Ran the scratch `codex_etw_native_run.py` reader on the original no-flags trace. `default-etw-native-lookup-codex.log` reports `ProcessTrace status 0, kernel-file events 4027679`. The lookup resolved the redirected boot log and a known distribution file by name.

The two paging objects had 42 and 6 game write requests and zero matching filename records. The archived capture cannot establish where those 48 writes landed.

### Item 2 follow-up capture and access check

`wpr -profiledetails` accepted `work/runtime/codex-portability-fileio.wprp` and listed file initialization, disk I/O, write stacks, and registry events in `default-wpr-profile-codex.log`.

The locked start probe returned `0x80070005` with the current Windows token. `default-wpr-access-codex.log` also confirms WPR is idle.

### Requests for Claude

Use the profile during the next authorized elevated no-flags boot under the shared lock and the existing Ghost cap.

```powershell
wpr -start 'work/runtime/codex-portability-fileio.wprp!Portability' -filemode -recordtempto 'work/runtime' -instancename CodexPortability
# Run the existing no-flags release fixture through Ghost.
wpr -stop 'work/runtime/portability-fileio.etl' -instancename CodexPortability
```

### Items 3 and 4 on the longer scripted boots

`release-long-boots-codex.log` counts zero unresolved NIDs and zero null calls across `blk6`, `blk7`, and `blk8`. The runs handled 24, 20, and 14 scripted presses respectively, and each reached the keyboard abort path.

Each run reports three font-open failures under the executable's default `dev_flash` folder. The current generated HLE table still omits the nine keyboard and media registrations listed above.

### Requests for Claude

Use `--dev-flash work/runtime/firmware-codex/dev_flash` during the next extended capture and keep its `PS3_MILESTONE_OUT` log with the menu frame.

### Runtime patch replay through 0036

The raw replay in `patch-replay-0036-raw-codex.log` stops at `0026`. The LF-copy replay in `patch-replay-0036-lf-codex.log` applies all 28 patches through `0036` against pinned ps3recomp `ae92407b`. Only the scratch copies of `0026` and `0027` were normalized.

The replayed font, audio, and pad files match the worktree. The two checked-in rendering patches still need the line-ending fix before a clean replay.

### Item 1 CLI flags through patch 0036

Added `--rsx-vp-scale`, `--rsx-flip-mark`, `--gcm-flip-wrap-wait`, `--rsx-full-split`, and `--audio-wav` in `port/cli_options.*`, `port/main.cpp`, and `docs/CLI.md`.

| Check | Evidence |
|---|---|
| CLI fixture | `cli-0036-red-codex.log` rejects the first new flag before the change. `cli-0036-green-codex.log` passes both switch values, malformed values, both argument forms, and environment precedence. |
| Locked build | `build-fix-1.02-codex-cli-0036.log` ends with `[done] build`. |
| Hidden Windows boot | Build `27e7cf82` exited 0 and wrote 3,473,408 bytes of 48 kHz stereo float audio to the path relative to the launch directory. The inherited WAV path received no file. |
| WAV setup error | `cli-0036-integration-codex.log` records exit 1 for a file used as the parent directory and confirms the original file was preserved. |
| Sample check | `cli-0036-wav-format-codex.log` records 868,352 finite samples, with 321,507 above the magnitude threshold of `1e-6`. |

The fixture verifies the four render and FIFO controls at the environment boundary. Their individual effects in a full round still need coverage.

### Item 2 elevated WPR capture

- With the build lock held, the elevated WPR helper recorded a no-flags Ghost launch of build `08db781f`. The boot log `boot-fix-1.02-codex-wpr-codex-53c41ac1.log` has both `[boot] dispatching entry OPD` and `[cellAudio] Mixing thread started`, with zero unresolved NIDs. The distribution contains zero WAV files, and the launch directory is empty.
- The first PID-specific stop timed out after four seconds, and a second stop terminated the game and its child about 55 seconds after launch, exceeding the 20-second cap. WPR stopped recording before the game exited, and its merge outlasted the runner's wait.
- Writes after recording stopped are unverified. See `wpr-portability-run-codex.log` for the runner output and `work/runtime/wpr-codex-53c41ac1/` for the trace files.

### Item 2 startup write attribution

WPR saved the startup trace for build `08db781f`. All 2,614 write requests had a completion and a stack, with zero events lost. The 1,905 successful requests went to four destinations.

| Destination | Completed writes |
|---|---:|
| Distribution | 763 |
| Redirected boot log | 1,093 |
| NVIDIA ProgramData | 5 |
| NTFS metadata on the distribution volume | 44 |

Six distribution writes matched Direct3D cache paths by the file-create and rundown timestamps. The 44 NTFS writes split into 38 to `$LogFile` and six to `$MFT`. `wpr-portability-attribution-codex.log` records the counts. This WPR recording has no registry events and ended before game exit.

### Item 1 frame clock FIFO wait

`port/main.cpp` now waits for the existing FIFO event with a 4 ms timeout. The new `--gcm-fifo-kick 0|1` option in `port/cli_options.*` overrides `GCM_FIFO_KICK` and defaults to the event wait. `docs/CLI.md` lists the switch.

| Check | Evidence |
|---|---|
| CLI | `fifo-kick-cli-codex.log` passes both values, invalid input, and environment precedence. |
| Build | `build-fix-1.02-fifo-kick-codex-0cd15f72.log` ends with `[done] build` and produced `29ab78d8`. |
| Hidden muted boots | `fifo-kick-integration-codex.log` records exit 0 at 12.97 s with the timed wait and 12.57 s with the event wait. Both started the mixer and recorded zero WAV files, unresolved NIDs, or null calls. |

### Requests for Claude

Build `29ab78d8` is archived in `build/fifo-kick-29ab78d8/`. Measure the two no-flip intervals and compare the first tee using the same build with both FIFO settings. Both intervals and the tee transition are beyond the capped Codex runs. Include the staged firmware path and a menu frame with its milestone log in the longer test.

### Item 2 muted launch and exit trace

Build `29ab78d8` ran under Ghost with `PS3_MUTE=1` and `--exit-after 12`. `wpr-portability-exit-run-codex.log` records exit 0 in 12.79 s, an empty launch folder, and no WAV file. All storage options kept their defaults.

`wpr-portability-exit-paths-codex.log` accounts for 2,638 write requests with no missing completions or lost events. The successful writes were 815 inside the distribution, 1,042 to the redirected test log, five to NVIDIA ProgramData, and 49 to NTFS metadata. No write reached the host AppData or launch folder.

The classic registry trace shows three successful value writes. `wpr-portability-registry-stack-codex.log` reproduced all three in a second muted run that exited 0 in 12.75 s.

| Value | Stack evidence |
|---|---|
| Windows activity record for `conhost.exe` | `bam.sys` and `condrv.sys`. This record is covered by the owner's allowance. |
| Windows activity record for the game executable | `bam.sys` and the Windows kernel. |
| `data` under Microsoft's `TIP\AggregateResults` key | Windows kernel and Windows DLLs above the executable's runtime frame. |

The classic trace also shows 12 create-key events against Windows text-input settings and 25 set-information events against Windows or driver keys. The create events give no disposition. The executable has no direct registry mutation imports.

### Requests for Claude

The file-write checks passed through clean exit. The registry gate remains open for the game executable's Windows activity record and the Microsoft text-input update, which fall outside the current allowance.

### Runtime patch replay through 0037

The raw series still stops at `0026`. The scratch replay with LF copies of `0026` and `0027` applies all 29 on-disk patches against pinned ps3recomp `ae92407b`. Both replayed video files match the worktree. See `patch-replay-0037-raw-codex.log` and `patch-replay-0037-lf-codex.log`.

### Item 1 CLI flags through patch 0037

Added `--rsx-vs-memo`, `--rsx-pso-reuse`, `--rsx-tex-memo`, `--rsx-srv-dedup`, `--rsx-vtx-fast`, and `--rsx-strip-ix` in `port/cli_options.*`. The same option table handles `--rsx-prof` and `--rsx-speed-check` and keeps Windows renderer controls behind the D3D12 check in `port/main.cpp`. `docs/CLI.md` lists the defaults and environment variables.

| Check | Evidence |
|---|---|
| CLI | `rsx-speed-cli-codex.log` passes switch bounds, profiler levels, the sample interval limit, and environment precedence. |
| Locked build | `build-fix-1.02-rsx-speed-codex-3ae57d7a.log` ends with `[done] build` and produced `2a459f40`. |
| Hidden muted boots | `rsx-speed-integration-codex.log` records exit 0 in 13.46 s with the six switches off and 12.48 s with them on. Both runs had zero unresolved NIDs or null calls. |
| Renderer checks | The enabled run logged 326 vertex, 333 vertex shader, 15 texture, 335 pipeline state, and six strip checks, all with zero mismatches. The disabled run printed the profiling summary with the detailed report and speed checker disabled. |

These runs cover startup rendering. The first-tee load timing and full-round rendering comparisons are pending.

### Item 2 portability allowance approved

The release owner approved the Windows-managed registry records observed during launch and shutdown, including the executable's Windows activity record and Microsoft text-input updates. The earlier console and NVIDIA ProgramData allowance still applies. The clean-exit file and registry traces satisfy the portability gate under that allowance.

### Items 3 and 4 coverage through 0037

`peripheral-coverage-0037-codex.log` checks 110 of 110 imports in the seven assigned libraries against the generated HLE table, port overrides, and NP score context registrations. The two keyboard and seven media registrations remain with their module owners. Both capped boots on `2a459f40` logged zero unresolved NID calls.

### Requests for Claude

Apply the release-gate wording below. It passed `git apply --check --unidiff-zero` against the current `STATE.md`.

~~~diff
--- a/docs/orchestration/STATE.md
+++ b/docs/orchestration/STATE.md
@@ -93 +93 @@
-  2. Portable by default. All files stay in the executable's folder. Deleting the folder removes the game.
+  2. Portable by default. The port stores its files in the executable's folder. Deleting the folder removes the game. The release owner permits the Windows registry and NVIDIA ProgramData activity observed in the portability traces.
@@ -96 +96 @@
-- Release gate status today: the executable has no DLL dependencies beyond Windows system libraries. It takes one positional ELF path and reads `PS3_VFS_ROOT`, `PS3_HDD0_ROOT`, `PS3_HDD1_ROOT`, `PS3_SAVEDATA_ROOT` and `PS3_TITLE` from the environment. No CLI flags exist yet, and portable defaults are not verified.
+- Release gate status for the tested Windows builds. One executable discovers the fixed 1.02 game files or prints the expected location and exits 1. Default-path startup and clean exit keep the port's files in its folder, with the approved Windows and NVIDIA records. Build `29ab78d8` passed the clean-exit trace. `docs/CLI.md` lists CLI controls through build `2a459f40`. The tarball gate applies when a release ships an AppImage.
~~~

### Items 3 and 4 contracts for the remaining keyboard and media imports

- `cellOskDialogExtSetInitialScale` takes one float, validates the range 0.80 through 1.05, and keeps the value for the initial keyboard layout. Plan for an FPR-aware registration. The reference uses parameter error `0x8002B504`, while the local header assigns `0x8002B303` to its generic invalid-parameter constant. [Reference implementation](https://github.com/RPCS3/rpcs3/blob/0ebb63697666a54b44a4de69ef222c4ecee0001a/rpcs3/Emu/Cell/Modules/cellOskDialog.cpp#L1047) [Reference constants](https://github.com/RPCS3/rpcs3/blob/0ebb63697666a54b44a4de69ef222c4ecee0001a/rpcs3/Emu/Cell/Modules/cellOskDialog.h)
- `cellOskDialogExtRegisterForceFinishCallback` takes a non-null guest function pointer. The callback has no arguments and returns a guest boolean. The system-dialog path uses that result to decide whether to finish a hidden keyboard in continuous mode. [Callback declaration](https://github.com/RPCS3/rpcs3/blob/0ebb63697666a54b44a4de69ef222c4ecee0001a/rpcs3/Emu/Cell/Modules/cellOskDialog.h#L230) [Reference implementation](https://github.com/RPCS3/rpcs3/blob/0ebb63697666a54b44a4de69ef222c4ecee0001a/rpcs3/Emu/Cell/Modules/cellOskDialog.cpp#L1184)
- The reference uses parameterless success stubs for the seven absent `cellSail` exports. Those stubs give the names. Argument layouts and output behavior still need a source for the media owner. [Reference media exports](https://github.com/RPCS3/rpcs3/blob/0ebb63697666a54b44a4de69ef222c4ecee0001a/rpcs3/Emu/Cell/Modules/cellSail.cpp)

`xOff1` and `xOn1` completed with zero unresolved NIDs and three firmware font-open failures each. Both used the default firmware folder of build `64ea5a5d`. The two logs give no new firmware menu evidence.

### Items 2 and 5 smoke test of the patch 0037 executable

Reverified archived build `2a459f40` from a separate launch folder. `llvm-readobj --coff-imports` lists ten Windows system DLLs. All three launches used Ghost and `PS3_MUTE=1`.

| Fixture | Expected and observed result |
|---|---|
| Executable alone | No-flag launch exited 1 in 0.27 s, listed the required game files, and created no runtime directories. |
| Same-size ELF with a wrong digest | No-flag launch exited 1 in 0.68 s before guest dispatch or runtime directory creation. |
| Adjacent game folder with the expected ELF | The guest dispatched and started the mixer. The test exited 0 in 12.50 s with the exit timer. The game, HDD, and save paths all resolved under the distribution. |

`release-artifact-0037-codex.log` records the executable hash and the boot log names. The launch folder and isolated Windows profile paths stayed empty. The approved registry allowance relies on the earlier WPR captures.

### Items 3 and 4 wider peripheral import audit

`release-import-candidate-gaps-codex.log` compares 445 import records across 34 libraries with the generated table and explicit production registrations. It flags 67 candidates for review. Runtime registration tables and reachability still need separate checks.

Confirmed 15 candidate names by matching the public export lists to the game NIDs with `compute_nid`. Added nine missing names in `tools/nid_database.py` and refreshed patch `0007`.

| Library | Names added | Previously named candidates |
|---|---|---:|
| `cellMic` | `cellMicSetNotifyEventQueue`, `cellMicRemoveNotifyEventQueue` | 0 |
| `cellVideoExportUtility` | `cellVideoExportInitialize2`, `cellVideoExportFromFile`, `cellVideoExportFinalize` | 0 |
| `sys_io` | `cellPadLddRegisterController`, `cellPadLddGetPortNo`, `cellPadLddDataInsert`, `cellPadLddUnregisterController` | 1 |
| `cellRec` | None | 5 |

`peripheral-expanded-name-resolution-codex.log` passes all 15 name lookups. The name changes provide diagnostics. Runtime handler coverage for these candidates remains with their module owners. [Microphone exports](https://github.com/RPCS3/rpcs3/blob/0ebb63697666a54b44a4de69ef222c4ecee0001a/rpcs3/Emu/Cell/Modules/cellMic.cpp) [Video-export functions](https://github.com/RPCS3/rpcs3/blob/0ebb63697666a54b44a4de69ef222c4ecee0001a/rpcs3/Emu/Cell/Modules/cellVideoExport.cpp) [Pad exports](https://github.com/RPCS3/rpcs3/blob/0ebb63697666a54b44a4de69ef222c4ecee0001a/rpcs3/Emu/Cell/Modules/cellPad.cpp)

### Item 4 firmware-backed capture on patch 0037

Build `2a459f40` used a copied save, the staged firmware, five-poll scripted Cross presses, and `PS3_MUTE=1`. The Ghost run exited 0 in 17.48 s after 17 scripted press events, with zero unresolved NIDs or font-open failures. Its milestone log includes `182 font:glyph-pixels-written`.

`work/runtime/firmware-menu-d38f5b07/frames/frame_00/backbuffer.bmp` shows the reception scene with readable version and user labels. The manifest records present 1 at frame 1144. A later capture showed the autoload screen, and its 19-second launcher wait timed out. The game logged exit 0 and the recorded PID was gone at cleanup. The exact runtime and a frame with selectable menu options remain unverified.

The completed `round37` log has zero unresolved NIDs and three firmware font-open failures. `STATE.md` records reaching the third tee.

### Runtime patch replay through 0038

`patch-replay-0038-raw-codex.log` still stops at `0026`. `patch-replay-0038-lf-codex.log` replays all 30 on-disk patches with LF copies of `0026` and `0027` in scratch. The NID database, D3D12 backend, and SPURS job-guard source match the worktree. Patch `0038` adds no CLI setting.

### Item 1 window caption observation

Opened the EmberGhost desktop by name and queried the D3D12 HWND for active build `68174eea` with `GetWindowTextW`. The read returned 72 characters, including the game name, 19.38 FPS, and 1,270 draws. This verifies the caption at that instant in the later run. The empty-caption observation on `round37` still lacks a reproduction.

### Item 4 microphone notification handler contract

The two microphone exports both take a 64-bit queue key. The reference set call returns `0x80140103` before microphone init and `0x8014010D` if no event queue matches the key. A valid call stores the key. Attach events depend on registered microphone devices. Removal clears the notification state after the init check. [Reference implementation](https://github.com/RPCS3/rpcs3/blob/0ebb63697666a54b44a4de69ef222c4ecee0001a/rpcs3/Emu/Cell/Modules/cellMic.cpp#L1264) [Error constants](https://github.com/RPCS3/rpcs3/blob/0ebb63697666a54b44a4de69ef222c4ecee0001a/rpcs3/Emu/Cell/Modules/cellMic.h#L14)

### Requests for Claude

Use the existing `sys_event_find_queue_by_key` helper for the set call. The local `CELL_MIC_ERROR_NOT_INITIALIZED` constant is `0x80140101`, so the new handlers need their own verified error mapping. The checked boot runs leave both imports untested. Confirm removal semantics for an unknown key before treating that case as covered.

### Item 1 CLI header dependency

The first `--mute` build compiled `cli_options.cpp` and kept `main.cpp.obj` from before the option layout changed. `ninja -t deps CMakeFiles/HotShotsGolfRecomp.dir/main.cpp.obj` reported zero dependencies. The mismatched build `70e1d444` printed help in 0.32 seconds when passed `--mute`. The source-level parser fixture passed because it compiled both callers against the current header.

### Requests for Claude

Declare the shared header on both source files. The change passed `git apply --check --unidiff-zero` against the current `port/CMakeLists.txt`.

~~~diff
--- a/port/CMakeLists.txt
+++ b/port/CMakeLists.txt
@@ -211,0 +212,5 @@
+# The clang-cl invocation can leave Ninja without header dependencies.
+# Rebuild both users when the shared options layout changes.
+set_property(SOURCE main.cpp cli_options.cpp APPEND PROPERTY
+    OBJECT_DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/cli_options.h")
+
~~~

### Item 1 mute flag

Added `--mute` in `port/cli_options.h` and `port/cli_options.cpp` and documented it in `docs/CLI.md`. The flag sets `PS3_MUTE=1` before audio starts. Without the flag, the launcher preserves the inherited setting.

| Check | Result |
|---|---|
| Parser fixture | `mute-cli-red-codex.log` reproduces the missing option. `mute-cli-green-codex.log` passes flag parsing, environment preservation, and rejection of an attached value. |
| Help | `cli-help-doc-parity-codex.log` matches all 37 documented options. |
| Rebuild | `build-fix-1.02-codex-mute-rebuild.log` recompiles `main.cpp.obj` and reports `[done] build` after the forced build. The source contents of `main.cpp` stayed unchanged. |
| Runtime | Build `2962b871` exited 0 in 12.94 s with Ghost, `--hidden`, `--mute`, and `PS3_MUTE=1` as a safety guard. The WAV contains 333,056 stereo frames at 48 kHz and has a nonzero signal, and the boot logged zero unresolved NIDs. |

The parser fixture checks the effect of the flag with no inherited mute setting. The runtime smoke test kept the guard on.

### Item 1 presented-frame counter in FIFO-off comparison

`guest-flips-rgkick0-codex.log` samples the runner's presented-frame counter on the active Ghost process. Build `70e1d444` was already 344.22 s old when sampling started. One 4.77 s gap appeared near age 448.78 s. The observed process exited at age 456.11 s.

The sample begins after the first-tee load interval. A same-build comparison needs the counter sampled from launch for both controls.

### Item 1 presentation gaps during rgcap

The sampler attached to build `2962b871` at game age 74.43 s and stopped at 314.48 s. Two gaps appeared. The first lasted 2.92 s at age 85.40 s, and the second lasted 3.38 s at age 115.06 s. See `guest-flips-rgcap-codex.log`.

The boot logged zero unresolved NIDs and three firmware font-open failures. Because sampling began 74.43 s into the run and the earlier FIFO-off sample used a different executable, the first-tee timings and same-build comparison remain open.

### Item 4 selectable title menu with staged firmware

| Check | Evidence |
|---|---|
| Launch and shutdown | `firmware-menu-2962-codex.log` records exit 0 in 18.65 s. Build `2962b871` ran via Ghost with `--hidden`, `--mute`, and `PS3_MUTE=1` using staged firmware and a copied save. |
| Dispatch | Zero unresolved NIDs and zero font-open failures. The milestone log records `182 font:glyph-pixels-written`. |
| Menu | Frame 1176 shows New Game, Continue, and HSG Info with Continue selected. The next captured frame shows loading. See `work/runtime/firmware-menu-d80125da/frames/frame_02/backbuffer.bmp`. |

### Items 3 and 4 live registration audit on patch 0036

| Check | Evidence |
|---|---|
| Dispatch tables | `registered-nids-rg36-codex.log` verifies the hash of active build `d1eb1479` and reads the generic, context, and fast tables without changing the process. Table counts stayed stable during the snapshot. |
| Coverage | Generic or context handlers cover 378 of 445 fixed 1.02 imports, including all 110 in the assigned libraries. Both fast handlers have a generic or context fallback. The 67 absent entries match the source audit. |

Whether gameplay reaches the 67 unregistered imports remains open.

### Requests for Claude

Compare `--gcm-fifo-kick 0` and `--gcm-fifo-kick 1` on one executable with the same save, swing script, shader cache state, and staged firmware. Start sampling when each Ghost PID is available, then correlate the two no-flip intervals with the course loads and capture the first tee. This needs the lead's longer test window.

### Items 3 and 4 release-build dispatch and import names

| Check | Evidence |
|---|---|
| Live dispatch | Build 2962b871 exited 0 in 12.49 s under muted Ghost. The boot logged zero unresolved NIDs. The read-only snapshot in registered-nids-2962-codex.log follows dispatcher lookup order and finds handlers for 378 of 445 imports, including all 110 in the assigned libraries. |
| Call sites | peripheral-direct-branches-2962-codex.log finds 91 direct guest branches to the 67 unregistered imports. peripheral-lifted-calls-2962-codex.log finds direct calls to all 67 wrappers in the generated PPU sources. These checks identify code paths to test. Runtime reachability remains unverified. |
| Names | Added 13 export names to tools/nid_database.py. The resolver already knew 50 through its built-ins and supplemental sources. Four remain unnamed. peripheral-release-import-names-verify-codex.log confirms hash matches, lookups in both directions, and preservation of earlier entries. |
| Replay | The refresh of patch 0007 keeps the SPURS name in patch 0002. The raw replay reaches 0026 and fails there. With LF copies of 0026 and 0027 in scratch, all 30 patches replay and the NID database, font, and filesystem blobs match the worktree. See patch-replay-0038-release-nids-lf-codex.log. |

The 13 names cover two localization functions, three clock functions, five certificate queries, and three title-storage functions. [RPCS3 export lists at the pinned revision](https://github.com/RPCS3/rpcs3/tree/0ebb63697666a54b44a4de69ef222c4ecee0001a/rpcs3/Emu/Cell/Modules)

### Requests for Claude

The 67 registrations and their direct call sites span modules outside the Codex assignment. Use the live and generated call-site logs to choose which callers to exercise. The four unnamed imports are cellSysutil 0x24644561, 0x41F20828, and 0x7F21C918, and sys_net 0xA9A079E0.

### Item 3 final names for the 67 registration gaps

Found the four remaining exports in the public PS3 NID table and confirmed each with the project hash. Added cellWebBrowserWakeupWithGameExit, cellOskDialogDisableDimmer, and cellOskDialogAddSupportLanguage under cellSysutil, and inet_aton under sys_net. peripheral-release-import-last-four-codex.log verifies both lookup directions and confirms that the resolver now names all 67 imports. [Public PS3 NID table](https://github.com/zecoxao/ida_console_py_ps3/blob/ecd2f5bed174476ac8e3a22b3cadc78e3620dde1/loaders/ps3.xml)

Patch 0007 adds 17 names across the two updates. All 30 patches replay with the LF scratch copies of 0026 and 0027. The replayed NID database matches the worktree. See patch-replay-0038-all-release-names-lf-codex.log. Handler coverage and reachability still need verification with the module owners.

### Item 1 fullscreen and windowed regression check on build 2962b871

Both Ghost launches used mute, verbose level 1, their own save root, a disabled shader cache, and a 12-second exit timer. The runner held BUILD.lock during each launch. See window-modes-2962-codex.log and the two referenced boot logs.

| Mode | Observed window | Result |
|---|---|---|
| Fullscreen | Borderless, 2560×1440, hidden, nonactivating, and outside the foreground at the window check | Exit 0 in 13.18 s |
| Windowed | Requested 960×540, hidden, nonactivating, and outside the foreground at the window check | Exit 0 in 13.13 s |

Both boots reached the guest flip command, used the requested save root, and logged verbose tile setup. Neither logged device removal code 0x887A0005 or an unresolved NID. The older fullscreen failure did not recur during these startup checks. Behavior later in a round remains unverified.

### Item 1 missing CLI values

A missing path value could consume the following option. The parser now reports the missing value before startup. Use the equals form for a literal value beginning with two hyphens. Changed port/cli_options.cpp and docs/CLI.md.

| Check | Evidence |
|---|---|
| Regression fixture | cli-missing-value-red-codex.log reproduces --savedata consuming --mute. cli-missing-value-green-codex.log checks 12 missing values and verifies that equals syntax and separate flags still work. cli-missing-value-mute-regression-codex.log verifies that --mute sets PS3_MUTE=1 and omission preserves the setting. |
| Build and bad command | build-fix-1.02-codex-cli-missing-value.log ends with [done] build. Under muted Ghost, build b2ab3d7a rejected --savedata --mute with exit 2 and no runtime files. The log is boot-fix-1.02-codex-cli-value-missing-b2ab3d7a.log. |
| Valid command | The muted Ghost run in cli-audio-later-b2ab3d7a-codex.log exited 0 in 16.59 s. It logged zero unresolved NIDs and wrote 454,400 stereo frames at 48 kHz. The first nonzero mix sample appeared at frame 290,310 and the logged peak was 0.0886. |

The two 12-second exit-timer runs captured 140,544 and 250,368 silent mixer frames before shutdown. The earlier build first produced a signal at frame 277,254. The 16-second run on the same rebuilt executable captured the signal beyond the shorter capture windows. The test verifies the pre-mute mixer and WAV path.

### Items 2 and 5 relocated build b2ab3d7a

llvm-readobj confirmed that the single executable imports ten Windows system DLLs. Ghost launched every case with mute enabled from a working directory separate from the distribution. The runner held BUILD.lock throughout. See release-artifact-b2ab3d7a-codex.log.

| Fixture | Result |
|---|---|
| Executable alone | Exit 1 in 0.29 s, setup locations printed, and no runtime files created. |
| Adjacent game data with an incorrect ELF of the expected size | Exit 1 in 0.25 s before dispatch or runtime writes. |
| Adjacent game data with the expected ELF | Exit 0 in 12.54 s with a 12-second exit timer. The guest dispatched and the mixer started. The game, HDD, and save roots resolved under the distribution. The launch directory and isolated profile paths stayed empty. |
| Adjacent game data with no CLI flags or path overrides | The guest dispatched and used the same four default roots. The first close attempt could not post a window message across desktops. Posting from a thread on the Ghost desktop delivered the close request, but the guest used the host exit fallback before reaching the mixer on that run. A clean guest exit in this exact scenario remains unverified. |

Neither no-flags run changed the launch directory. The registry allowance remains backed by the previous WPR captures.

### Item 1 FIFO event wait on sw1

The read-only FIFO state check confirmed mode 1 on the lead's running build d4f2702b. The presentation sampler covered game age 19.84 through 279.85 s and recorded two gaps of at least 2 s.

| Game age | Gap | Presented frame counter |
|---|---|---|
| 75.20 s | 3.12 s | 4487 to 4491 |
| 103.36 s | 2.79 s | 7005 to 7009 |

The boot log shows the Challenge layout and the first two course01 hole files opening successfully. The course log observer attached after both gaps, so the samples give no exact timing for those file opens. The first-tee frame and same-build mode 0 control remain open. See fifo-state-sw1-codex.log, guest-flips-19752-codex.log, and boot-fix-1.02-sw1-1.log.

The read-only dispatch check on the same process reports 378 of 445 imports registered. Its 67 gaps match the preceding snapshot.

### Items 1, 2, and 5 clean no-flags window close

Closing the window stopped the Windows frame clock from draining the RSX FIFO, which could leave the guest waiting on a fence while exit callbacks were queued. The change in port/main.cpp keeps FIFO and flip processing active after close while stopping host presents and window-message pumping.

| No-flags Ghost run | Outcome |
|---|---|
| Control, d4f2702b | Window close queued three exit callbacks. The host fallback ended the process after 17.66 s. The log lacks a guest exit marker. |
| Fixed, b1055466 | Window close queued three exit callbacks. Audio shut down and the guest called sys_process_exit(code=0). The launcher exited 0 in 16.61 s with zero unresolved NIDs. |

The locked Git Bash build in build-fix-1.02-codex-window-close.log rebuilt main.cpp.obj, relinked, and ended with [done] build. Both muted Ghost runs used the same staged game data and copied shader cache, with no CLI flags or path overrides. The launch folder stayed empty. Game, HDD, and save roots resolved beside the executable. See no-flags-window-close-control-codex.log and no-flags-window-close-fixed-codex.log. Registry coverage still comes from the earlier WPR traces.

### Item 1 FIFO-enabled timing on sw2

On FIFO-enabled build 6b26eeb2, the frame sampler recorded 16 gaps of at least 2 s from game age 71.74 to 291.80 s. The build recompiled cellGcmSys.c and rsx_d3d12_backend.c.

A 6.45 s gap began at age 91.50 s, just after the 90.91 s confirm, and the log records Challenge at 109.17 s and the dress-up layout at 117.24 s. From age 164.28 to 277.65 s, the presented-frame counter increased from 6,648 to 6,999. The boot had reached the dress-up flow and had yet to open the expected first course file when checked at age 305 s.

The earlier sw1 build opened the first two course files with the same FIFO setting, so the timing difference leaves the effect of the FIFO wait unverified. See fifo-state-sw2-codex.log, guest-flips-sw2-codex.log, and course-markers-sw2-codex.log.

### Item 1 course-entry timing on sw3

With FIFO event waiting enabled on build b5985c29, the sampler counted seven gaps of at least 2 s from age 40.55 s to process exit at 205.30 s. Six came before the first scripted confirm.

A 3.00 s gap began at age 149.39 s alongside the confirm recorded at 149.42 s. The first two course files opened at 157.49 and 159.06 s. The probe recorded no later gap of at least 2 s before process exit. See fifo-state-sw3-codex.log, guest-flips-sw3-codex.log, and course-markers-sw3-codex.log. A tee capture and the same-build FIFO-off control remain open.

### Item 4 Move hue requests

The existing cellGemTrackHues registration at 0x928AC5F8 returned success without writing the guest output. The handler now reads four big-endian hue requests, stores the selected hues, and writes all four results when an output buffer is supplied. It supports automatic colors, disabled tracking, and retaining the previous selection. No controller is reported connected. Changes are in libs/hardware/cellGem.c and patch 0009.

| Check | Evidence |
|---|---|
| Regression | gem-track-hues-red-confirmed-codex.log fails on the unchanged guest output. gem-track-hues-green-codex.log passes selection, optional output, overlapping buffers, null and uninitialized errors, and end/reinit resets. |
| Patch replay | patch-replay-0038-gem-hues-codex.log replays all 30 patches with the two LF scratch copies and matches the Move source. |
| Build and boot | build-fix-1.02-codex-gem-track-hues.log recompiles cellGem.c and regenerates the dispatch table. Lead run sw4 on build f1c52f46 dispatched the guest and started the mixer, with zero unresolved NIDs at the snapshot. |

The public header defines the retain-selection sentinel. Its behavior was tested in the focused host harness, and physical Move behavior remains unverified. The runtime sample verifies startup and registration. The focused fixture exercises the hue calls. [Reference implementation](https://github.com/RPCS3/rpcs3/blob/0ebb63697666a54b44a4de69ef222c4ecee0001a/rpcs3/Emu/Cell/Modules/cellGem.cpp#L4226) [Reference constants](https://github.com/RPCS3/rpcs3/blob/0ebb63697666a54b44a4de69ef222c4ecee0001a/rpcs3/Emu/Cell/Modules/cellGem.h#L95)

### Windows release evidence through f1c52f46

| Requirement | Evidence and status |
|---|---|
| One executable and first-run discovery | The f1c52f46 executable imports ten Windows system DLLs. The relocated fixture verified setup instructions, rejection of a same-size wrong ELF, and launch with adjacent data on b2ab3d7a, plus a clean no-flags boot and shutdown on b1055466. |
| Portable defaults | The no-flags window-close check used executable-relative game, HDD, and save roots and left the alternate working directory empty. The approvals and earlier WPR capture cover the observed Windows registry and NVIDIA ProgramData records. |
| Tarball beside an AppImage | Conditional on an AppImage release. No AppImage exists in the checked repository or local build tree. |
| CLI | release-audit-checks-codex.log confirms all 37 help flags match the documentation and include every explicitly named release control. Fullscreen, hidden behavior, save routing, and verbose output have runtime checks above. |
| Peripheral dispatch | The f1c52f46 live table contains all 110 imports from the seven assigned libraries. The remaining 67 import stubs have names and direct callers in the generated code, with no generic or context registration in the sampled live table. |
| Patch reproduction | release-audit-raw-patches-codex.log confirms the tracked sequence stops at 0026. With scratch LF copies of 0026 and 0027, the latest checked sequence replays all 30 patches. |

Remaining lead-owned checks are the longer FIFO comparison, registration coverage outside the seven assigned libraries, and replay of the tracked rendering patches.

### Item 4 completed sw4 log

The lead's f1c52f46 process ended after the boot log recorded the Challenge layout and the first two course files opening. The final log has 18,551 lines, zero unresolved NID messages, and zero D3D12 device removal messages. It has no guest exit marker. This extends the verified dispatch path through course loading. The 67 unregistered imports still require coverage outside the assigned libraries.

### Full patch replay through 0039

The command .venv/Scripts/python.exe codex_full_patch_contents.py replayed 31 patches from pinned commit ae92407b with LF scratch copies of 0026 and 0027. The comparison covered every modified, new, and replayed runtime source path. Of 42 paths, 10 match byte for byte and 32 differ only in line endings. See release-full-patch-contents-codex.log.

The first hash comparison appeared to flag sys_event.c because Git applied its text filter to the worktree file. Comparing the file and the replayed blob directly confirmed no content change there.

### Requests for Claude

The two checked patch files contain 59 and 431 CRLF endings, respectively. Apply the scratch-verified byte transformation to those two tracked files from the project root.

~~~python
from pathlib import Path

for name in ("0026-rsx-menu-scene.patch", "0027-rsx-frame-time.patch"):
    patch = Path("patches/runtime") / name
    patch.write_bytes(patch.read_bytes().replace(b"\r\n", b"\n"))
~~~

### Item 1 CLI switches for patch 0039

The three rendering controls accept 0 or 1, default to enabled, and preserve inherited settings when omitted. Added --rsx-disp-depth-tex, --rsx-disp-depth-keep, and --rsx-keep-display in port/cli_options.h, port/cli_options.cpp, and docs/CLI.md.

| Check | Evidence |
|---|---|
| Parser | rsx-swing-cli-red-codex.log reproduces the unknown option before the change. rsx-swing-cli-green-codex.log passes both values, invalid input, and environment precedence. |
| Build | build-fix-1.02-rsx-swing-codex-361357ef.log recompiles cli_options.cpp and main.cpp before linking f43f7a59. The runner touched the main.cpp timestamp to rebuild it after the options layout changed. |
| Muted Ghost startup | rsx-swing-cli-integration-codex.log records exit 0 in 12.70 s with all three switches off and 12.62 s with them on. Both started the mixer, and each log has zero unresolved NIDs and zero D3D12 device removals. |

Help and docs list the same 40 flags. Swing-frame comparisons extend beyond these startup runs.


### Item 1 FIFO timing on imp1

With FIFO event waiting enabled on build 35939b9a, the frame sampler covered game age 34.14 to 214.21 s. It recorded gaps of 2.68, 2.79, 5.18, and 2.67 s beginning at ages 62.38, 93.12, 124.82, and 145.29 s. See fifo-state-imp1-codex.log and guest-flips-imp1-codex.log.

The process was still running when sampling ended, and the boot log shows the Challenge layout and the first two course files opening. The same-build FIFO-off result and first-tee frame comparison remain open. See boot-fix-1.02-imp1-1.log.


### Item 4 HTTP client handle byte order

Changed cellHttpCreateClient in libs/network/cellHttp.c to write the client ID in guest byte order. Patch 0009 carries the change.

| Check | Result |
|---|---|
| Focused fixture | http-client-handle-red-codex.log shows client 1 reading back as 0x01000000. The same fixture in http-client-handle-green-codex.log reads 0x00000001 and uses it to configure, destroy, and recreate the client. |
| Build and boot | build-fix-1.02-imp2.log recompiles cellHttp.c and ends with [done] build. Build 7bcf370f creates client 0 during imp2 startup. The fixture exercises client 1. |
| Patch replay | patch-replay-0039-http-client-handle-codex.log replays 31 patches with LF scratch copies of 0026 and 0027. The HTTP source matches. Two live rendering files differ from the replay and belong to Claude. |

The live dispatch snapshot on 7bcf370f matches the previous one. All 110 imports in the seven assigned libraries have handlers. Sixty-seven imports outside those libraries lack a registered handler. See registered-nids-imp2-codex.log.

### Item 1 FIFO timing on imp2

The frame sampler covered game age 45.46 to 444.84 s with FIFO event waiting enabled on 7bcf370f. It recorded gaps of 3.11, 2.90, and 3.92 s starting at ages 48.91, 90.55, and 268.00 s. The first two course files opened at 97.76 and 99.32 s. See guest-flips-imp2-codex.log and course-markers-imp2-codex.log.

The completed 22,596-line boot log records zero unresolved NIDs and zero D3D12 device removals. It contains no guest exit marker. FIFO-off timing on the same build and a matching first-tee capture remain open.

### Items 2 and 5 relocated build 7bcf370f

The executable imports ten Windows system DLLs. A no-flags muted Ghost launch used the game, HDD, and save folders beside the executable and left the separate launch directory empty. Closing the window requested three exit callbacks. The guest exited 0 in 14.76 s with zero unresolved NIDs, as recorded in no-flags-window-close-7bcf370f-codex.log and boot-fix-1.02-codex-release-artifact-window-close-7bcf370f.log. The earlier WPR captures supply the registry evidence under the owner's allowance.


### Item 4 UCS-2 conversion coverage

The live table lacks UCS2stoUTF8s (0x2AD091C6) and UTF8stoUCS2s (0xFDBF6AC5). The project NID tool confirms both names, and peripheral-direct-branches-2962-codex.log records six direct guest call sites between them. The generator matches export prefixes such as cell, sce, and sys, so the proposal registers these two names in port/stubs.cpp.

The handlers reuse the local codec helpers and read and write guest lengths and UCS-2 words in big-endian order. On success they write the output length. Malformed input and insufficient space report the remaining input and the completed output. A null destination measures the output size. [RPCS3 UCS-2 input](https://github.com/RPCS3/rpcs3/blob/0ebb63697666a54b44a4de69ef222c4ecee0001a/rpcs3/Emu/Cell/Modules/cellL10n.cpp#L658) [RPCS3 UTF-8 input](https://github.com/RPCS3/rpcs3/blob/0ebb63697666a54b44a4de69ef222c4ecee0001a/rpcs3/Emu/Cell/Modules/cellL10n.cpp#L2634)

`git apply --check --no-index --ignore-space-change` accepts both hunks against the current worktree. The scratch fixture passes exact-capacity output, size queries, malformed input, and partial conversion in both directions. The registration file passes the C++ syntax check. See l10n-owner-proposal-green-codex.log. The worktree still lacks these handlers, and guest calls through the live dispatch table remain unverified.

### Requests for Claude

Apply both hunks together from the repository root and export the cellL10n.c change as a runtime patch. The port needs the two explicit registrations alongside that source change.

~~~diff
--- a/external/ps3recomp/libs/font/cellL10n.c
+++ b/external/ps3recomp/libs/font/cellL10n.c
@@ -8,6 +8,7 @@
  */
 
 #include "cellL10n.h"
+#include "../../runtime/ppu/ppu_memory.h"
 #include <stdio.h>
 #include <string.h>
 
@@ -551,3 +552,78 @@
                           (u32)dst_code, dst, out_len, dst_len);
     return rc;
 }
+
+/* The PS3 bulk conversion exports have a separate status enum from the
+ * host-side codec helpers above. Lengths are guest-endian and count units. */
+enum {
+    L10N_CONVERSION_OK = 0,
+    L10N_SOURCE_ILLEGAL = 1,
+    L10N_DESTINATION_EXHAUSTED = 2,
+};
+
+static int l10n_guest_span(u32 address, u64 size)
+{
+    return size == 0 || (address && size <= (1ull << 32) - address);
+}
+
+static s32 l10n_conversion_stop(u32 src_len, u32 dst_len, u32 remaining,
+                                u32 written, s32 status)
+{
+    vm_write32(src_len, remaining);
+    vm_write32(dst_len, written);
+    return status;
+}
+
+s32 UCS2stoUTF8s(u32 src, u32 src_len, u32 dst, u32 dst_len)
+{
+    if (!l10n_guest_span(src_len, 4) || !l10n_guest_span(dst_len, 4))
+        return L10N_SOURCE_ILLEGAL;
+
+    const u32 count = vm_read32(src_len);
+    if (!l10n_guest_span(src, (u64)count * 2))
+        return l10n_conversion_stop(src_len, dst_len, count, 0, L10N_SOURCE_ILLEGAL);
+    const u32 capacity = dst && count ? vm_read32(dst_len) : UINT32_MAX;
+    u32 written = 0;
+    for (u32 i = 0; i < count; ++i) {
+        u8 bytes[3];
+        const u16 codepoint = vm_read16(src + i * 2);
+        const u32 size = (u32)encode_utf8(codepoint, bytes, sizeof(bytes));
+        if (size == 0)
+            return l10n_conversion_stop(src_len, dst_len, count - i, written, L10N_SOURCE_ILLEGAL);
+        if (size > capacity - written || (dst && !l10n_guest_span(dst, (u64)written + size)))
+            return l10n_conversion_stop(src_len, dst_len, count - i, written, L10N_DESTINATION_EXHAUSTED);
+        if (dst)
+            vm_memcpy_to(dst + written, bytes, size);
+        written += size;
+    }
+    vm_write32(dst_len, written);
+    return L10N_CONVERSION_OK;
+}
+
+s32 UTF8stoUCS2s(u32 src, u32 src_len, u32 dst, u32 dst_len)
+{
+    if (!l10n_guest_span(src_len, 4) || !l10n_guest_span(dst_len, 4))
+        return L10N_SOURCE_ILLEGAL;
+
+    const u32 count = vm_read32(src_len);
+    if (!l10n_guest_span(src, count))
+        return l10n_conversion_stop(src_len, dst_len, count, 0, L10N_SOURCE_ILLEGAL);
+    const u8* bytes = GUEST_PTR(src, const u8*);
+    const u32 capacity = dst && count ? vm_read32(dst_len) : UINT32_MAX;
+    u32 written = 0;
+    u32 consumed = 0;
+    while (consumed < count) {
+        u32 codepoint;
+        const u32 size = (u32)decode_utf8(bytes + consumed, count - consumed, &codepoint);
+        if (size == 0 || codepoint > 0xFFFF)
+            return l10n_conversion_stop(src_len, dst_len, count - consumed, written, L10N_SOURCE_ILLEGAL);
+        if (written == capacity || (dst && !l10n_guest_span(dst, ((u64)written + 1) * 2)))
+            return l10n_conversion_stop(src_len, dst_len, count - consumed, written, L10N_DESTINATION_EXHAUSTED);
+        if (dst)
+            vm_write16(dst + written * 2, (u16)codepoint);
+        ++written;
+        consumed += size;
+    }
+    vm_write32(dst_len, written);
+    return L10N_CONVERSION_OK;
+}
--- a/port/stubs.cpp
+++ b/port/stubs.cpp
@@ -28,6 +28,8 @@
 void ps3_hle_register(u32 nid, const char* name, void* function);
 void ps3_hle_register_ctx(u32 nid, const char* name, void (*function)(ppu_context*));
 u32 vm_read32(u64 address);
+s32 UCS2stoUTF8s(u32 src, u32 src_len, u32 dst, u32 dst_len);
+s32 UTF8stoUCS2s(u32 src, u32 src_len, u32 dst, u32 dst_len);
 s32 cellCameraGetBufferInfoEx(s32 device, void* info);
 s32 cellGemGetImageState(u32 controller, void* state);
 s32 cellGemPrepareCamera(s32 exposure, float quality);
@@ -69,6 +71,8 @@
     REGISTER(sceNpScoreGetBoardInfo);
     REGISTER(cellFontEndLibrary);
     REGISTER(cellFontInitLibraryFreeTypeWithRevision);
+    REGISTER(UCS2stoUTF8s);
+    REGISTER(UTF8stoUCS2s);
     REGISTER(cellGemGetImageState);
     REGISTER(cellGemGetTrackerHue);
     REGISTER(cellGemConvertVideoFinish);
~~~


### Item 4 IPv4 parsing with host sockets disabled

Build e853ac82 left inet_aton (0xA9A079E0) out of the offline dispatch table. The import has three direct guest call sites. The existing parser converts text to network-order bytes and does not need host sockets. port/stubs.cpp now registers it through the same guest calling convention used by the online backend.

| Check | Evidence |
|---|---|
| Before | registered-nids-imp4-codex.log shows 378 of 445 imports registered and lists inet_aton among the eight missing sys_net names. |
| Parser | inet-aton-integration-recheck-codex.log records four-byte guest output, invalid input handling, and parsing without socket initialization. |
| Build and dispatch | The locked Git Bash build in build-fix-1.02-codex-inet-aton.log rebuilds port/stubs.cpp and links 5ed856bd. The live snapshot in registered-nids-inet-aton-codex.log shows 379 of 445 imports registered. The only change in the gap list is inet_aton. |

The focused fixture exercises conversion directly. The muted Ghost run exited 0 in 12.60 s and printed zero unresolved NIDs. It logged the same 16 null-read offsets as the earlier relocated 7bcf370f check. The remaining seven sys_net imports need offline socket behavior from the module owner.


### Items 2 and 5 null reads in the release boot

The relocated 7bcf370f boot and the 5ed856bd offline dispatch boot show the same two sequences. The first read accesses guest address 0xA0 immediately after both lookups for layout_chipin_rank_regist.lay fail. The read in function 0x0078FB68 uses the object pointer in r3. The exact file is absent from the staged game data. The related ranking-board file in the update has a different name and extension.

The remaining fifteen printed reads follow a TTY warning with buffer 0 and length 4,294,967,295. Each log then holds exactly 16,384 consecutive zero bytes, matching the loader's TTY output cap. The current loader routes both syscall 403 and 988 into that same byte-copy path. The public syscall references identify 403 as TTY write and describe 988 as a two-argument PPU exception operation. [RPCS3 syscall table](https://github.com/RPCS3/rpcs3/blob/0ebb63697666a54b44a4de69ef222c4ecee0001a/rpcs3/Emu/Cell/lv2/lv2.cpp#L956) [PS3 DevWiki](https://www.psdevwiki.com/ps3/LV2_Functions_and_Syscalls)

The locked muted Ghost run on 3c81b482 used PS3_NULL_READ_STACK=1 and exited 0 in 14.66 s. The stack at the read of 0xA0 shows r3=0 at return address 0x004B20DC. The stack at the first TTY byte read shows r11=0x3DC, r3=1, r4=0, and r5=0xFFFFFFFF. The guest passed the two-argument form. See boot-fix-1.02-codex-null-read-trace.log.

### Requests for Claude

The proposed loader change reports the two-argument PPU exception operation as unavailable and returns CELL_ENOSYS before reading a TTY buffer. The caller at return address 0x0001AB4C replaces r3 before its next call. The diff passed git apply --check --no-index --ignore-space-change. Runtime behavior after applying it and the missing layout lookup remain open.

~~~diff
--- a/external/ps3recomp/runtime/ppu/ppu_loader.cpp
+++ b/external/ps3recomp/runtime/ppu/ppu_loader.cpp
@@ -3380,13 +3380,20 @@
         ctx->gpr[3] = 0;
         return;
     }
-    case 988:     /* sys_tty_write — canonical LV2 number (psdevwiki); some CRTs
-                   * use this instead of 403. Same ABI. */
+    case 988:     /* Some CRTs also use this number for TTY writes. */
     case 403: {   /* sys_tty_write(s32 ch, cptr buf, u32 len, ptr pwritelen) */
         uint32_t ch   = (uint32_t)ctx->gpr[3];
         uint32_t buf  = (uint32_t)ctx->gpr[4];
         uint32_t len  = (uint32_t)ctx->gpr[5];
         uint32_t pwl  = (uint32_t)ctx->gpr[6];
+        if (num == 988 && !buf) {
+            /* The two-argument PPU exception operation has no TTY buffer. */
+            static int logged = 0;
+            if (PS3_LOG_FIRST(logged, 8))
+                fprintf(stderr, "[ppu] syscall 988 PPU exception operation %u is unavailable\n", ch);
+            ctx->gpr[3] = (uint64_t)(int64_t)(int32_t)0x80010003u; /* CELL_ENOSYS */
+            return;
+        }
         uint32_t wlen = len;
         if (wlen > 0x4000u) {   /* guard against garbage len (divergence dumps memory) */
             static int n = 0;
~~~


### Item 4 offline NP title storage imports

The fixed 1.02 executable imports seven TUS functions the runtime leaves unregistered. The existing create-context function writes a local handle through an output pointer. The firmware title-context call takes three identity pointers and returns the handle. The proposal creates, validates, and destroys title contexts with the firmware ABI. Termination clears the title records.

The current NP manager reports offline without a PSN server. The new transaction and async entries check the applicable arguments and report the offline error. They leave output records intact on failure. An online transaction is reported as unsupported when the title context is valid. [RPCS3 TUS implementation](https://github.com/RPCS3/rpcs3/blob/0ebb63697666a54b44a4de69ef222c4ecee0001a/rpcs3/Emu/Cell/Modules/sceNpTus.cpp#L77) [RPCS3 TUS types](https://github.com/RPCS3/rpcs3/blob/0ebb63697666a54b44a4de69ef222c4ecee0001a/rpcs3/Emu/Cell/Modules/sceNpTus.h)

The exact diff passes git apply --check against the current worktree. The SDK generator detects all seven expected NIDs. The focused fixture checks title ID allocation and reuse, invalid handles, lifecycle, guest-endian slot and option validation, and untouched output on offline errors. See tus-owner-proposal-codex.log. Full-build and live dispatch verification require the module owner's integration.

### Requests for Claude

Apply the proposed sceNpTus.c change and export it as a runtime patch. The normal HLE generator can register the seven names without a port override.

~~~diff
--- a/external/ps3recomp/libs/network/sceNpTus.c
+++ b/external/ps3recomp/libs/network/sceNpTus.c
@@ -7,6 +7,8 @@
  */
 
 #include "sceNpTus.h"
+#include "sceNp.h"
+#include "np_psnr.h"
 #include <stdio.h>
 #include <string.h>
 #include <stdlib.h>
@@ -17,7 +19,42 @@
  * Internal state
  * -----------------------------------------------------------------------*/
 
-static int s_initialized = 0;
+static _Atomic int s_initialized = 0;
+
+enum {
+    TUS_TITLE_BASE = 0x7001,
+    TUS_TITLE_COUNT = 32,
+    TUS_COMMUNICATION_ID_SIZE = 12,
+    TUS_VARIABLE_SIZE = 120,
+    TUS_TRY_SET_OPTION_SIZE = 16,
+};
+
+#define TUS_COMM_INVALID_ARGUMENT 0x8002a104u
+#define TUS_COMM_TOO_MANY_OBJECTS 0x8002a107u
+#define TUS_COMM_INSUFFICIENT_ARGUMENT 0x8002a1a1u
+#define TUS_COMM_INVALID_ID 0x8002a1a3u
+#define TUS_COMM_INVALID_ONLINE_ID 0x8002a1a4u
+#define TUS_COMM_INVALID_ALIGNMENT 0x8002a1acu
+#define TUS_COMM_TOO_MANY_SLOT_IDS 0x8002a1b1u
+
+typedef struct {
+    int in_use;
+    u8 communication_id[TUS_COMMUNICATION_ID_SIZE];
+    SceNpCommunicationPassphrase passphrase;
+} TusTitleContext;
+
+static TusTitleContext s_title_ctx[TUS_TITLE_COUNT];
+static atomic_flag s_title_lock = ATOMIC_FLAG_INIT;
+
+static void lock_title_contexts(void)
+{
+    while (atomic_flag_test_and_set_explicit(&s_title_lock, memory_order_acquire)) {}
+}
+
+static void unlock_title_contexts(void)
+{
+    atomic_flag_clear_explicit(&s_title_lock, memory_order_release);
+}
 
 typedef struct {
     int in_use;
@@ -78,7 +115,10 @@
         }
     }
 
+    lock_title_contexts();
     s_initialized = 0;
+    memset(s_title_ctx, 0, sizeof(s_title_ctx));
+    unlock_title_contexts();
     return CELL_OK;
 }
 
@@ -334,3 +374,128 @@
     (void)reqId;
     return CELL_OK;
 }
+
+s32 sceNpTusCreateTitleCtx(const void* communicationId, const SceNpCommunicationPassphrase* passphrase,
+                          const SceNpId* selfNpId)
+{
+    lock_title_contexts();
+    s32 result = (s32)SCE_NP_COMMUNITY_ERROR_NOT_INITIALIZED;
+    if (s_initialized) {
+        result = (s32)TUS_COMM_INSUFFICIENT_ARGUMENT;
+        if (communicationId && passphrase && selfNpId) {
+            result = (s32)TUS_COMM_TOO_MANY_OBJECTS;
+            for (s32 i = 0; i < TUS_TITLE_COUNT; ++i) {
+                TusTitleContext* ctx = &s_title_ctx[i];
+                if (ctx->in_use)
+                    continue;
+                vm_memcpy_from(ctx->communication_id, GUEST_EA(communicationId), sizeof(ctx->communication_id));
+                vm_memcpy_from(&ctx->passphrase, GUEST_EA(passphrase), sizeof(ctx->passphrase));
+                ctx->in_use = 1;
+                result = TUS_TITLE_BASE + i;
+                break;
+            }
+        }
+    }
+    unlock_title_contexts();
+    return result;
+}
+
+s32 sceNpTusDestroyTitleCtx(s32 titleCtxId)
+{
+    const u32 index = (u32)titleCtxId - TUS_TITLE_BASE;
+    lock_title_contexts();
+    s32 result = (s32)SCE_NP_COMMUNITY_ERROR_NOT_INITIALIZED;
+    if (s_initialized) {
+        result = (s32)TUS_COMM_INVALID_ID;
+        if (index < TUS_TITLE_COUNT && s_title_ctx[index].in_use) {
+            memset(&s_title_ctx[index], 0, sizeof(s_title_ctx[index]));
+            result = CELL_OK;
+        }
+    }
+    unlock_title_contexts();
+    return result;
+}
+
+s32 sceNpTusCreateTransactionCtx(s32 titleCtxId)
+{
+    if (!s_initialized)
+        return (s32)SCE_NP_COMMUNITY_ERROR_NOT_INITIALIZED;
+    if (!np_psnr_enabled())
+        return (s32)TUS_COMM_INVALID_ONLINE_ID;
+    const u32 index = (u32)titleCtxId - TUS_TITLE_BASE;
+    lock_title_contexts();
+    const int valid = s_initialized && index < TUS_TITLE_COUNT && s_title_ctx[index].in_use;
+    unlock_title_contexts();
+    return valid ? (s32)CELL_ENOSYS : (s32)TUS_COMM_INVALID_ID;
+}
+
+s32 sceNpTusDestroyTransactionCtx(s32 transId)
+{
+    (void)transId;
+    if (!s_initialized)
+        return (s32)SCE_NP_COMMUNITY_ERROR_NOT_INITIALIZED;
+    return (s32)TUS_COMM_INVALID_ID;
+}
+
+static s32 validate_tus_slot_ids(const u32* slotIds, s32 count)
+{
+    if (count > SCE_NP_TUS_MAX_SLOT_NUM)
+        return (s32)TUS_COMM_TOO_MANY_SLOT_IDS;
+    for (s32 i = 0; i < count; ++i) {
+        if ((s32)vm_read32(GUEST_EA(slotIds) + (u32)i * 4) < 0)
+            return (s32)TUS_COMM_INVALID_ARGUMENT;
+    }
+    return CELL_OK;
+}
+
+static s32 tus_async_network_error(const SceNpId* targetNpId)
+{
+    if (!s_initialized)
+        return (s32)SCE_NP_COMMUNITY_ERROR_NOT_INITIALIZED;
+    if (!targetNpId)
+        return (s32)TUS_COMM_INSUFFICIENT_ARGUMENT;
+    return np_psnr_enabled() ? (s32)TUS_COMM_INVALID_ID : (s32)TUS_COMM_INVALID_ONLINE_ID;
+}
+
+s32 sceNpTusSetMultiSlotVariableAsync(s32 transId, const SceNpId* targetNpId, const u32* slotIds,
+                                     const s64* variables, s32 count, const void* option)
+{
+    (void)transId;
+    if (!slotIds || !variables)
+        return (s32)TUS_COMM_INSUFFICIENT_ARGUMENT;
+    if (count <= 0 || option)
+        return (s32)TUS_COMM_INVALID_ARGUMENT;
+    const s32 status = validate_tus_slot_ids(slotIds, count);
+    return status ? status : tus_async_network_error(targetNpId);
+}
+
+s32 sceNpTusGetMultiSlotVariableAsync(s32 transId, const SceNpId* targetNpId, const u32* slotIds,
+                                     void* variables, u32 variableSize, s32 count, const void* option)
+{
+    (void)transId;
+    if (!slotIds || !variables)
+        return (s32)TUS_COMM_INSUFFICIENT_ARGUMENT;
+    if (count <= 0 || option)
+        return (s32)TUS_COMM_INVALID_ARGUMENT;
+    if (variableSize != (u64)count * TUS_VARIABLE_SIZE)
+        return (s32)TUS_COMM_INVALID_ALIGNMENT;
+    const s32 status = validate_tus_slot_ids(slotIds, count);
+    return status ? status : tus_async_network_error(targetNpId);
+}
+
+s32 sceNpTusTryAndSetVariableAsync(s32 transId, const SceNpId* targetNpId, s32 slotId, s32 operation,
+                                   s64 value, void* variable, u32 variableSize, const void* option)
+{
+    (void)transId;
+    (void)operation;
+    (void)value;
+    if (!s_initialized)
+        return (s32)SCE_NP_COMMUNITY_ERROR_NOT_INITIALIZED;
+    if (!variable)
+        return (s32)TUS_COMM_INSUFFICIENT_ARGUMENT;
+    if (slotId < 0)
+        return (s32)TUS_COMM_INVALID_ARGUMENT;
+    if (variableSize != TUS_VARIABLE_SIZE || (option && vm_read32(GUEST_EA(option)) != TUS_TRY_SET_OPTION_SIZE))
+        return (s32)TUS_COMM_INVALID_ALIGNMENT;
+    return tus_async_network_error(targetNpId);
+}
~~~


### Item 4 offline SSL certificate imports

The current offline backend supplies no peer certificates. Five certificate getters are missing from its dispatch table. The proposal gives those exports the firmware calling conventions and returns the SSL error for an uninitialized module, missing output argument, or invalid certificate. It also corrects the initialization and repeated-init error constants. Failed queries preserve the guest output. [RPCS3 SSL implementation](https://github.com/RPCS3/rpcs3/blob/0ebb63697666a54b44a4de69ef222c4ecee0001a/rpcs3/Emu/Cell/Modules/cellSsl.cpp#L175) [RPCS3 SSL errors](https://github.com/RPCS3/rpcs3/blob/0ebb63697666a54b44a4de69ef222c4ecee0001a/rpcs3/Emu/Cell/Modules/cellSsl.h)

The scratch fixture checks all five exports across initialization, null certificates, missing output pointers, and complete arguments with no live certificate. The HLE generator finds all five expected NIDs. See ssl-owner-proposal-codex.log. Live dispatch remains unverified for this patch.

The current imp7 snapshot still has 66 gaps. A combined scratch replay applies the SSL, UCS-2, TUS, and syscall 988 proposals across six files. The generated table and explicit port registrations account for 14 of the 66 gaps after integration. See registered-nids-imp7-codex.log and pending-peripheral-owner-replay-codex.log.

### Requests for Claude

Apply the SSL hunks together. The normal HLE generator detects the five exports.

~~~diff
--- a/external/ps3recomp/libs/network/cellSsl.c
+++ b/external/ps3recomp/libs/network/cellSsl.c
@@ -136,3 +136,39 @@
 
     return CELL_OK;
 }
+
+/* The offline backend never creates a peer certificate. Check the public ABI
+ * parameters without reading a guest handle or modifying failed outputs. */
+static s32 ssl_no_peer_certificate(const void* certificate, int has_output)
+{
+    if (!s_ssl_initialized)
+        return (s32)CELL_SSL_ERROR_NOT_INITIALIZED;
+    if (certificate && !has_output)
+        return (s32)CELL_SSL_ERROR_NO_BUFFER;
+    return (s32)CELL_SSL_ERROR_INVALID_CERTIFICATE;
+}
+
+s32 cellSslCertGetRsaPublicKeyModulus(const void* certificate, const u8** data, u64* length)
+{
+    return ssl_no_peer_certificate(certificate, data && length);
+}
+
+s32 cellSslCertGetRsaPublicKeyExponent(const void* certificate, const u8** data, u64* length)
+{
+    return ssl_no_peer_certificate(certificate, data && length);
+}
+
+s32 cellSslCertGetSubjectName(const void* certificate, const void** name)
+{
+    return ssl_no_peer_certificate(certificate, name != NULL);
+}
+
+s32 cellSslCertGetIssuerName(const void* certificate, const void** name)
+{
+    return ssl_no_peer_certificate(certificate, name != NULL);
+}
+
+s32 cellSslCertGetMd5Fingerprint(const void* certificate, u8* fingerprint, u32* length)
+{
+    return ssl_no_peer_certificate(certificate, fingerprint && length);
+}
--- a/external/ps3recomp/libs/network/cellSsl.h
+++ b/external/ps3recomp/libs/network/cellSsl.h
@@ -18,8 +18,10 @@
 /* ---------------------------------------------------------------------------
  * Error codes
  * -----------------------------------------------------------------------*/
-#define CELL_SSL_ERROR_NOT_INITIALIZED       0x80720101
-#define CELL_SSL_ERROR_ALREADY_INITIALIZED   0x80720102
+#define CELL_SSL_ERROR_NOT_INITIALIZED       0x80740001
+#define CELL_SSL_ERROR_ALREADY_INITIALIZED   0x80740002
+#define CELL_SSL_ERROR_NO_BUFFER             0x80740004
+#define CELL_SSL_ERROR_INVALID_CERTIFICATE   0x80740005
 #define CELL_SSL_ERROR_INVALID_ARG           0x80720103
 #define CELL_SSL_ERROR_NO_MEMORY             0x80720104
 #define CELL_SSL_ERROR_HANDSHAKE_FAILED      0x80720105
@@ -43,6 +45,11 @@
 s32 cellSslCertGetPublicKey(CellSslCertId certId, u8* key, u32* keySize);
 s32 cellSslCertGetNotBefore(CellSslCertId certId, u64* time);
 s32 cellSslCertGetNotAfter(CellSslCertId certId, u64* time);
+s32 cellSslCertGetRsaPublicKeyModulus(const void* certificate, const u8** data, u64* length);
+s32 cellSslCertGetRsaPublicKeyExponent(const void* certificate, const u8** data, u64* length);
+s32 cellSslCertGetSubjectName(const void* certificate, const void** name);
+s32 cellSslCertGetIssuerName(const void* certificate, const void** name);
+s32 cellSslCertGetMd5Fingerprint(const void* certificate, u8* fingerprint, u32* length);
 
 /* Entropy / RNG */
 s32 cellSslGetRandomNumber(u8* buf, u32 size);
~~~


### Item 1 patch replay through 0040

The scratch replay applied all 32 runtime patches, including 0040-rsx-impact-reflect.patch. Of 43 compared files, 10 match byte for byte and 33 differ only in line endings. The replay used LF scratch copies of 0026 and 0027. See patch-replay-0040-codex.log.


### Item 2 portability evidence after cleanup

The relocated 7bcf370f no-flags check still has its summary and boot log. They record executable-relative paths, a clean guest exit, and an empty launch directory. The file and registry trace logs cited in the earlier portability entry were removed during cleanup. The recorded trace counts and the owner's Windows and NVIDIA allowance remain in that entry.


### Item 4 RTC week offsets awaiting a build

The imp8 dispatch snapshot shows cellRtcTickAddWeeks (0x64C63FD5) missing. The port now registers a handler in port/stubs.cpp that validates its guest buffers and reuses the existing RTC tick arithmetic. The one direct caller passes a stack destination and an input tick from its data area.

The RTC fixture and build timed out while waiting for the lead's 14:45:19 BUILD.lock. See rtc-weeks-resumed-codex.log. The source change still needs compilation and live dispatch verification.
