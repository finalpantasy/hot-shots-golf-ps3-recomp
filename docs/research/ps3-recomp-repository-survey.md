# PS3 decompilation and recompilation repository survey

Checked 2026-11-17. Star counts are a same-day GitHub search snapshot, not a quality score. Compatibility statements below are maintainer-reported unless explicitly described as repository documentation or source inspection. The Hot Shots rip remains untouched.

## Highest-value repositories

| Repository | Stars | Reported state | Why study it |
|---|---:|---|---|
| [`whompay/inFAMOUSreborn`](https://github.com/whompay/inFAMOUSreborn) | 497 | Native inFamous port with local regeneration | Best declarative, hash-locked installer process. No license was detected, so study the process but do not copy its code. |
| [`arnaldolima1/gow-ascension-pc`](https://github.com/arnaldolima1/gow-ascension-pc) | 448 | Maintainer reports a full playthrough; performance and stability work continues | Best recorded-job native verification and detailed milestone history. MIT. |
| [`soyjxck/dod3-recomp`](https://github.com/soyjxck/dod3-recomp) | 348 | Playable Windows/macOS port; Linux experimental; update and DLC supported | Best overall update mapping, renderer replay, settings, and native-vs-lifted checks. MIT. |
| [`timboat/demons-souls-recomp`](https://github.com/timboat/demons-souls-recomp) | 238 | Maintainer reports the whole game playable on desktop platforms | Best long engineering log, reproducible setup, pruning of bogus data functions, and player diagnostic bundles. MIT. |
| [`kastieloficial/RE-Code-Veronica-PS3-HD-Recomp-PC`](https://github.com/kastieloficial/RE-Code-Veronica-PS3-HD-Recomp-PC) | 232 | Maintainer reports a full playthrough and three PSN regional builds | Useful PSN/RAP handling, per-region executables, and explicit unsupported-version checks. MIT. |
| [`SamiEnazi/infamous2-port`](https://github.com/SamiEnazi/infamous2-port) | 195 | Active Windows/Linux port with setup from disc or PSN PKG | Useful small-toolchain setup, native SPU fast paths, and honest performance comparisons that also report weak 1% lows. MIT with additional third-party terms. |
| [`Re-TeRo17/ratchet-tod-recomp`](https://github.com/Re-TeRo17/ratchet-tod-recomp) | 178 | Maintainer reports a full playthrough of version 1.3.0 | Good example of building on DOD3's installer/settings model and tracking frame-rate-sensitive game behavior. MIT. |
| [`undecuple/project-helghast`](https://github.com/undecuple/project-helghast) | 166 | Partly playable Killzone 3 preview | Best explicit release criteria: full human playthrough, chapter sweeps, rendering comparisons, pacing, and known-issue accounting. MIT. |
| [`miroslavdanutalexandru-alt/Resistance-Fall-of-Man-Recomp`](https://github.com/miroslavdanutalexandru-alt/Resistance-Fall-of-Man-Recomp) | 123 | Campaign tested through Cheddar Gorge; later levels unverified | Useful regeneration hooks, offline shader-cache process, and clear distinction between tested and untested content. MIT with separate optional SDK terms. |
| [`andrebrumdev/gow2-recomp`](https://github.com/andrebrumdev/gow2-recomp) | 107 | Rhodes gameplay on macOS/arm64; mobile experimental | Strong cross-platform A/B discipline, curated lift boundaries, lift promotion gates, and guest-versus-overlay acceptance checks. MIT. |
| [`Mava-b/folklore-decomp`](https://github.com/Mava-b/folklore-decomp) | 92 | Maintainer reports playable Windows build, update 1.10 and DLC | Most relevant to Hot Shots: trace-driven SPURS replacement and update/DLC import tests with wrong-license and rollback cases. Despite its name, it is static recompilation, not matching decompilation. MIT. |
| [`llesieur99/rac8-act-decomp`](https://github.com/llesieur99/rac8-act-decomp) and [`rac6-totd-decomp`](https://github.com/llesieur99/rac6-totd-decomp) | 2 each | Early true matching-decompilation workspaces; no completion percentage claimed | Best evidence gates, accepted-versus-nonmatching source policy, and cross-game function-signature method. GPL-3.0. |

Other active parallel efforts found in the same search include [`bc160201983/GoW-Ascension-Recomp`](https://github.com/bc160201983/GoW-Ascension-Recomp) (177 stars), [`rigaz29/Ascension-R`](https://github.com/rigaz29/Ascension-R) (159), [`undecuple/project-pyrrhus`](https://github.com/undecuple/project-pyrrhus) (156), [`bhuiyah/infamous2-recomp`](https://github.com/bhuiyah/infamous2-recomp) (96), and [`MormonFTP-hub/gt5-recomp`](https://github.com/MormonFTP-hub/gt5-recomp) (71). They are worth checking for fixes when Hot Shots hits a shared PS3 subsystem, but the table above covers the most distinct reusable processes inspected in this pass.

## Popular hits that do not belong in the PS3 static-recomp shortlist

- [`Mabec-games/Gran-Turismo-6-PC`](https://github.com/Mabec-games/Gran-Turismo-6-PC) (223 stars) explicitly combines RPCS3 LLVM recompilation with emulation and game-specific patches. Its update-chain and hardware-tuning processes are useful, but it is not the requested standalone static-recomp architecture.
- [`birabittoh/EternalSonataReprise`](https://github.com/birabittoh/EternalSonataReprise) (213 stars) can consume PS3 game data, but its documented executable build requires the Xbox 360 PAL version. It is not a PS3 PPU/SPU recompilation reference.

## Processes worth adopting

### inFAMOUS: reproducible generation instead of committed generated code

The [installer documentation](https://github.com/whompay/inFAMOUSreborn/blob/main/installer/README.md) describes a declarative `infamous.toml`, resumable steps, and `generated.lock` hashes before and after patches. The maintainer export refuses cases where a patch would publish generated content: binary differences, files the pipeline cannot produce, or a patch carrying more than half a file. Unchanged outputs keep their timestamps so downstream compilation stays incremental.

Adopt the mechanism, not the unlicensed source: pin all tool arguments and input hashes, verify generated outputs, and fail if a manual edit should have been a pipeline step.

### Folklore: trace the real subsystem, write its contract, then replace it

[Folklore's SPURS document](https://github.com/Mava-b/folklore-decomp/blob/main/folklore/docs/SPURS.md) records actual calls, command lists, guard semantics, descriptors, local-store placement, events, and stack setup from the real library. That trace became a bounded specification for a native replacement. The project can run Sony libsre and its replacement in the same trace format, and it compares job entries, placements, descriptors, stack frames, and event behavior.

For Hot Shots, use the same sequence for SPURS and other opaque middleware:

1. Capture a reference trace with the original code.
2. Reduce it to the operations and ordering the game actually uses.
3. Fail loudly on behavior outside that contract.
4. Run original and replacement traces against each other.
5. Expand the contract only from new evidence.

[Folklore's DLC process](https://github.com/Mava-b/folklore-decomp/blob/main/folklore/docs/DLC.md) is equally relevant. It treats each pack as all-or-nothing, verifies EDAT block hashes, refuses wrong or missing licenses without writing the pack, rolls back partial imports, makes repeat imports idempotent, and tests removal/restoration. Our update and DLC importer should follow those rules rather than flattening every package into one directory.

### God of War Ascension: replay jobs and correct the measurement before optimizing

The [milestone log](https://github.com/arnaldolima1/gow-ascension-pc/blob/main/docs/MILESTONES.md) records SPU jobs replayed outside the game and checked byte for byte by their writes. Later native geometry modules were checked on hundreds of recorded jobs; an anti-aliasing path was checked over millions of calls. The project also corrected a Vulkan FPS counter that presented frames twice, halving previously reported numbers.

Use job replay for expensive SPU work and validate performance instrumentation before publishing speed claims. A native fast path needs an original-versus-native equality suite, not just a frame-rate improvement.

### Demon's Souls: constrain the input range and keep the whole build reproducible

The [development notes](https://github.com/timboat/demons-souls-recomp/blob/main/docs/NOTES.md) distinguish the real executable range from OPD-like descriptors in rodata/data. Supplying `--code-end` removed thousands of bogus functions and most of the irrelevant generated output. The setup pins ps3recomp, applies separate runtime and lifted-code patches, skips completed stages, and regenerates everything locally. Its F8/REPORT process combines marked frame timings, system information, and a privacy-scrubbed log tail.

For Hot Shots, validate segment flags and code ranges before accepting function counts, and record lift coverage only inside those ranges. Add a user-triggered diagnostic marker and bundle once the port runs.

### Project Helghast and GoW2: define evidence and release labels before implementation

[Project Helghast's release criteria](https://github.com/undecuple/project-helghast/blob/main/docs/RELEASE-CRITERIA.md) do not call a title screen “playable.” A playable release requires a full human campaign playthrough, automated chapter coverage, scene comparisons against RPCS3, frame pacing, no known campaign-path crash or soft-lock, and accurate labeling.

[GoW2](https://github.com/andrebrumdev/gow2-recomp) separately warns that a host overlay is not evidence that the guest rendered pixels. Its performance protocol uses alternating A/B pairs, repeated runs, platform-specific evidence, and unavailable values instead of fake zeroes.

Our first playable-hole milestone and later “playable” label need the same separation. UI drawn by the port never counts as a game-rendering milestone.

### Ratchet matching decompilations: separate candidates from accepted proof

The Ratchet workspaces define [body, placement, and complete-program gates](https://github.com/llesieur99/rac8-act-decomp/blob/master/docs/GATES.md). Only the complete-program gate counts as a match; failed attempts remain in `nonmatching/` with their first difference and reopening condition. Their [cross-game method](https://github.com/llesieur99/rac6-totd-decomp/blob/master/docs/CROSS-GAME.md) compares normalized instruction shapes and call graphs rather than addresses.

Static recompilation does not need byte-identical C output, but the evidence discipline transfers: keep hypotheses separate from accepted findings, retain failed probes with reopening conditions, and use cross-version/cross-game signatures to name shared engine routines. Hot Shots PSP/Vita titles may help with terminology only after a real binary match—not merely because they share the franchise.

## Priority reading order for this project

1. Folklore SPURS and DLC documents.
2. inFAMOUS installer/generation-lock design.
3. DOD3 technical and debugging documents.
4. Demon's Souls engineering notes.
5. God of War Ascension milestones and job-replay work.
6. Project Helghast release criteria and GoW2 cross-platform A/B protocol.
7. Ratchet matching-decompilation evidence gates when shared-function identification becomes useful.

The concrete implementation of these processes for Hot Shots is in `docs/recomp-process.md`.
