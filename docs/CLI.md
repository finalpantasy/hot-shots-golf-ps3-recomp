# Command-line options

Usage: `hotshots [options] [path/to/EBOOT.elf]`

For each setting the order is: command-line flag, then environment variable, then the default. Every default path is relative to the folder the executable is in. Nothing is written to AppData, the registry or the current directory.

Flags accept `--flag value` or `--flag=value`.

| Flag | Environment | Default | What it does | Status |
|---|---|---|---|---|
| `--elf <file>` | none | `<game-dir>/USRDIR/EBOOT.elf` | PPU ELF to boot. A bare path with no flag does the same. | wired |
| `--game-dir <dir>` | `PS3_VFS_ROOT` | `<exe dir>/game` | Game folder (VFS root). Holds `PARAM.SFO` and `USRDIR/`. | wired |
| `--hdd0 <dir>` | `PS3_HDD0_ROOT` | `<exe dir>/hdd0` | Host folder for `/dev_hdd0`. | wired |
| `--hdd1 <dir>` | `PS3_HDD1_ROOT` | `<exe dir>/hdd1` | Host folder for `/dev_hdd1`. | wired |
| `--savedata <dir>` | `PS3_SAVEDATA_ROOT` | `<exe dir>/savedata` | Save data folder. The folder is created and exported, but the runtime does not read it yet. | not yet wired |
| `--title <text>` | `PS3_TITLE` | `TITLE` from `PARAM.SFO` | Window caption. | wired |
| `--fullscreen` | none | off | Start fullscreen. Prints a notice and starts windowed. | not yet wired |
| `--windowed` | none | on | Start in a window. | wired (default) |
| `--width <px>` | none | 1280 | Window and render surface width. | wired |
| `--height <px>` | none | 720 | Window and render surface height. | wired |
| `--verbose <n>` | `PS3_VERBOSE` | 0 | Log detail, 0 to 9. Exported to the environment; no runtime code reads it yet. | not yet wired |
| `--log <file>` | none | console | Send all output to a file. A bare name goes in `<exe dir>/logs`. | wired |
| `--hidden` | none | off | Create the window without showing it or taking focus, for automated runs. Uses a window-creation hook and hides the window after init. Not verified on every Windows setup. | wired, best effort |
| `--exit-after <sec>` | none | off | Quit cleanly (same path as the console's Quit Game) after this many seconds. | wired |
| `--help` | none | | Print the option list. | wired |
| `--version` | none | | Print the version. | wired |

`--fullscreen` and `--windowed` cannot be used together.

## Game files

With no flags, put the game in the `game` folder next to the executable. It needs `PARAM.SFO` and `USRDIR/EBOOT.elf`. If the ELF is missing, the program prints which folder to use and exits with code 1.

The title ID (for example `NPUA80864`) is read from `PARAM.SFO` at startup. If `PARAM.SFO` is missing or has no `TITLE_ID`, the program prints an error and exits with code 1. There is no built-in fallback ID.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Normal exit, `--help`, `--version`, or `--exit-after` |
| 1 | Game files or `PARAM.SFO` missing, ELF failed to load, log file not writable |
| 2 | Bad command-line option |
