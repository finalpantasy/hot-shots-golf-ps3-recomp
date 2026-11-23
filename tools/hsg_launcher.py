#!/usr/bin/env python3
"""Hot Shots Golf: World Invitational (PC recompilation) settings launcher.

Small Tkinter GUI, standard library only. It reads and writes hsg_settings.json
and starts HotShotsGolfRecomp.exe with the matching flags and environment.

    python tools/hsg_launcher.py                  open the settings window
    python tools/hsg_launcher.py --print-command  print the command and env, do not launch
    python tools/hsg_launcher.py --run            launch from the saved settings
    --settings <file or folder>                   use another settings file or folder
    --exe <file>                                  override the saved exe path for this run

Every launch writes the game's stdout/stderr to logs/run-<date-time>.log beside the
settings file (the newest 10 are kept), ending with the exit code.

Where each setting comes from (checked against the sources, nothing invented):
  Command-line flags: port/cli_options.cpp (parser and --help text) and docs/CLI.md.
  HSG_TWEAKS:         patches/runtime/0059-guest-tweaks.patch (libs/system/hsg_tweaks.c).
  HSG_FPS:            patches/runtime/0058 (30 = off, 60/90/120 on the course).
  HSG_DLC_EARN:       patches/runtime/0070 (DLC club/ball classes 3-4 sold in the shop;
                      on by default but only acts with PS3_NPDRM_STRICT=1;
                      "dlc_earn": false passes =0).
  --aspect expand:    patches/runtime/0055 (Hor+ ultrawide).
"""
import argparse
import json
import os
import shlex
import subprocess
import sys
import threading
import time

SETTINGS_NAME = "hsg_settings.json"
EXE_NAME = "HotShotsGolfRecomp.exe"
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# (label, width, height). Presets for the resolution list.
# Source: --width / --height, port/cli_options.cpp (accepted range 160..16384).
RESOLUTIONS = [
    ("1280x720", 1280, 720),
    ("1920x1080", 1920, 1080),
    ("2560x1440", 2560, 1440),
    ("3840x2160", 3840, 2160),
    ("3440x1440", 3440, 1440),
    ("5120x1440", 5120, 1440),
    ("Custom", 0, 0),
]
# Source: --aspect, port/cli_options.cpp line "stretch (default) or fit"; env RSX_ASPECT.
# "expand" = Hor+ ultrawide (patch 0055).
ASPECTS = ["stretch", "fit", "expand"]
EXPERIMENTAL_ASPECTS = set()
# Source: --windowed (default), --fullscreen, --hidden in port/cli_options.cpp.
WINDOW_MODES = ["windowed", "fullscreen", "hidden"]
# FPS: HSG_FPS is not read by any code in this repo yet. It is exported only when
# the player picks a value other than "Default", and current builds ignore it.
FPS_CHOICES = ["Default", "30", "60", "90", "120"]

DEFAULTS = {
    "exe": "",                # blank = look for the exe (see find_exe)
    "resolution": "1280x720",
    "width": 1280,            # used when resolution == "Custom"
    "height": 720,
    "aspect": "stretch",
    "window_mode": "windowed",
    "tex_replace": "",        # --tex-replace <dir>   (port/cli_options.cpp, patch 0047)
    "tex_replace_mb": 768,    # --tex-replace-mb      (docs/CLI.md default 768)
    "tex_dump": "",           # --tex-dump <dir>      (port/cli_options.cpp, patch 0047)
    "fps": "Default",         # HSG_FPS               (patch 0058)
    "tweaks": "",             # HSG_TWEAKS=<json>     (patch 0059)
    "mute": False,            # --mute                (port/cli_options.cpp)
    "dlc_earn": True,         # HSG_DLC_EARN=0 when off (patch 0070)
    # Paths. Blank means "use the exe's default" from docs/CLI.md and no flag is passed.
    "elf": "",                # --elf        default <game-dir>/USRDIR/EBOOT.elf
    "game_dir": "",           # --game-dir   default <build dir>/game or <build dir>
    "hdd0": "",               # --hdd0       default <build dir>/hdd0
    "hdd1": "",               # --hdd1       default <build dir>/hdd1
    "savedata": "",           # --savedata   default <build dir>/savedata
    "dev_flash": "",          # --dev-flash  default <build dir>/dev_flash
    "extra_args": "",         # free text, appended as-is (hides nothing that exists)
}
PATH_DEFAULT_HINT = {
    "elf": "<game dir>/USRDIR/EBOOT.elf",
    "game_dir": "<exe folder>/game, or the exe folder",
    "hdd0": "<exe folder>/hdd0",
    "hdd1": "<exe folder>/hdd1",
    "savedata": "<exe folder>/savedata",
    "dev_flash": "<exe folder>/dev_flash",
}
PATH_FLAG = {"elf": "--elf", "game_dir": "--game-dir", "hdd0": "--hdd0",
             "hdd1": "--hdd1", "savedata": "--savedata", "dev_flash": "--dev-flash"}


