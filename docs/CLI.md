# Command-line options

Run `HotShotsGolfRecomp [options] [path/to/EBOOT.elf]`.

Command-line flags take precedence over environment variables. Default paths start next to the executable or in the folder selected with `--build-dir`.

Flags accept `--flag value` or `--flag=value`.
Explicit relative paths resolve from the launch directory. The process uses the build folder for internal relative paths.

| Flag | Environment | Default | What it does | Status |
|---|---|---|---|---|
| `--elf <file>` | none | `<game-dir>/USRDIR/EBOOT.elf` | PPU ELF to boot. A bare path with no flag does the same. | wired |
| `--build-dir <dir>` | none | Executable folder | Base folder for game discovery and runtime storage. | wired |
| `--game-dir <dir>` | `PS3_VFS_ROOT` | `<build dir>/game` or `<build dir>` | Game folder (VFS root). Holds `PARAM.SFO` and `USRDIR/`. | wired |
| `--hdd0 <dir>` | `PS3_HDD0_ROOT` | `<build dir>/hdd0` | Host folder for `/dev_hdd0`. | wired |
| `--hdd1 <dir>` | `PS3_HDD1_ROOT` | `<build dir>/hdd1` | Host folder for `/dev_hdd1`. | wired |
| `--savedata <dir>` | `PS3_SAVEDATA_ROOT` | `<build dir>/savedata` | Root for the save tree. | wired |
| `--dev-flash <dir>` | `PS3_DEV_FLASH` | `<build dir>/dev_flash` | Firmware folder. | wired |
| `--title <text>` | `PS3_TITLE` | `TITLE` from `PARAM.SFO` | Window caption. | wired |
| `--fullscreen` | none | off | Cover the primary monitor with a borderless window on Windows. | wired |
| `--windowed` | none | on | Start in a window. | wired (default) |
| `--width <px>` | none | 1280 | Render surface and windowed client width. | wired |
| `--height <px>` | none | 720 | Render surface and windowed client height. | wired |
| `--verbose <n>` | `PS3_VERBOSE` | 0 | Use 0 for normal logs or 1 through 9 to enable additional runtime diagnostics. | wired |
| `--log <file>` | none | console | Send output to a file. A bare name goes in `<build dir>/logs`. | wired |
| `--hidden` | none | off | Create a hidden window that cannot take focus on Windows. | wired |
| `--exit-after <sec>` | none | off | Quit cleanly (same path as the console's Quit Game) after this many seconds. | wired |
| `--help` | none | | Print the option list. | wired |
| `--version` | none | | Print the version. | wired |

`--fullscreen` and `--windowed` cannot be used together.

The local PS3 user's saves live in `dev_hdd0/home/00000001/savedata` under the save root. The older `PS3_GAMEDATA_ROOT` variable also works when no save root is specified.

The US font set uses `data/font/SCE-PS3-RD-R-LATIN2.TTF` under the firmware folder. Supply it from a local firmware dump.

## Game files

Put the extracted US game files in the `game` folder next to the executable. The folder needs `PARAM.SFO` and `USRDIR/EBOOT.elf` from the inputs for the fixed 1.02 build. The launcher also checks for both files directly next to the executable. An alternate game root can contain the same layout under `PS3_GAME`.

The executable reads the title ID from `PARAM.SFO` and starts the game. If a startup file is missing or the title ID cannot be read, it prints a setup message and exits with code 1. A fresh Explorer console waits for Enter so the message stays visible.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Normal exit, `--help`, `--version`, or `--exit-after` |
| 1 | Game files or `PARAM.SFO` missing, ELF failed to load, log file not writable |
| 2 | Bad command-line option |
