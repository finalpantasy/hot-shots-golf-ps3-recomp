# Hot Shots Golf: World Invitational recompilation

- Goal: a native static recompilation of the US PS3 release `NPUA80864` from the user's own base game, updates, DLC, and fix packages.
- The user authorized implementation to resume on 2026-11-17. Preserve original packages, reject incomplete downloads from build inputs, and stage extracted content separately from the originals.
- Research and the selected toolchain are in `docs/research/ps3-static-recompilation-tooling.md`.
- The ranked repository survey is in `docs/research/ps3-recomp-repository-survey.md`; the implementation process derived from it is in `docs/recomp-process.md`.
- Default route: `sp00nznet/ps3recomp` v0.19.0, RPCS3 as the behavioral reference, and REA/Ghidra for targeted analysis of decrypted PPU/SPU binaries. REA currently rejects PowerPC machine 21 on this host, so use ps3recomp's PPC tools as the working fallback and preserve that limitation.
- Official 1.03 is decrypted at `work/extracted/update-1.03/USRDIR/EBOOT.elf` (SHA-256 `8cb18c2ec06c8a0ed2de12d3dd3bdd09caa36af55d49c18a869dbac0f52e140b`). Its independent pipeline is `pipeline-1.03.toml`; preserve the fixed-1.02 baseline and verify the official 1.03 build separately.
- Exclude `HP9000-NPHA80248`: it is the separate Asian Everybody's Golf 6 release, not the US target.
- Run stages with `.venv/Scripts/python.exe tools/recomp_pipeline.py analyze lift build`; the lock is `config/generated.lock` and current evidence is in `docs/STATUS.md`.
- Do not substitute Vita `pkg2zip` or the PSP Hot Shots Tennis matching decomp for this PS3 static-recompilation toolchain.
- Measure progress by runtime milestones, not lifted-function counts. Keep observations, inferences, and unknowns separate.
- Keep game assets, packages, keys, licenses, generated game code, and shader microcode out of source control. Preserve upstream license and attribution requirements.
