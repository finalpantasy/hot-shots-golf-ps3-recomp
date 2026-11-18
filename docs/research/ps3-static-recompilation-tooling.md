# Hot Shots Golf: World Invitational — PS3 recompilation tooling research

Research checked on 2026-11-17. Target: the US PS3 release, `NPUA80864`, using the user's own base game, updates, DLC, and fix packages. The rip is still in progress; no further package inspection or extraction is authorized until the user says it is complete.

## Decision

Use **`sp00nznet/ps3recomp` as the primary static-recompilation toolkit**, pinned initially to **v0.19.0** (released 2026-11-06), with **RPCS3 as a behavioral reference** and **REA/Ghidra for targeted PPU/SPU analysis**.

This is a per-game native-port project, not a one-click conversion. Do not equate a high lifted-function count with playability. The useful progress sequence is: valid decrypted ELF → imports resolved → CRT startup → game main → assets loading → SPU/SPURS work completing → RSX frames → menu → input → gameplay → update/DLC parity.

No existing Hot Shots Golf: World Invitational recompilation was found in bounded searches for the title and `NPUA80864`. That is not proof none exists.

An expanded same-day repository ranking and technical comparison is in `docs/research/ps3-recomp-repository-survey.md`. The project-owned process derived from those ports is in `docs/recomp-process.md`.

## Decompilation, recompilation, and assets are different jobs

- **Static recompilation** translates the original machine code ahead of time into generated C/C++, then links it with a native runtime that supplies PS3 operating-system services. This is the requested route.
- **Matching decompilation** reconstructs human-written source and proves it by compiling back to matching original bytes. It is slower and has a different finish line.
- **Dynamic recompilation/emulation** translates code while the game runs. RPCS3 belongs here; it is the reference oracle, not the native-port deliverable.
- **Assets and containers** are inventoried, decoded, and mapped. They are not all “decompiled.” PPU code, SPU code, PRX modules, and RSX shader programs need separate treatment.
- **Updates and DLC** are versioned overlays on the base game, not independent recompilation targets. Fix packages need provenance and content diffs before they are trusted as inputs.

## Recommended tool stack