# ---------------------------------------------------------------- settings file

def settings_path(arg=None):
    """File given, or folder given, or hsg_settings.json beside the launcher/repo."""
    if arg:
        arg = os.path.abspath(arg)
        if os.path.isdir(arg) or not arg.lower().endswith(".json"):
            return os.path.join(arg, SETTINGS_NAME)
        return arg
    for d in (HERE, ROOT):
        p = os.path.join(d, SETTINGS_NAME)
        if os.path.isfile(p):
            return p
    return os.path.join(HERE, SETTINGS_NAME)


def load_settings(path):
    s = dict(DEFAULTS)
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for k, v in data.items():
            if k in DEFAULTS:           # ignore unknown keys
                s[k] = v
    return s


def save_settings(path, s):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    clean = {k: s.get(k, DEFAULTS[k]) for k in DEFAULTS}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(clean, f, indent=2)
        f.write("\n")


# ------------------------------------------------------------------- resolution

def find_exe(s, settings_file):
    """Saved path, then next to the settings file, then the project's build folders."""
    if s.get("exe"):
        return os.path.abspath(os.path.join(os.path.dirname(settings_file), s["exe"]))
    cands = [os.path.join(os.path.dirname(settings_file), EXE_NAME)]
    for b in ("official-1.03", "fix-1.02"):
        cands.append(os.path.join(ROOT, "build", b, EXE_NAME))
    for c in cands:
        if os.path.isfile(c):
            return os.path.abspath(c)
    return os.path.abspath(cands[0])


def _abs(base, p):
    return os.path.abspath(os.path.join(base, p)) if p else ""


def resolve_size(s):
    for label, w, h in RESOLUTIONS:
        if label == s["resolution"] and w:
            return w, h
    return int(s["width"]), int(s["height"])


def effective_elf(s, exe, base):
    """The ELF the exe will boot: --elf, else <game-dir>/USRDIR/EBOOT.elf (docs/CLI.md)."""
    if s["elf"]:
        return _abs(base, s["elf"])
    exe_dir = os.path.dirname(exe)
    game = _abs(base, s["game_dir"]) if s["game_dir"] else None
    if game is None:
        g = os.path.join(exe_dir, "game")
        game = g if os.path.isdir(g) else exe_dir
    return os.path.join(game, "USRDIR", "EBOOT.elf")


