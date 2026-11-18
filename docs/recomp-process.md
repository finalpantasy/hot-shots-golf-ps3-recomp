# Hot Shots Golf recompilation process

This is the project-owned implementation of the processes surveyed in `docs/research/ps3-recomp-repository-survey.md`. It takes effect when the user says the rip is complete. Until then, do not inspect or transform game packages.

## 1. Pin every input and tool

Create `config/target.json` before analysis. Record:

- title ID, region, content ID, package role, and version for every input;
- byte size and SHA-256 of each original package;
- whether the package is base, official update, DLC, or third-party fix;
- extracted `EBOOT.BIN`, decrypted ELF, PRX, and SPU image hashes;
- ps3recomp commit, local runtime patch IDs, lifter arguments, compiler, and host target.

Reject incomplete downloads and unsupported executable hashes by default. A deliberate new target requires a new profile, not silent acceptance. Keep base 1.00, updates 1.01/1.02, and DLC in separate staging trees. Do not let fix packages overwrite the official baseline before their content and provenance are recorded.

## 2. Make generation resumable and hash-locked

Use a declarative `pipeline.toml` with these stages:

```text
inventory → extract → decrypt → analyze → lift-ppu → lift-spu
→ capture-jobmods → generate-hle → patch → build → smoke
```

Each stage declares its inputs, command, output directory, and completion receipt. A rerun skips valid completed stages; a changed input invalidates only dependents. Generated files stay local and are never committed.

Maintain `config/generated.lock` containing hashes before and after project patches. Unchanged files retain timestamps to avoid unnecessary recompilation. Do not manually edit generated output: put systematic fixes in the lifter, game-independent fixes in the runtime, and genuine one-offs in clearly separated game patches.

Separate:

- `patches/runtime/`: changes against the pinned ps3recomp revision;
- `patches/lifted/`: deliberate changes to generated game code;
- `src/overrides/`: host-native replacements and fast paths;
- `config/functions.json`: curated boundaries only when automatic analysis is insufficient.

A patch export fails if it contains generated game content rather than a small reproducible edit. This follows the inFAMOUS process without copying its unlicensed implementation.

## 3. Establish binary facts before lifting

Use REA/Ghidra on the decrypted updated EBOOT and PRX files. Record evidence for:

- ELF segments and executable ranges;
- entry OPD, TOC, imports/NIDs, and relocations;
- OPD and heuristic function candidates;
- embedded SPU ELFs and possible streamed-job data;
- middleware and engine strings.

Accept lift-coverage metrics only inside validated executable ranges. Keep bogus data descriptors, unresolved functions, and unhandled instructions as explicit lists. Do not report a single “functions decompiled” percentage as project progress.

Use normalized instruction signatures and call graphs when comparing 1.00, 1.01, 1.02, or another Clap Hanz binary. Shared franchise names alone establish nothing.

## 4. Capture subsystem contracts from the original runtime

For SPURS and other opaque middleware, record a reference run before replacing it:

- PPU calls and arguments;
- command lists, guards, task/workload ordering, and completion events;
- SPU image fingerprints and local-store placement;
- descriptors, DMA, stack setup, and writes visible to PPU code.

Write a bounded contract in `analysis/contracts/`. The replacement must reject unknown opcodes or layouts rather than return fake success. Run original and replacement traces in the same format and compare them.

Use `SPU_DUMP_MISS` for streamed jobs that standalone extraction misses. Track interpreted and lifted execution separately; an interpreter fallback is not static coverage.

## 5. Treat update and DLC installation as transactions

For each update or DLC pack:

1. Verify package identity, region, version, and required license data.
2. Write to a fresh staging directory.
3. Verify EDAT integrity and expected output sizes where applicable.
4. Refuse wrong or missing licenses without leaving partial content.
5. Commit the whole pack atomically and record installed files and replacements.
6. Make a second import a no-op.
7. Test removal and restoration while protecting saves.

Keep update files and DLC overlays visible in the VFS manifest. Do not flatten official and third-party fixes into an untraceable final directory.

## 6. Verify in layers

### Static and lift checks

- Input hashes and ELF layout match `config/target.json`.
- No unhandled instructions inside accepted code ranges.
- Every direct call target is intentional: lifted, HLE, override, or documented missing.
- Every imported NID resolves intentionally; unknown behavior does not silently return `CELL_OK`.

### Job and subsystem checks

- Record real SPU jobs and replay them outside the game.
- Compare original and native/lifted results by registers, local store, and guest writes.
- Keep native fast paths behind an A/B/check switch that can run both versions.
- Compare original and replacement SPURS traces for ordering, descriptors, placement, and events.

### Runtime and rendering checks

- Emit a lightweight ordered milestone stream for imports, LV2 syscalls, file opens, SPU jobs, and RSX paths.
- Compare the same save and scene against RPCS3.
- Capture and replay RSX command streams for rendering regressions.
- Treat guest frames and host overlays as separate evidence. A working launcher or overlay never proves guest rendering.

### Performance checks

- Warm up once after building, then alternate at least three A/B pairs where practical.
- Use the same binary when testing an environment switch and the same save/scene for build comparisons.
- Report median, spread, p99 or 1% lows, and present counts. Do not rely on average FPS alone.
- Check the frame counter before trusting it; duplicate presents are not new rendered frames.
- Record no-gain results so they are not repeated without new evidence.

### Gameplay checks

Use these labels:

- **Lifted:** code generated inside validated ranges. No runtime claim.
- **Boots:** reaches the game entry and initializes without an unresolved boot blocker.
- **Renders:** the guest produces verified pixels, not only a window or overlay.
- **Menu:** the real title/menu accepts input.
- **First playable hole:** one hole can be started, played, scored, and exited with correct input, audio, and save behavior.
- **Playable:** a person completes a representative full playthrough with no known progression-blocking crash or soft-lock, with remaining issues documented.

Do not call the whole game playable from a title screen, one menu, or a lifted-function count.

## 7. Keep diagnostics useful and private

Add a player-triggered log marker once the port runs. A diagnostic bundle should contain:

- build and target hashes;
- recent milestone events and log tail;
- marked frame timings and present counts;
- hardware and renderer information;
- crash or stall details where available.

Scrub usernames and local paths. Never include packages, game code, assets, licenses, keys, or other people's saves.

## 8. Release gates

A preview tag requires a reproducible build, installer test, documented known issues, and published source/tool hashes.

A playable release requires:

- a dated human playthrough log with build ID and issues encountered;
- automated hole/course coverage with save/reload and quit/continue;
- scene comparisons against RPCS3;
- frame pacing and performance measured on named hardware;
- no known progression-blocking crash or soft-lock;
- accurate statements about lifted, interpreted, reimplemented, and native paths;
- no game data or generated game code in the distributed source kit.

## Initial implementation order after the hold ends

1. Target manifest and read-only package inventory.
2. Decrypted 1.02 EBOOT validation and REA evidence.
3. Declarative resumable pipeline and generation lock.
4. PPU/SPU lifting with explicit coverage ledgers.
5. RPCS3 reference traces and first native boot.
6. SPURS contract, streamed-job capture, and replay harness.
7. RSX milestone/capture checks through the first real menu.
8. First playable hole.
9. Transactional update/DLC import and parity checks.
10. Broader playthrough, optimization, and release hardening.
