# Command-line options

Usage: `hotshots [options] [path/to/EBOOT.elf]`

For each setting the order is: command-line flag, then environment variable, then the default. Every default path is relative to the folder the executable is in. Nothing is written to AppData, the registry or the current directory.

Flags accept `--flag value` or `--flag=value`.
Explicit relative paths resolve from the folder you launch from. The port uses its own folder for internal relative paths.

| Flag | Environment | Default | What it does | Status |
|---|---|---|---|---|
| `--elf <file>` | none | `<game-dir>/USRDIR/EBOOT.elf` | PPU ELF to boot. A bare path with no flag does the same. | wired |
| `--game-dir <dir>` | `PS3_VFS_ROOT` | `<exe dir>/game` | Game folder (VFS root). Holds `PARAM.SFO` and `USRDIR/`. | wired |
| `--hdd0 <dir>` | `PS3_HDD0_ROOT` | `<exe dir>/hdd0` | Host folder for `/dev_hdd0`. | wired |
| `--hdd1 <dir>` | `PS3_HDD1_ROOT` | `<exe dir>/hdd1` | Host folder for `/dev_hdd1`. | wired |
| `--savedata <dir>` | `PS3_SAVEDATA_ROOT` | `<exe dir>/savedata` | Root for the save tree. | wired |
| `--title <text>` | `PS3_TITLE` | `TITLE` from `PARAM.SFO` | Window caption. | wired |
| `--fullscreen` | none | off | Cover the primary monitor with a borderless window on Windows. | wired |
| `--windowed` | none | on | Start in a window. | wired (default) |
| `--width <px>` | none | 1280 | Render surface and windowed client width. | wired |
| `--height <px>` | none | 720 | Render surface and windowed client height. | wired |
| `--verbose <n>` | `PS3_VERBOSE` | 0 | Use 0 for normal logs or 1 through 9 to enable additional runtime diagnostics. | wired |
| `--log <file>` | none | console | Send all output to a file. A bare name goes in `<exe dir>/logs`. | wired |
| `--hidden` | none | off | Create a hidden window that cannot take focus on Windows. | wired |
| `--exit-after <sec>` | none | off | Quit cleanly (same path as the console's Quit Game) after this many seconds. | wired |
| `--help` | none | | Print the option list. | wired |
| `--version` | none | | Print the version. | wired |

`--fullscreen` and `--windowed` cannot be used together.

The local PS3 user's saves live in `dev_hdd0/home/00000001/savedata` under the save root. The older `PS3_GAMEDATA_ROOT` variable also works when no save root is specified.

Optional firmware files go in `dev_flash` next to the executable. Set `PS3_DEV_FLASH` to use a different firmware folder.

## Game files

With no flags, put the game in the `game` folder next to the executable. It needs `PARAM.SFO` and `USRDIR/EBOOT.elf`. If the ELF is missing, the program prints which folder to use and exits with code 1.

The title ID (for example `NPUA80864`) is read from `PARAM.SFO` at startup. If `PARAM.SFO` is missing or has no `TITLE_ID`, the program prints an error and exits with code 1. There is no built-in fallback ID.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Normal exit, `--help`, `--version`, or `--exit-after` |
| 1 | Game files or `PARAM.SFO` missing, ELF failed to load, log file not writable |
| 2 | Bad command-line option |