def validate(s, settings_file):
    """Return (errors, warnings) as lists of plain-English strings."""
    errs, warns = [], []
    base = os.path.dirname(os.path.abspath(settings_file))
    exe = find_exe(s, settings_file)
    if not os.path.isfile(exe):
        errs.append("The game program was not found: %s\n"
                    "Set the path to %s under Advanced." % (exe, EXE_NAME))
    elf = effective_elf(s, exe, base)
    if not os.path.isfile(elf):
        errs.append("The game file EBOOT.elf was not found: %s\n"
                    "Set the Game folder or the ELF path under Advanced." % elf)
    try:
        w, h = resolve_size(s)
        if not (160 <= w <= 16384 and 160 <= h <= 16384):
            errs.append("Width and height must be between 160 and 16384.")
    except (TypeError, ValueError):
        errs.append("Width and height must be whole numbers.")
    try:
        if int(s["tex_replace_mb"]) <= 0:
            errs.append("The texture budget must be a positive number of MB.")
    except (TypeError, ValueError):
        errs.append("The texture budget must be a whole number of MB.")
    if s["tex_replace"] and not os.path.isdir(_abs(base, s["tex_replace"])):
        errs.append("HD texture folder not found: %s" % _abs(base, s["tex_replace"]))
    if s["tweaks"] and not os.path.isfile(_abs(base, s["tweaks"])):
        errs.append("Tweaks file not found: %s" % _abs(base, s["tweaks"]))
    for k in ("game_dir", "hdd0", "hdd1", "savedata", "dev_flash"):
        if s[k] and not os.path.isdir(_abs(base, s[k])):
            if k in ("hdd0", "hdd1", "savedata"):
                continue            # the game creates these on first run
            errs.append("Folder not found (%s): %s" % (k, _abs(base, s[k])))
    if s["window_mode"] not in WINDOW_MODES:
        errs.append("Unknown window mode: %s" % s["window_mode"])
    if s["aspect"] not in ASPECTS:
        errs.append("Unknown aspect mode: %s" % s["aspect"])
    if s["aspect"] in EXPERIMENTAL_ASPECTS:
        warns.append("Aspect 'expand' is experimental (patch 0055). Builds without it "
                     "reject the option and exit with code 2.")
    if s["fps"] in ("60", "90", "120"):
        warns.append("Frame rates above 30 are opt-in (patch 0058) and apply on the course only.")
    if s["tweaks"]:
        warns.append("Guest tweaks are experimental (patch 0059).")
    if s["extra_args"]:
        try:
            shlex.split(s["extra_args"], posix=False)
        except ValueError as e:
            errs.append("Extra arguments are not valid: %s" % e)
    return errs, warns


def build_command(s, settings_file):
    """Return (argv, env_overrides, cwd). Paths are made absolute so cwd does not matter."""
    base = os.path.dirname(os.path.abspath(settings_file))
    exe = find_exe(s, settings_file)
    argv = [exe]
    env = {}
    w, h = resolve_size(s)
    argv += ["--width", str(w), "--height", str(h)]           # port/cli_options.cpp
    argv += ["--aspect", s["aspect"]]                         # port/cli_options.cpp
    if s["window_mode"] == "fullscreen":
        argv.append("--fullscreen")                           # port/cli_options.cpp
    elif s["window_mode"] == "hidden":
        argv.append("--hidden")                               # port/cli_options.cpp
    if s["tex_replace"]:
        argv += ["--tex-replace", _abs(base, s["tex_replace"]),   # patch 0047
                 "--tex-replace-mb", str(int(s["tex_replace_mb"]))]
    if s["tex_dump"]:
        argv += ["--tex-dump", _abs(base, s["tex_dump"])]     # patch 0047
    if s["mute"]:
        argv.append("--mute")                                 # port/cli_options.cpp
    for key, flag in PATH_FLAG.items():
        if s[key]:
            argv += [flag, _abs(base, s[key])]
    if s["tweaks"]:
        env["HSG_TWEAKS"] = _abs(base, s["tweaks"])           # patch 0059
    if s["fps"] != "Default":
        env["HSG_FPS"] = s["fps"]                             # patch 0058
    if not s["dlc_earn"]:
        env["HSG_DLC_EARN"] = "0"                             # patch 0070 (default on)
    if s["extra_args"]:
        argv += shlex.split(s["extra_args"], posix=False)
    return argv, env, os.path.dirname(exe)


def format_command(argv, env):
    lines = ["%s=%s" % (k, v) for k, v in sorted(env.items())]
    lines.append(subprocess.list2cmdline(argv))
    return "\n".join(lines)


LOG_KEEP = 10