| Tool | Role here | Why / limits | License |
|---|---|---|---|
| [`sp00nznet/ps3recomp`](https://github.com/sp00nznet/ps3recomp) | Main PPU/SPU lifter, HLE runtime, RSX backend | Best direct fit for a Windows native port. Uses Capstone rather than Ghidra output. Windows game path uses D3D12 and clang-cl. Still requires per-game debugging. | MIT |
| [`RPCS3/rpcs3`](https://github.com/RPCS3/rpcs3) | Reference execution, debugger, API behavior, decrypted ELF/SPU capture | Dynamic emulator, not static recomp. Compare boot behavior, calls, timing-sensitive state, and rendering. Keep its code separate from an MIT port unless licensing is deliberately changed. | Mostly GPL-2.0-only |
| REA + Ghidra | Guided analysis of decrypted EBOOT/PRX/SPU images | Use for functions, xrefs, NID stubs, memory writers, and boot blockers. REA does not replace the ps3recomp lifter. Its current archive opener rejected the official PKG as an unsupported target; the correct next input is a decrypted ELF. | Tool-specific |
| [`clienthax/Ps3GhidraScripts`](https://github.com/clienthax/Ps3GhidraScripts) | PS3 PPU ELF imports, TOC, and syscall naming in Ghidra | README requires big-endian `PowerISA-Altivec-64-32addr`, says relocations are unsupported, and warns of unsupported Cell vector instructions. GitHub metadata showed no license, so do not vendor or redistribute it without permission. | No license detected |
| [`aerosoul94/GhidraSPU`](https://github.com/aerosoul94/GhidraSPU) | SPU processor support in Ghidra | Useful base, but its README says work in progress. Last push shown by GitHub metadata was 2023-07-07. | Apache-2.0 |
| [`eth-man/ps3-cell-re-tools`](https://github.com/eth-man/ps3-cell-re-tools) | Higher-assurance SPU decompiler and differential harness | Its `spu-sleigh` model is checked against an independent SPU emulator. Useful when an SPU job is a blocker; the repository's secure-boot/lv1 tools are otherwise out of scope. | GPL-2.0 |
| [`BitEdits/ps3sce`](https://github.com/BitEdits/ps3sce) | Optional SELF decryption route | Open-source `scetool` replacement. Requires user-supplied keys/support files and, where applicable, license data. RPCS3 dumping or an existing port's installer may be easier. | GPL-3.0 |
| [`soyjxck/dod3-recomp`](https://github.com/soyjxck/dod3-recomp) | Reference implementation for PKG installation, updates, DLC, native optimization, and regression tests | A mature ps3recomp port to study and selectively adapt with attribution; not a dependency to copy wholesale. Its own ps3recomp fork may contain changes not upstream. | MIT |
| [`maceeek/AnyPS3`](https://github.com/maceeek/AnyPS3) | Alternative architecture and test ideas | Linux x86-64 only and currently targets one game. Its fail-closed behavior and SPU interpreter handoff are useful design references, but it is not the best base for this Windows project. | GPL-2.0-only |
| [`miroslavdanutalexandru-alt/shaderscan`](https://github.com/miroslavdanutalexandru-alt/shaderscan) | Optional offline RSX shader-cache work later | Requires a new game/engine front end and a backend matching the port. Not a boot dependency. Keep generated game microcode local. | GPL-2.0-only |

### Explicitly not selected

- [`mmozeiko/pkg2zip`](https://github.com/mmozeiko/pkg2zip) is for **Vita, PSP, PSX, and PSM PKGs**, not these PS3 PKGs. The matching filename extension is misleading.
- [`Jstar269/hst-decomp`](https://github.com/Jstar269/hst-decomp) is a matching decompilation of **Hot Shots Tennis on PSP**, not Hot Shots Golf on PS3. Its MIPS source cannot be dropped into this PPC64 port. It is useful only as an example of exact-match methodology and possibly as a source of high-level Clap Hanz terminology. Its reconstructed source and tools have different path-specific licenses.
- Generic decompiler output should not become thousands of manually maintained generated files. Fix systematic translation bugs in the lifter and use game-specific overrides sparingly.

## What current PS3 recomp projects actually do

### Drakengard 3: proof that the full route can become playable

The [`dod3-recomp` README](https://github.com/soyjxck/dod3-recomp) reports a playable ps3recomp port on Windows/D3D12 and macOS/Metal, with experimental Linux/Vulkan support, update 1.01, and all 20 DLC packs. These are maintainer-reported results, not an independent verification for this project.

Its [technical document](https://github.com/soyjxck/dod3-recomp/blob/main/docs/TECHNICAL.md) describes the useful architecture:

- Lift the PPU EBOOT and each SPU program separately.
- Run a flat 32-bit guest address space inside the 64-bit host process.
- Supply PS3 libraries through HLE and translate the RSX command stream.
- Preserve the update as a complete overlay and map addresses between game versions.
- Add native fast paths only after correctness, with modes that run both lifted and native versions and compare results.
- Capture RSX streams and replay them as rendering regressions.

Its [debugging guide](https://github.com/soyjxck/dod3-recomp/blob/main/docs/DEBUGGING.md) is the best model found for this project's later verification: hands-off runs, frame captures, native-vs-lifted checks, runtime switches for bisecting regressions, and replayed rendering captures.

### Tokyo Jungle: the most relevant warning case

[`sp00nznet/tokyojungle`](https://github.com/sp00nznet/tokyojungle) is a same-era Sony PSN 3D title and therefore a useful process reference, although Hot Shots Golf's engine is not yet known.

Its README reports 7,924 PPU functions and 12 SPU images lifted, successful data installation and asset opens, SPURS execution, and RSX clears—but no geometry or gameplay. It also documents an earlier inflated function count caused by treating basic blocks as functions. Two lessons transfer directly:

1. Runtime SPU capture (`SPU_DUMP_MISS`) can be necessary because streamed job modules are not all present as standalone ELFs.
2. Function coverage and successful compilation do not demonstrate game behavior.

### flOw: lifting everything is not finishing the port

[`sp00nznet/flow`](https://github.com/sp00nznet/flow) reports over 100,000 lifted functions and substantial PhyreEngine/RSX initialization, yet its own status still lists the title-state machine and full gameplay as incomplete. Treat its technical discoveries as leads to verify against current ps3recomp, not as instructions to reproduce old per-game workarounds.

### AnyPS3: useful fail-closed and fallback design

[`AnyPS3`](https://github.com/maceeek/AnyPS3) reports booting Ratchet & Clank: A Crack in Time into a rendered first level on Linux. It translates PPU/SPU ahead of time but retains an exact SPU interpreter for runtime-only overlays and stops explicitly on unsupported states. Current ps3recomp also documents an SPU interpreter/lifted-code handoff in its [getting-started guide](https://github.com/sp00nznet/ps3recomp/blob/master/docs/GETTING_STARTED.md). A fallback is useful for bring-up, but interpreted coverage must be measured rather than silently called fully static.

## Recommended project workflow after the rip is finished

### 1. Freeze and identify inputs

- Hash every supplied package and preserve originals read-only.
- Separate base game, official 1.01/1.02 updates, DLC, and third-party fixes. The filenames indicate 1.02 is the newest update, but verify package metadata and content hashes.
- Reject incomplete downloads from the build manifest.
- Extract each package into its own staging directory; never overwrite base files with fixes before recording their diffs.
- Keep game data, keys, licenses, generated lifts, and shader microcode out of source control.

### 2. Obtain and validate the updated executable

- Produce the decrypted 1.02 `EBOOT.ELF` and any game PRX modules.
- Verify ELF64, big-endian PowerPC, expected segments, entry OPD, and module TOC before lifting.
- Use RPCS3's documented dump route or a user-supplied-key tool such as `ps3sce`. Study `dod3-recomp`'s installer if a local automated PKG/SELF path is warranted.

### 3. Analyze with REA before generating the port

- Open the decrypted ELF with REA/Ghidra and record Evidence IDs for the image layout, imports, entry point, and representative functions.
- Resolve OPD functions, import NIDs, TOC use, PRX dependencies, embedded SPU ELFs, and meaningful engine/middleware strings.
- Use `Ps3GhidraScripts` locally if compatible; do not assume its decompilation is complete.
- Do not infer the engine from the franchise or publisher. Confirm it from the shipped binary and data.

### 4. Establish the reference behavior

- Run the user's copy in RPCS3 with focused logging once the rip is ready.
- Record loaded modules, unresolved APIs, SPU images, file paths, and the expected boot/menu sequence.
- Use targeted runtime evidence to answer static unknowns; do not treat verbose logs as timing-neutral. Tokyo Jungle and ps3recomp's regression documentation both warn that heavy logging changes execution.

### 5. Generate the first native scaffold

Follow the current [ps3recomp getting-started pipeline](https://github.com/sp00nznet/ps3recomp/blob/master/docs/GETTING_STARTED.md):

1. `ppu_loader.py` for functions, imports, image, and loader manifests.
2. `ppu_lifter.py --hle-stubs` for PPU C++.
3. `gen_hle_nids.py` for the NID handler table.
4. SPU discovery/lifting, with runtime miss capture for streamed jobs.
5. CMake/Ninja/clang-cl on Windows, using `/bigobj` for lifted translation units.

Both the HLE stubs and generated NID table are required. Omitting either can produce the same misleading unresolved indirect call to `0x39800000`.

### 6. Advance by observable milestones

Use a small event/milestone stream rather than judging only screenshots or function counts. ps3recomp's [regression-gate design](https://github.com/sp00nznet/ps3recomp/blob/master/docs/REGRESSION_GATE.md) compares first occurrences and counts of firmware imports, LV2 syscalls, and RSX paths. It also documents cold-run and stateful-install pitfalls.

Suggested gates:

1. Native runtime and synthetic tests pass without game data.
2. Recompiled CRT reaches the game's main entry.
3. All boot imports resolve intentionally; no silent success stubs for unknown behavior.
4. Base-game files open through the VFS and worker threads run.
5. SPU/SPURS jobs complete with zero unexplained dispatch misses.
6. RSX clear, then real geometry, then title/menu rendering.
7. Input, audio, saves, and a playable hole.
8. Apply 1.02 and DLC overlays; compare against the equivalent RPCS3 configuration.
9. Optimize and add native fast paths only with differential checks.

### 7. Keep analysis durable

For each blocker, record: guest address/module, evidence ID or runtime trace, expected writer/callee, current hypothesis, next probe, and resolution. Retract superseded conclusions rather than leaving old “current status” notes beside new ones.

Some ps3recomp documentation contains stale sections—for example, parts of the porting guide lag the current renderer—so prefer the pinned release source, current port technical notes, and observed behavior over any single README status table.

## Initial repository shape when implementation resumes

```text
external/ps3recomp/       # pinned upstream source/submodule
input/                    # user-supplied packages; local only
analysis/                 # manifests, REA notes/evidence exports; no game bytes
src/                      # game-specific runner and deliberate overrides
tools/                    # project-owned automation
generated/                # lifted output; local only
docs/research/            # this research and future findings
```

Do not install or clone the full stack until the user resumes implementation. The immediate deliverable of this pass is the researched tool choice and workflow, not a partially extracted game.
