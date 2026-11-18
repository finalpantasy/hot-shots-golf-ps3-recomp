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