def open_run_log(settings_file):
    """Open logs/run-<date-time>.log beside the settings file, keeping the newest LOG_KEEP runs.
    Returns (file, path), or (None, None) when the folder cannot be written."""
    d = os.path.join(os.path.dirname(os.path.abspath(settings_file)), "logs")
    try:
        os.makedirs(d, exist_ok=True)
        old = sorted(f for f in os.listdir(d) if f.startswith("run-") and f.endswith(".log"))
        for f in old[:max(0, len(old) - (LOG_KEEP - 1))]:
            try:
                os.remove(os.path.join(d, f))
            except OSError:
                pass
        stamp = time.strftime("%Y-%m-%d_%H-%M-%S")
        path = os.path.join(d, "run-%s.log" % stamp)
        n = 1
        while os.path.exists(path):
            n += 1
            path = os.path.join(d, "run-%s_%d.log" % (stamp, n))
        return open(path, "ab", buffering=0), path
    except OSError:
        return None, None


def launch(s, settings_file, wait=False):
    """Start the game with its stdout/stderr in logs/run-<date-time>.log beside the
    settings file (newest LOG_KEEP kept). A watcher thread appends the exit code."""
    errs, _ = validate(s, settings_file)
    if errs:
        raise RuntimeError("\n".join(errs))
    argv, env, cwd = build_command(s, settings_file)
    full_env = dict(os.environ)
    full_env.update(env)
    log, log_path = open_run_log(settings_file)
    if log is None:
        proc = subprocess.Popen(argv, cwd=cwd, env=full_env)
    else:
        head = format_command(argv, env).replace("\n", "\n[launcher] ")
        log.write(("[launcher] %s\n[launcher] %s\n\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), head)).encode("utf-8"))
        t0 = time.time()
        try:
            proc = subprocess.Popen(argv, cwd=cwd, env=full_env, stdin=subprocess.DEVNULL,
                                    stdout=log, stderr=subprocess.STDOUT)
        except Exception:
            log.close()
            raise

        def watch():
            rc = proc.wait()
            try:
                log.write(("\n[launcher] game exited with code %d (0x%08X) after %.0f s\n"
                           % (rc, rc & 0xFFFFFFFF, time.time() - t0)).encode("utf-8"))
            finally:
                log.close()
        # Not a daemon thread: closing the launcher window still records the exit code.
        threading.Thread(target=watch, name="hsg-log-watch").start()
        proc.log_path = log_path
    if wait:
        proc.wait()
    return proc


# -------------------------------------------------------------------------- GUI

def run_gui(settings_file):
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox

    root = tk.Tk()
    root.title("Hot Shots Golf Launcher")
    state = {"file": settings_file}
    s = load_settings(settings_file)
    V = {}

    def var(key, kind=tk.StringVar):
        V[key] = kind(value=s[key])
        return V[key]

    nb = ttk.Notebook(root)
    nb.pack(fill="both", expand=True, padx=8, pady=8)

    def tab(name):
        f = ttk.Frame(nb, padding=10)
        nb.add(f, text=name)
        f.columnconfigure(1, weight=1)
        return f

    def row_path(f, r, key, label, is_dir=True, hint=""):
        ttk.Label(f, text=label).grid(row=r, column=0, sticky="w", pady=2)
        e = ttk.Entry(f, textvariable=var(key), width=52)
        e.grid(row=r, column=1, sticky="we", padx=4)

        def browse():
            p = (filedialog.askdirectory() if is_dir else filedialog.askopenfilename())
            if p:
                V[key].set(os.path.normpath(p))
        ttk.Button(f, text="Browse", command=browse).grid(row=r, column=2)
        if hint:
            ttk.Label(f, text="Blank = " + hint, foreground="#666").grid(
                row=r + 1, column=1, sticky="w", padx=4)

    # Display
    d = tab("Display")
    ttk.Label(d, text="Resolution").grid(row=0, column=0, sticky="w", pady=2)
    ttk.Combobox(d, textvariable=var("resolution"), state="readonly",
                 values=[r[0] for r in RESOLUTIONS]).grid(row=0, column=1, sticky="w", padx=4)
    ttk.Label(d, text="Custom width / height").grid(row=1, column=0, sticky="w", pady=2)
    cf = ttk.Frame(d)
    cf.grid(row=1, column=1, sticky="w", padx=4)
    ttk.Entry(cf, textvariable=var("width", tk.IntVar), width=7).pack(side="left")
    ttk.Label(cf, text=" x ").pack(side="left")
    ttk.Entry(cf, textvariable=var("height", tk.IntVar), width=7).pack(side="left")
    ttk.Label(d, text="Aspect mode").grid(row=2, column=0, sticky="w", pady=2)
    ttk.Combobox(d, textvariable=var("aspect"), state="readonly",
                 values=["stretch", "fit", "expand (ultrawide)"]).grid(
        row=2, column=1, sticky="w", padx=4)
    V["aspect"].set("expand (ultrawide)" if s["aspect"] == "expand" else s["aspect"])
    ttk.Label(d, text="stretch fills the window. fit keeps 16:9 with black bars. "
                      "expand widens the view on ultrawide screens.",
              foreground="#666", wraplength=520).grid(row=3, column=1, sticky="w", padx=4)
    ttk.Label(d, text="Window").grid(row=4, column=0, sticky="w", pady=2)
    mf = ttk.Frame(d)
    mf.grid(row=4, column=1, sticky="w", padx=4)
    var("window_mode")
    for m in WINDOW_MODES:
        ttk.Radiobutton(mf, text=m, value=m, variable=V["window_mode"]).pack(side="left", padx=4)

    # Textures
    t = tab("Textures")
    row_path(t, 0, "tex_replace", "HD texture pack folder")
    ttk.Label(t, text="Texture budget (MB)").grid(row=2, column=0, sticky="w", pady=2)
    ttk.Spinbox(t, textvariable=var("tex_replace_mb", tk.IntVar), from_=64, to=16384,
                width=8).grid(row=2, column=1, sticky="w", padx=4)
    row_path(t, 3, "tex_dump", "Texture dump folder", hint="off (saves textures for HD pack creation)")

    # Frame rate
    fr = tab("Frame rate")
    ttk.Label(fr, text="Frame rate").grid(row=0, column=0, sticky="w", pady=2)
    ttk.Combobox(fr, textvariable=var("fps"), state="readonly",
                 values=FPS_CHOICES).grid(row=0, column=1, sticky="w", padx=4)
    ttk.Label(fr, text="Sets HSG_FPS. 60, 90 and 120 are opt-in and apply on the course; "
                       "game logic stays at 30. Menus stay at 30.",
              foreground="#a60", wraplength=520).grid(row=1, column=1, sticky="w", padx=4)

    # Advanced
    a = tab("Advanced")
    row_path(a, 0, "exe", "Game program (exe)", is_dir=False, hint="the exe next to this project's build folder")
    row_path(a, 2, "tweaks", "Guest tweaks file (EXPERIMENTAL)", is_dir=False,
             hint="off (HSG_TWEAKS, patch 0059)")
    ttk.Checkbutton(a, text="Mute audio", variable=var("mute", tk.BooleanVar)).grid(
        row=4, column=1, sticky="w", padx=4, pady=2)
    row_path(a, 5, "elf", "EBOOT.elf", is_dir=False, hint=PATH_DEFAULT_HINT["elf"])
    row_path(a, 7, "game_dir", "Game folder", hint=PATH_DEFAULT_HINT["game_dir"])
    row_path(a, 9, "hdd0", "hdd0 folder", hint=PATH_DEFAULT_HINT["hdd0"])
    row_path(a, 11, "hdd1", "hdd1 folder", hint=PATH_DEFAULT_HINT["hdd1"])
    row_path(a, 13, "savedata", "Save data folder", hint=PATH_DEFAULT_HINT["savedata"])
    row_path(a, 15, "dev_flash", "dev_flash folder", hint=PATH_DEFAULT_HINT["dev_flash"])
    ttk.Label(a, text="Extra arguments").grid(row=17, column=0, sticky="w", pady=2)
    ttk.Entry(a, textvariable=var("extra_args"), width=52).grid(row=17, column=1, sticky="we", padx=4)
    ttk.Checkbutton(a, text="Sell DLC clubs and balls (classes 3-4) in the shop when not owned",
                    variable=var("dlc_earn", tk.BooleanVar)).grid(row=18, column=1, sticky="w", padx=4, pady=2)

    status = tk.Text(root, height=7, width=84, wrap="word", state="disabled")
    status.pack(fill="x", padx=8)

    def show(text, color="black"):
        status.config(state="normal", fg=color)
        status.delete("1.0", "end")
        status.insert("end", text)
        status.config(state="disabled")

    def collect():
        out = {}
        for k in DEFAULTS:
            if k in V:
                v = V[k].get()
                out[k] = v
            else:
                out[k] = s[k]
        if out["aspect"].startswith("expand"):
            out["aspect"] = "expand"
        for k in ("width", "height", "tex_replace_mb"):
            try:
                out[k] = int(out[k])
            except (TypeError, ValueError, tk.TclError):
                out[k] = DEFAULTS[k]
        return out

    def check():
        cur = collect()
        errs, warns = validate(cur, state["file"])
        if errs:
            show("ERROR\n" + "\n".join(errs), "#b00")
        else:
            argv, env, _ = build_command(cur, state["file"])
            show("OK\n" + "\n".join(warns + [format_command(argv, env)]), "#060" if not warns else "#a60")
        return cur, errs

    def save():
        cur, _ = check()
        save_settings(state["file"], cur)
        messagebox.showinfo("Saved", "Saved to " + state["file"])

    def play():
        cur, errs = check()
        if errs:
            messagebox.showerror("Cannot start", "\n".join(errs))
            return
        save_settings(state["file"], cur)
        try:
            launch(cur, state["file"])
        except Exception as e:                                # noqa: BLE001
            messagebox.showerror("Launch failed", str(e))

    def choose_folder():
        p = filedialog.askdirectory(title="Folder for " + SETTINGS_NAME)
        if p:
            state["file"] = os.path.join(p, SETTINGS_NAME)
            root.title("Hot Shots Golf Launcher - " + state["file"])
            check()

    bf = ttk.Frame(root)
    bf.pack(fill="x", padx=8, pady=8)
    ttk.Button(bf, text="Check", command=check).pack(side="left")
    ttk.Button(bf, text="Settings folder...", command=choose_folder).pack(side="left", padx=4)
    ttk.Button(bf, text="Save", command=save).pack(side="right")
    ttk.Button(bf, text="Save and Play", command=play).pack(side="right", padx=4)
    root.title("Hot Shots Golf Launcher - " + state["file"])
    check()
    root.mainloop()


# --------------------------------------------------------------------- CLI main

def main(argv=None):
    ap = argparse.ArgumentParser(description="Hot Shots Golf settings launcher")
    ap.add_argument("--settings", help="settings file or folder (default: hsg_settings.json beside the launcher)")
    ap.add_argument("--exe", help="override the exe path for this run")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--print-command", action="store_true", help="print the command and env, do not launch")
    g.add_argument("--run", action="store_true", help="launch from the saved settings, no window")
    a = ap.parse_args(argv)

    sf = settings_path(a.settings)
    if a.print_command or a.run:
        s = load_settings(sf)
        if a.exe:
            s["exe"] = os.path.abspath(a.exe)
        errs, warns = validate(s, sf)
        for w in warns:
            print("warning: " + w, file=sys.stderr)
        for e in errs:
            print("error: " + e, file=sys.stderr)
        if a.print_command:
            cmd, env, _ = build_command(s, sf)
            print(format_command(cmd, env))
            return 1 if errs else 0
        if errs:
            return 1
        return launch(s, sf, wait=True).returncode
    run_gui(sf)
    return 0


if __name__ == "__main__":
    sys.exit(main())
