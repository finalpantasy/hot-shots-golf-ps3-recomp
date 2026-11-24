#!/usr/bin/env python3
"""Hot Shots Golf PC recompilation: launcher (settings window, editions, profiles, Ultimate setup).

Small Tkinter GUI, standard library only. tools/build_launcher.py freezes it into one
Windows exe (HotShotsGolfLauncher.exe) so players need no Python.

    HotShotsGolfLauncher.exe                       open the settings window
    ... --print-command                            print the command and env, do not launch
    ... --run                                      launch from the saved settings
    --settings <file or folder>                    use another settings file or folder
    --exe <file>                                   override the exe of the chosen edition
    --edition us|ult  --profile NAME               override those two for this run
    --set key=value                                override any top-level setting (repeatable;
                                                   value is JSON, else plain text)
    --out-file <file>                              also write the --print-command text there
    --ultimate-setup <args>                        run tools/build_ultimate_data.py (see its --help)
    --pkg-extract <in.pkg> <out dir>               extract a PS3 PKG (tools/pkg_extract.py)

Editions (two separate game exes, each with its own paths):
  us   Hot Shots Golf: World Invitational (US 1.03). Exe next to the launcher, or
       build/official-1.03 in the repository.
  ult  Ultimate Edition (JP 1.27, English). Exe in ultimate/ next to the launcher, or
       A:/hsg-ultimate/build in the repository. Needs the data made by Ultimate setup.

Every launch writes the game's stdout/stderr to logs/run-<date-time>.log beside the
settings file (the newest 10 are kept), ending with the exit code.

Where each setting comes from (checked against the sources, nothing invented):
  Command-line flags: port/cli_options.cpp (parser and --help text) and docs/CLI.md.
  HSG_TWEAKS:         patches/runtime/0059-guest-tweaks.patch (libs/system/hsg_tweaks.c).
  HSG_FPS:            patches/runtime/0058 + 0074 (30 = off; 31..1000, "unlocked" or
                      "monitor" on the course; logic stays 30 Hz, frames interpolated).
                      The JP 1.27 program (Ultimate edition) has its own address set
                      (patch 0075, picked by libs/system/hsg_program.c).
  D3D12_VSYNC=0:      libs/video/rsx_d3d12_backend.c (present without vsync, tearing
                      allowed: for rates above the display's and VRR displays).
  HSG_DLC_EARN:       patches/runtime/0070 (DLC club/ball classes 3-4 sold in the shop;
                      on by default but only acts with PS3_NPDRM_STRICT=1;
                      "dlc_earn": false passes =0).
  --aspect expand:    patches/runtime/0055 (Hor+ ultrawide).
  --savedata <dir>:   save root; the local user's saves are <root>/dev_hdd0/home/00000001/savedata
                      (docs/CLI.md). A save profile is its own save root; hdd0 is not touched.
"""
import argparse
import copy
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import threading
import time

FROZEN = bool(getattr(sys, "frozen", False))
SETTINGS_NAME = "hsg_settings.json"
EXE_NAME = "HotShotsGolfRecomp.exe"
if FROZEN:
    HERE = os.path.dirname(os.path.abspath(sys.executable))
    ROOT = HERE
    BUNDLE = getattr(sys, "_MEIPASS", HERE)
else:
    HERE = os.path.dirname(os.path.abspath(__file__))
    ROOT = os.path.dirname(HERE)
    BUNDLE = HERE
    if HERE not in sys.path:
        sys.path.insert(0, HERE)

# Dev-tree locations (only used when they exist, and never for a frozen release).
DEV_ULT_DIR = "A:/hsg-ultimate"
DEV_ULT_EXE = DEV_ULT_DIR + "/build/" + EXE_NAME
DEV_JP_UPDATES = "A:/hsg-updates/x/BCJS30089"
DEV_US_UPDATES = "A:/hsg-updates/x/NPUA80864"

EDITIONS = {
    "us": "Hot Shots Golf: World Invitational (US 1.03)",
    "ult": "Ultimate Edition (JP 1.27, English)",
}
ED_KEYS = ["exe", "elf", "game_dir", "hdd0", "hdd1", "savedata", "dev_flash"]
DEFAULT_PROFILE = "Default"

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
# FPS: HSG_FPS (libs/system/hsg_fps.c, patches 0058 and 0074). "30 (stock)" exports
# nothing. Older settings files may hold "Default", "30" or "90"; they still work.
FPS_CHOICES = ["30 (stock)", "60", "120", "144", "165", "180", "240", "Unlocked", "Match monitor"]
FPS_STOCK = ("30 (stock)", "Default", "30", "")


def fps_env(choice):
    """HSG_FPS value for a frame-rate choice, or None for the stock 30."""
    c = str(choice).strip()
    if c in FPS_STOCK:
        return None
    if c == "Unlocked":
        return "unlocked"
    if c == "Match monitor":
        return "monitor"
    if c.isdigit() and 30 < int(c) <= 1000:
        return c
    return None


# True since patch 0075 (HSG_FPS address set for the JP 1.27 program). False greys out the
# Ultimate edition's rates above 30; this one flag controls the env, warning and GUI controls.
ULT_FPS_SUPPORTED = True


def fps_locked(s):
    """True when the frame-rate choice does not apply to the chosen edition."""
    return s["edition"] == "ult" and not ULT_FPS_SUPPORTED


def fps_effective(s):
    """HSG_FPS for the chosen edition: none while the JP 1.27 program ignores it."""
    return None if fps_locked(s) else fps_env(s["fps"])


DEFAULTS = {
    "edition": "us",
    "profile": DEFAULT_PROFILE,
    "profiles": [],           # names of extra save profiles (not "Default")
    "resolution": "1280x720",
    "width": 1280,            # used when resolution == "Custom"
    "height": 720,
    "aspect": "stretch",
    "window_mode": "windowed",
    "tex_enable": False,      # HD texture pack on/off (default off)
    "tex_replace": "",        # --tex-replace <dir>   (port/cli_options.cpp, patch 0047)
    "tex_replace_mb": 768,    # --tex-replace-mb      (docs/CLI.md default 768)
    "tex_dump": "",           # --tex-dump <dir>      (port/cli_options.cpp, patch 0047)
    "fps": "30 (stock)",      # HSG_FPS               (patches 0058, 0074)
    "vsync": True,            # D3D12_VSYNC=0 when off (only with a rate above 30)
    "tweaks": "",             # HSG_TWEAKS=<json>     (patch 0059)
    "mute": False,            # --mute                (port/cli_options.cpp)
    "dlc_earn": True,         # HSG_DLC_EARN=0 when off (patch 0070)
    "extra_args": "",         # free text, appended as-is (hides nothing that exists)
    # Ultimate setup (tools/build_ultimate_data.py). Blank = the default for this install.
    "ult_base": "",           # US base game folder (PARAM.SFO + USRDIR)
    "ult_updates": "",        # extracted JP updates 01.01 .. 01.27
    "ult_us_updates": "",     # extracted US updates 01.01 .. 01.03 (English source, optional)
    "ult_out": "",            # where the Ultimate data is built (game/ and hdd0/)
    "pkg_dir": "",            # folder of JP update .pkg files for the extractor
    # Per-edition paths. Blank means "use the exe's default" (docs/CLI.md) unless found
    # automatically (see eff_path); then no flag is passed.
    "editions": {e: {k: "" for k in ED_KEYS} for e in EDITIONS},
}
GLOBAL_KEYS = [k for k in DEFAULTS if k != "editions"]
PATH_FLAG = {"elf": "--elf", "game_dir": "--game-dir", "hdd0": "--hdd0",
             "hdd1": "--hdd1", "savedata": "--savedata", "dev_flash": "--dev-flash"}
LEGACY_US_KEYS = ["exe", "elf", "game_dir", "hdd0", "hdd1", "savedata", "dev_flash"]


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
    s = copy.deepcopy(DEFAULTS)
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for k, v in data.items():
            if k in GLOBAL_KEYS:        # ignore unknown keys
                s[k] = v
        eds = data.get("editions")
        if isinstance(eds, dict):
            for e in EDITIONS:
                if isinstance(eds.get(e), dict):
                    for k in ED_KEYS:
                        s["editions"][e][k] = str(eds[e].get(k, ""))
        else:                           # settings from before editions: paths were the US ones
            for k in LEGACY_US_KEYS:
                if k in data:
                    s["editions"]["us"][k] = str(data[k])
        if "tex_enable" not in data and data.get("tex_replace"):
            s["tex_enable"] = True      # old files: a folder meant "on"
    if s["edition"] not in EDITIONS:
        s["edition"] = "us"
    return s


def save_settings(path, s):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    clean = {k: s.get(k, DEFAULTS[k]) for k in GLOBAL_KEYS}
    clean["editions"] = {e: {k: s["editions"][e].get(k, "") for k in ED_KEYS} for e in EDITIONS}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(clean, f, indent=2)
        f.write("\n")


# ------------------------------------------------------------------- resolution

def _abs(base, p):
    return os.path.abspath(os.path.join(base, p)) if p else ""


def _first(paths, isdir=False):
    for p in paths:
        if p and (os.path.isdir(p) if isdir else os.path.isfile(p)):
            return os.path.abspath(p)
    return ""


def ult_out_dir(s, base):
    """Folder Ultimate setup builds into (game/ and hdd0/ inside)."""
    if s["ult_out"]:
        return _abs(base, s["ult_out"])
    if not FROZEN and os.path.isdir(DEV_ULT_DIR + "/game"):
        return os.path.abspath(DEV_ULT_DIR)
    return os.path.join(base, "ultimate", "data")


def find_exe(s, settings_file, ed=None):
    """Saved path, then the edition's usual places."""
    ed = ed or s["edition"]
    base = os.path.dirname(os.path.abspath(settings_file))
    v = s["editions"][ed]["exe"]
    if v:
        return _abs(base, v)
    if ed == "us":
        cands = [os.path.join(base, EXE_NAME), os.path.join(HERE, EXE_NAME)]
        if not FROZEN:
            cands += [os.path.join(ROOT, "build", b, EXE_NAME) for b in ("official-1.03", "fix-1.02")]
    else:
        cands = [os.path.join(base, "ultimate", EXE_NAME), os.path.join(HERE, "ultimate", EXE_NAME)]
        if not FROZEN:
            cands.append(DEV_ULT_EXE)
    return _first(cands) or os.path.abspath(cands[0])


def eff_path(s, settings_file, key, ed=None):
    """The path passed for a flag: the saved value, else one found automatically, else ''
    (then no flag is passed and the exe uses its own default)."""
    ed = ed or s["edition"]
    base = os.path.dirname(os.path.abspath(settings_file))
    v = s["editions"][ed][key]
    if v:
        return _abs(base, v)
    dev = not FROZEN
    if ed == "us":
        if key == "elf":
            return _first([os.path.join(base, "EBOOT.elf")] +
                          ([ROOT + "/work/extracted/update-1.03/USRDIR/EBOOT.elf"] if dev else []))
        if key == "game_dir":
            return _first([os.path.join(base, "game")] +
                          ([ROOT + "/work/game/base-1.00"] if dev else []), isdir=True)
        if key == "dev_flash":
            return _first([os.path.join(base, "dev_flash")] +
                          ([ROOT + "/work/runtime/firmware-codex/dev_flash"] if dev else []), isdir=True)
        return ""
    out = ult_out_dir(s, base)
    if key == "elf":
        return _first([out + "/eboot/jp127.elf", os.path.join(base, "ultimate", "jp127.elf"),
                       os.path.join(base, "ultimate", "EBOOT.elf"), os.path.join(base, "jp127.elf")])
    if key == "game_dir":
        return _first([out + "/game"], isdir=True)
    if key == "hdd0":
        return _first([out + "/hdd0"], isdir=True)
    if key == "dev_flash":
        return eff_path(s, settings_file, "dev_flash", "us")
    return ""


def profile_name_ok(name):
    return bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 _.\-]{0,31}", name or "")) and \
        not name.endswith((" ", ".")) and name.lower() != DEFAULT_PROFILE.lower() and \
        name.upper() not in {"CON", "PRN", "AUX", "NUL"} | {"COM%d" % i for i in range(1, 10)} | \
        {"LPT%d" % i for i in range(1, 10)}


def profiles_root(settings_file):
    return os.path.join(os.path.dirname(os.path.abspath(settings_file)), "profiles")


def profile_savedata(s, settings_file, ed=None, profile=None):
    """Save root for a profile. Default = the edition's saved path (blank: the exe's own default,
    where existing saves already live). Others = profiles/<name>/<edition>/savedata."""
    ed = ed or s["edition"]
    profile = profile or s["profile"]
    if profile == DEFAULT_PROFILE or not profile:
        return eff_path(s, settings_file, "savedata", ed)
    return os.path.join(profiles_root(settings_file), profile, ed, "savedata")


def create_profile(s, settings_file, name, copy_from=None):
    """Add a profile. Empty unless copy_from names an existing profile (explicit copy). Existing
    saves are never moved or changed; the source is only read. Returns a message."""
    if not profile_name_ok(name):
        raise ValueError("Profile names use letters, digits, space, _ . - (1 to 32 characters) "
                         "and cannot be 'Default'.")
    if name.lower() in [p.lower() for p in s["profiles"]]:
        raise ValueError("A profile called %s already exists." % name)
    made = []
    for ed in EDITIONS:
        dst = profile_savedata(s, settings_file, ed, name)
        if os.path.exists(dst) and os.listdir(dst):
            raise ValueError("Folder already holds data, not touching it: " + dst)
    notes = []
    for ed in EDITIONS:
        dst = profile_savedata(s, settings_file, ed, name)
        if copy_from:
            src = profile_savedata(s, settings_file, ed, copy_from)
            if src and os.path.isdir(src):
                if os.path.isdir(dst):
                    os.rmdir(dst)               # empty only (checked above)
                shutil.copytree(src, dst)
                notes.append("%s: copied from %s" % (ed, src))
                made.append(dst)
                continue
            notes.append("%s: nothing to copy, starts empty" % ed)
        os.makedirs(dst, exist_ok=True)
        made.append(dst)
    s["profiles"].append(name)
    return "\n".join(notes) or "Created empty profile %s." % name


# ------------------------------------------------------------------- validation

def resolve_size(s):
    for label, w, h in RESOLUTIONS:
        if label == s["resolution"] and w:
            return w, h
    return int(s["width"]), int(s["height"])


def validate(s, settings_file):
    """Return (errors, warnings) as lists of plain-English strings."""
    errs, warns = [], []
    base = os.path.dirname(os.path.abspath(settings_file))
    ed = s["edition"]
    ult = ed == "ult"
    exe = find_exe(s, settings_file)
    if not os.path.isfile(exe):
        errs.append("The game program for %s was not found: %s\nSet the path to %s under Advanced."
                    % (EDITIONS[ed], exe, EXE_NAME))
    elf = eff_path(s, settings_file, "elf")
    if not elf:                         # the exe's own default: <game dir>/USRDIR/EBOOT.elf
        exe_dir = os.path.dirname(exe)
        g = eff_path(s, settings_file, "game_dir")
        if not g:
            g = os.path.join(exe_dir, "game")
            g = g if os.path.isdir(g) else exe_dir
        elf = os.path.join(g, "USRDIR", "EBOOT.elf")
    if not os.path.isfile(elf):
        errs.append("The game file %s was not found: %s\n%s"
                    % ("jp127.elf (JP 1.27)" if ult else "EBOOT.elf", elf,
                       "Put the decrypted JP 1.27 EBOOT.elf in the Ultimate data folder's eboot folder, or set it under Advanced."
                       if ult else "Set the Game folder or the ELF path under Advanced."))
    if ult:
        g = eff_path(s, settings_file, "game_dir")
        if not g or not os.path.isfile(os.path.join(g, "PARAM.SFO")):
            errs.append("The Ultimate game data was not found (%s).\nOpen the Ultimate setup tab and "
                        "press Build the Ultimate data." % (g or ult_out_dir(s, base) + "/game"))
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
    if s["tex_enable"] and not s["tex_replace"]:
        errs.append("HD textures are on but no texture folder is chosen.")
    if s["tex_enable"] and s["tex_replace"] and not os.path.isdir(_abs(base, s["tex_replace"])):
        errs.append("HD texture folder not found: %s" % _abs(base, s["tex_replace"]))
    if s["tweaks"] and not os.path.isfile(_abs(base, s["tweaks"])):
        errs.append("Tweaks file not found: %s" % _abs(base, s["tweaks"]))
    for k in ("game_dir", "hdd0", "hdd1", "savedata", "dev_flash"):
        v = s["editions"][ed][k]
        if v and not os.path.isdir(_abs(base, v)):
            if k in ("hdd0", "hdd1", "savedata"):
                continue            # the game creates these on first run
            errs.append("Folder not found (%s): %s" % (k, _abs(base, v)))
    if s["profile"] != DEFAULT_PROFILE and s["profile"] not in s["profiles"]:
        errs.append("Unknown save profile: %s" % s["profile"])
    if s["window_mode"] not in WINDOW_MODES:
        errs.append("Unknown window mode: %s" % s["window_mode"])
    if s["aspect"] not in ASPECTS:
        errs.append("Unknown aspect mode: %s" % s["aspect"])
    if s["aspect"] in EXPERIMENTAL_ASPECTS:
        warns.append("Aspect 'expand' is experimental (patch 0055). Builds without it "
                     "reject the option and exit with code 2.")
    if fps_env(s["fps"]) is None and str(s["fps"]).strip() not in FPS_STOCK:
        errs.append("Unknown frame rate: %s" % s["fps"])
    if fps_locked(s) and fps_env(s["fps"]):
        warns.append("The Ultimate edition runs at 30 FPS; the frame rate setting (%s) is not used "
                     "for it." % s["fps"])
    if fps_effective(s):
        warns.append("Frame rates above 30 are opt-in (patches 0058, 0074) and apply on the "
                     "course only; menus and the swing gauge keep the stock 30/60.")
        if s["vsync"] and fps_effective(s) not in ("monitor",):
            warns.append("With vsync on, the rate cannot pass the display's refresh rate. "
                         "Turn vsync off for higher rates (tearing, or a VRR display).")
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
    if s["tex_enable"] and s["tex_replace"]:
        argv += ["--tex-replace", _abs(base, s["tex_replace"]),   # patch 0047
                 "--tex-replace-mb", str(int(s["tex_replace_mb"]))]
    if s["tex_dump"]:
        argv += ["--tex-dump", _abs(base, s["tex_dump"])]     # patch 0047
    if s["mute"]:
        argv.append("--mute")                                 # port/cli_options.cpp
    for key, flag in PATH_FLAG.items():
        v = profile_savedata(s, settings_file) if key == "savedata" else eff_path(s, settings_file, key)
        if v:
            argv += [flag, v]
    if s["tweaks"]:
        env["HSG_TWEAKS"] = _abs(base, s["tweaks"])           # patch 0059
    if fps_effective(s):
        env["HSG_FPS"] = fps_effective(s)                     # patches 0058, 0074
        if not s["vsync"]:
            env["D3D12_VSYNC"] = "0"                          # rsx_d3d12_backend.c
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
    sd = profile_savedata(s, settings_file)
    if sd and s["profile"] != DEFAULT_PROFILE:
        os.makedirs(sd, exist_ok=True)
    full_env = dict(os.environ)
    full_env.update(env)
    log, log_path = open_run_log(settings_file)
    if log is None:
        proc = subprocess.Popen(argv, cwd=cwd, env=full_env)
    else:
        head = format_command(argv, env).replace("\n", "\n[launcher] ")
        log.write(("[launcher] %s\n[launcher] edition=%s profile=%s\n[launcher] %s\n\n"
                   % (time.strftime("%Y-%m-%d %H:%M:%S"), s["edition"], s["profile"], head)).encode("utf-8"))
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


# ---------------------------------------------------- Ultimate setup and PKG tools

def ult_defaults(s, settings_file):
    """Effective input folders for Ultimate setup (saved value, else the dev-tree default)."""
    base = os.path.dirname(os.path.abspath(settings_file))
    dev = not FROZEN
    return {
        "base": _abs(base, s["ult_base"]) or (os.path.join(ROOT, "work", "game", "base-1.00") if dev else ""),
        "updates": _abs(base, s["ult_updates"]) or (DEV_JP_UPDATES if dev else ""),
        "us_updates": _abs(base, s["ult_us_updates"]) or (DEV_US_UPDATES if dev and os.path.isdir(DEV_US_UPDATES) else ""),
        "out": ult_out_dir(s, base),
    }


def ult_setup_args(d, dry=False):
    a = ["--base", "us", "--lang", "en", "--out", d["out"]]
    if d["base"]:
        a += ["--base-dir", d["base"]]
    if d["updates"]:
        a += ["--updates", d["updates"]]
    if d["us_updates"]:
        a += ["--us-updates", d["us_updates"]]
    if dry:
        a.append("--dry")
    return a


def self_command(*tool_args):
    """argv that runs this program again in a tool mode (the frozen exe, or python + this file)."""
    if FROZEN:
        return [sys.executable] + list(tool_args)
    return [sys.executable, os.path.abspath(__file__)] + list(tool_args)


def pkg_extract_script():
    for p in (os.path.join(BUNDLE, "pkg_extract.py"),
              os.path.join(ROOT, "external", "ps3recomp", "tools", "pkg_extract.py")):
        if os.path.isfile(p):
            return p
    return ""


def pkg_version(name):
    """JP update version from a package file name ...-A0127-V0100-... -> 01.27."""
    m = re.search(r"-A(\d\d)(\d\d)-V", name)
    return "%s.%s" % m.groups() if m else ""


def run_tool(args):
    """In-process tool modes used by the GUI's background runs."""
    if args[0] == "--ultimate-setup":
        import build_ultimate_data
        sys.argv = ["build_ultimate_data"] + args[1:]
        return build_ultimate_data.main()
    if args[0] == "--pkg-extract":
        import runpy
        script = pkg_extract_script()
        if not script:
            print("[error] pkg_extract.py is not available in this build.")
            return 2
        sys.argv = [script] + args[1:]
        try:
            runpy.run_path(script, run_name="__main__")
        except SystemExit as e:
            return e.code if isinstance(e.code, int) else (1 if e.code else 0)
        except Exception as e:                                # noqa: BLE001
            print("[error] extraction failed: %s: %s" % (type(e).__name__, e))
            return 1
        return 0
    return 2


def attach_stdio():
    """A windowed exe has no stdout. Wire it to the parent's pipe or console so CLI modes print."""
    if os.name != "nt":
        return
    import ctypes
    import msvcrt
    k = ctypes.windll.kernel32
    k.GetStdHandle.restype = ctypes.c_void_p
    for name, std, mode in (("stdout", -11, "w"), ("stderr", -12, "w")):
        if getattr(sys, name, None) is not None:
            continue
        k.AttachConsole(-1)
        h = k.GetStdHandle(std)
        fobj = None
        if h not in (None, 0, ctypes.c_void_p(-1).value):
            try:
                fd = msvcrt.open_osfhandle(h, 0)
                fobj = os.fdopen(fd, mode, encoding="utf-8", errors="replace", buffering=1)
            except OSError:
                fobj = None
        if fobj is None:
            try:
                fobj = open("CONOUT$", mode, encoding="utf-8", errors="replace", buffering=1)
            except OSError:
                fobj = open(os.devnull, mode)
        setattr(sys, name, fobj)


# -------------------------------------------------------------------------- GUI

def run_gui(settings_file):
    import queue
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox, simpledialog

    root = tk.Tk()
    root.title("Hot Shots Golf Launcher")
    state = {"file": settings_file, "fps_saved": None}
    s = load_settings(settings_file)
    state["fps_saved"] = s["fps"]
    V = {}          # global setting variables
    PV = {}         # path variables of the edition on screen
    cur_ed = {"v": s["edition"]}

    def var(key, kind=tk.StringVar):
        V[key] = kind(value=s[key])
        return V[key]

    # ---- top bar: edition and profile
    top = ttk.Frame(root, padding=(8, 8, 8, 0))
    top.pack(fill="x")
    ttk.Label(top, text="Edition").grid(row=0, column=0, sticky="w")
    ed_var = tk.StringVar(value=EDITIONS[s["edition"]])
    ed_box = ttk.Combobox(top, textvariable=ed_var, state="readonly", width=48,
                          values=[EDITIONS["us"], EDITIONS["ult"]])
    ed_box.grid(row=0, column=1, sticky="w", padx=6)
    ttk.Label(top, text="Save profile").grid(row=1, column=0, sticky="w", pady=(4, 0))
    prof_var = tk.StringVar(value=s["profile"])
    prof_box = ttk.Combobox(top, textvariable=prof_var, state="readonly", width=24)
    prof_box.grid(row=1, column=1, sticky="w", padx=6, pady=(4, 0))

    nb = ttk.Notebook(root)
    nb.pack(fill="both", expand=True, padx=8, pady=8)

    def tab(name):
        f = ttk.Frame(nb, padding=10)
        nb.add(f, text=name)
        f.columnconfigure(1, weight=1)
        return f

    def browse_into(v, is_dir=True):
        p = filedialog.askdirectory() if is_dir else filedialog.askopenfilename()
        if p:
            v.set(os.path.normpath(p))

    def row_path(f, r, key, label, is_dir=True, hint="", store=V):
        ttk.Label(f, text=label).grid(row=r, column=0, sticky="w", pady=2)
        if store is V:
            v = var(key)
        else:
            v = store[key] = tk.StringVar(value="")
        ttk.Entry(f, textvariable=v, width=52).grid(row=r, column=1, sticky="we", padx=4)
        ttk.Button(f, text="Browse", command=lambda: browse_into(v, is_dir)).grid(row=r, column=2)
        if hint:
            ttk.Label(f, text=hint, foreground="#666", wraplength=520).grid(
                row=r + 1, column=1, sticky="w", padx=4)

    # ---- Display
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

    # ---- Frame rate
    fr = tab("Frame rate")
    ttk.Label(fr, text="Frame rate").grid(row=0, column=0, sticky="w", pady=2)
    fps_var = var("fps")
    fps_box = ttk.Combobox(fr, textvariable=fps_var, state="readonly", values=FPS_CHOICES)
    fps_box.grid(row=0, column=1, sticky="w", padx=4)
    ttk.Label(fr, text="Sets HSG_FPS. Rates above 30 apply on the course; game logic stays "
                       "at 30 and the frames between are interpolated, so the game runs at "
                       "its normal speed. Menus stay at 30 and the swing gauge at 60. "
                       "Match monitor uses the refresh rate of the game window's display.",
              foreground="#a60", wraplength=520).grid(row=1, column=1, sticky="w", padx=4)
    vs_box = ttk.Checkbutton(fr, text="Vsync (off: no rate limit from the display; tearing unless "
                                      "the display has VRR)",
                             variable=var("vsync", tk.BooleanVar))
    vs_box.grid(row=2, column=1, sticky="w", padx=4, pady=2)
    fps_note = ttk.Label(fr, text="", foreground="#b00", wraplength=520)
    fps_note.grid(row=3, column=1, sticky="w", padx=4, pady=4)

    # ---- Textures
    t = tab("Textures")
    ttk.Checkbutton(t, text="Use an HD texture pack", variable=var("tex_enable", tk.BooleanVar)
                    ).grid(row=0, column=1, sticky="w", padx=4, pady=2)
    row_path(t, 1, "tex_replace", "HD texture pack folder",
             hint="PNG or DDS replacement textures (--tex-replace). Off by default; with the box "
                  "ticked and a folder chosen the game loads matching textures.")
    ttk.Label(t, text="Texture memory cap (MB)").grid(row=3, column=0, sticky="w", pady=2)
    ttk.Spinbox(t, textvariable=var("tex_replace_mb", tk.IntVar), from_=64, to=16384,
                width=8).grid(row=3, column=1, sticky="w", padx=4)
    ttk.Label(t, text="GPU memory budget for the replacement textures (--tex-replace-mb, default 768).",
              foreground="#666", wraplength=520).grid(row=4, column=1, sticky="w", padx=4)
    row_path(t, 5, "tex_dump", "Texture dump folder",
             hint="Blank = off. Saves the game's textures for building an HD pack.")

    # ---- Save profiles
    sp = tab("Save profiles")
    ttk.Label(sp, text=("A profile is a separate save folder. The game takes one save root "
                        "(--savedata) and keeps its saves under it, so each named profile gets its "
                        "own root for each edition: profiles/<name>/<edition>/savedata next to the "
                        "settings file. The installed game data (hdd0) is shared and not copied.\n\n"
                        "Default keeps using the save folder you already have (the one set under "
                        "Advanced, or the game's own default). Nothing is moved or changed: a "
                        "new profile starts empty, or is a copy of a profile you pick."),
              wraplength=540, justify="left").grid(row=0, column=0, columnspan=3, sticky="w")
    pl = tk.Listbox(sp, height=6, exportselection=False)
    pl.grid(row=1, column=0, columnspan=2, sticky="we", pady=8)
    pl_info = ttk.Label(sp, text="", foreground="#666", wraplength=540, justify="left")
    pl_info.grid(row=2, column=0, columnspan=3, sticky="w")

    def refresh_profiles():
        names = [DEFAULT_PROFILE] + list(s["profiles"])
        prof_box.config(values=names)
        pl.delete(0, "end")
        for n in names:
            pl.insert("end", n)
        if prof_var.get() not in names:
            prof_var.set(DEFAULT_PROFILE)
        pl.selection_clear(0, "end")
        pl.selection_set(names.index(prof_var.get()))

    def profile_info(*_):
        cur = tmp_settings()
        sd = profile_savedata(cur, state["file"])
        pl_info.config(text="Saves for %s / %s: %s" % (
            EDITIONS[cur["edition"]], cur["profile"],
            sd or "(the game's own default, next to the exe)"))

    def new_profile(copy):
        name = simpledialog.askstring("New profile", "Profile name:", parent=root)
        if not name:
            return
        src = None
        if copy:
            src = prof_var.get()
            if not messagebox.askyesno("Copy saves", "Copy the saves of '%s' into the new profile '%s'?\n"
                                       "The original is only read, never changed." % (src, name)):
                return
        try:
            cur = tmp_settings()
            cur["profiles"] = list(s["profiles"])
            msg = create_profile(cur, state["file"], name.strip(), src)
            s["profiles"] = cur["profiles"]
        except (ValueError, OSError) as e:
            messagebox.showerror("Profile", str(e))
            return
        prof_var.set(name.strip())
        refresh_profiles()
        profile_info()
        show("Profile created.\n" + msg, "#060")

    pbf = ttk.Frame(sp)
    pbf.grid(row=3, column=0, columnspan=3, sticky="w", pady=6)
    ttk.Button(pbf, text="New empty profile...", command=lambda: new_profile(False)).pack(side="left")
    ttk.Button(pbf, text="New profile as a copy of the selected one...",
               command=lambda: new_profile(True)).pack(side="left", padx=6)

    def pick_from_list(_e=None):
        sel = pl.curselection()
        if sel:
            prof_var.set(pl.get(sel[0]))
            profile_info()
    pl.bind("<<ListboxSelect>>", pick_from_list)
    prof_box.bind("<<ComboboxSelected>>", lambda e: (refresh_profiles(), profile_info()))

    # ---- Ultimate setup
    us = tab("Ultimate setup")
    ttk.Label(us, text=("The Ultimate edition needs game data built from your own files: the US base "
                        "game (1.00) renamed for the JP program, the JP updates 01.01 to 01.27 "
                        "layered on top, and English menus and text. This runs "
                        "build_ultimate_data.py with jp127_english.py and the bundled translation "
                        "table. Needs the JP updates already extracted (folders 01.01 .. 01.27, "
                        "each with a USRDIR folder). Nothing is written outside the output "
                        "folder."), wraplength=560, justify="left").grid(row=0, column=0, columnspan=3, sticky="w")
    row_path(us, 1, "ult_base", "US base game folder",
             hint="Holds PARAM.SFO and USRDIR (the 1.00 base game).")
    row_path(us, 3, "ult_updates", "JP updates folder",
             hint="Holds the extracted updates 01.01 .. 01.27 (BCJS30089).")
    row_path(us, 5, "ult_us_updates", "US updates folder (optional)",
             hint="Extracted US updates 01.01 .. 01.03 (NPUA80864); more English text and textures.")
    row_path(us, 7, "ult_out", "Output folder",
             hint="Blank = the default. Gets game/ and hdd0/ (several GB; hard links on the same drive).")
    dry_var = tk.BooleanVar(value=False)
    ubf = ttk.Frame(us)
    ubf.grid(row=9, column=0, columnspan=3, sticky="we", pady=4)
    log_box = tk.Text(us, height=9, width=80, wrap="word", state="disabled")
    log_box.grid(row=10, column=0, columnspan=3, sticky="we")
    prog = ttk.Progressbar(us, mode="indeterminate")
    prog.grid(row=11, column=0, columnspan=3, sticky="we", pady=2)
    job = {"proc": None}
    lines_q = queue.Queue()

    def log_add(text):
        log_box.config(state="normal")
        log_box.insert("end", text)
        log_box.see("end")
        log_box.config(state="disabled")

    def pump():
        try:
            while True:
                item = lines_q.get_nowait()
                if item is None:
                    prog.stop()
                    rc = job["proc"].returncode if job["proc"] else 0
                    log_add("\n[launcher] finished, exit code %s\n" % rc)
                    job["proc"] = None
                    refresh_all()
                else:
                    log_add(item)
        except queue.Empty:
            pass
        if job["proc"]:
            root.after(150, pump)

    def start_job(argv, title):
        if job["proc"]:
            messagebox.showinfo(title, "Another job is still running.")
            return
        log_add("\n[launcher] %s\n[launcher] %s\n" % (title, subprocess.list2cmdline(argv)))
        flags = 0x08000000 if os.name == "nt" else 0            # CREATE_NO_WINDOW
        try:
            p = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, creationflags=flags)
        except OSError as e:
            log_add("[error] could not start: %s\n" % e)
            return
        job["proc"] = p
        prog.start(12)

        def reader():
            for raw in iter(p.stdout.readline, b""):
                lines_q.put(raw.decode("utf-8", "replace"))
            p.wait()
            lines_q.put(None)
        threading.Thread(target=reader, daemon=True).start()
        root.after(150, pump)

    def ult_dirs():
        cur = tmp_settings()
        return ult_defaults(cur, state["file"])

    def run_setup(dry):
        argv = self_command("--ultimate-setup", *ult_setup_args(ult_dirs(), dry))
        start_job(argv, "Ultimate setup" + (" (dry run, writes nothing)" if dry else ""))

    ttk.Button(ubf, text="Build the Ultimate data", command=lambda: run_setup(False)).pack(side="left")
    ttk.Button(ubf, text="Dry run (check only)", command=lambda: run_setup(True)).pack(side="left", padx=6)

    def stop_job():
        p = job["proc"]
        if p and p.pid:
            subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True,
                           creationflags=0x08000000 if os.name == "nt" else 0)
    ttk.Button(ubf, text="Stop", command=stop_job).pack(side="left")

    def extract_pkgs():
        src = filedialog.askdirectory(title="Folder with the JP update .pkg files")
        if not src:
            return
        pkgs = sorted(f for f in os.listdir(src) if f.lower().endswith(".pkg") and pkg_version(f))
        if not pkgs:
            messagebox.showerror("Extract", "No update .pkg files with a version (-A0101-V...) in that folder.")
            return
        if not pkg_extract_script():
            messagebox.showerror("Extract", "The PKG extractor is not part of this build. "
                                            "Extract the updates yourself into folders 01.01 .. 01.27.")
            return
        dst = _abs(os.path.dirname(os.path.abspath(state["file"])), V["ult_updates"].get()) or \
            filedialog.askdirectory(title="Where to put the extracted updates (01.01 .. 01.27)")
        if not dst:
            return
        V["ult_updates"].set(os.path.normpath(dst))
        steps = []
        for f in pkgs:
            o = os.path.join(dst, pkg_version(f))
            if os.path.isfile(os.path.join(o, ".done")):
                continue
            steps.append((os.path.join(src, f), o))
        if not steps:
            log_add("[pkg] everything in that folder is already extracted\n")
            return
        if not messagebox.askyesno("Extract", "Extract %d package(s) to %s?" % (len(steps), dst)):
            return
        def chain():
            for pkg, o in steps:
                os.makedirs(o, exist_ok=True)
                lines_q.put("[pkg] %s -> %s\n" % (os.path.basename(pkg), o))
                p = subprocess.Popen(self_command("--pkg-extract", pkg, o), stdin=subprocess.DEVNULL,
                                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                     creationflags=0x08000000 if os.name == "nt" else 0)
                job["proc"] = p
                tail = b""
                for raw in iter(p.stdout.readline, b""):
                    tail = raw
                    lines_q.put(raw.decode("utf-8", "replace"))
                p.wait()
                if p.returncode == 0:
                    open(os.path.join(o, ".done"), "w").close()
                else:
                    lines_q.put("[error] extraction failed (exit %s): %s\n" % (p.returncode, os.path.basename(pkg)))
                    break
            lines_q.put(None)
        job["proc"] = type("Pending", (), {"returncode": 0, "pid": None})()
        prog.start(12)
        threading.Thread(target=chain, daemon=True).start()
        root.after(150, pump)
    ttk.Button(ubf, text="Extract JP update PKGs...", command=extract_pkgs).pack(side="left", padx=6)

    # ---- Advanced
    a = tab("Advanced")
    ttk.Label(a, text="Paths below belong to the edition chosen at the top. Blank = automatic "
                      "(see the grey text) or the exe's own default; no flag is passed for it.",
              foreground="#666", wraplength=560).grid(row=0, column=0, columnspan=3, sticky="w")
    hint_lbl = {}

    def adv_row(r, key, label, is_dir=True):
        row_path(a, r, key, label, is_dir=is_dir, store=PV)
        hint_lbl[key] = ttk.Label(a, text="", foreground="#666", wraplength=520)
        hint_lbl[key].grid(row=r + 1, column=1, sticky="w", padx=4)
    adv_row(1, "exe", "Game program (exe)", is_dir=False)
    adv_row(3, "elf", "EBOOT.elf", is_dir=False)
    adv_row(5, "game_dir", "Game folder")
    adv_row(7, "hdd0", "hdd0 folder")
    adv_row(9, "hdd1", "hdd1 folder")
    adv_row(11, "savedata", "Save data folder (Default profile)")
    adv_row(13, "dev_flash", "dev_flash folder")
    row_path(a, 15, "tweaks", "Guest tweaks file (EXPERIMENTAL)", is_dir=False,
             hint="Blank = off (HSG_TWEAKS, patch 0059).")
    ttk.Checkbutton(a, text="Mute audio", variable=var("mute", tk.BooleanVar)).grid(
        row=17, column=1, sticky="w", padx=4, pady=2)
    ttk.Label(a, text="Extra arguments").grid(row=18, column=0, sticky="w", pady=2)
    ttk.Entry(a, textvariable=var("extra_args"), width=52).grid(row=18, column=1, sticky="we", padx=4)
    ttk.Checkbutton(a, text="Sell DLC clubs and balls (classes 3-4) in the shop when not owned",
                    variable=var("dlc_earn", tk.BooleanVar)).grid(row=19, column=1, sticky="w", padx=4, pady=2)

    status = tk.Text(root, height=7, width=84, wrap="word", state="disabled")
    status.pack(fill="x", padx=8)

    def show(text, color="black"):
        status.config(state="normal", fg=color)
        status.delete("1.0", "end")
        status.insert("end", text)
        status.config(state="disabled")

    def ed_key():
        return "ult" if ed_var.get() == EDITIONS["ult"] else "us"

    def store_paths():
        for k in ED_KEYS:
            s["editions"][cur_ed["v"]][k] = PV[k].get().strip()

    def load_paths():
        for k in ED_KEYS:
            PV[k].set(s["editions"][cur_ed["v"]][k])

    def tmp_settings():
        """Settings as the window shows them (without writing)."""
        out = copy.deepcopy(s)
        for k in GLOBAL_KEYS:
            if k in V:
                try:
                    out[k] = V[k].get()
                except tk.TclError:
                    out[k] = DEFAULTS[k]
        out["edition"] = ed_key()
        out["profile"] = prof_var.get()
        out["editions"][cur_ed["v"]] = {k: PV[k].get().strip() for k in ED_KEYS}
        if out["aspect"].startswith("expand"):
            out["aspect"] = "expand"
        for k in ("width", "height", "tex_replace_mb"):
            try:
                out[k] = int(out[k])
            except (TypeError, ValueError, tk.TclError):
                out[k] = DEFAULTS[k]
        if fps_locked(out):             # the on-screen rate is locked to 30; keep the US choice
            out["fps"] = state["fps_saved"]
        else:
            state["fps_saved"] = out["fps"]
        return out

    def apply_edition(*_):
        new = ed_key()
        if new != cur_ed["v"]:
            store_paths()
            cur_ed["v"] = new
            load_paths()
        if fps_locked({"edition": new}):
            fps_box.config(state="disabled")
            vs_box.config(state="disabled")
            if V["fps"].get() != "30 (stock)":
                state["fps_saved"] = V["fps"].get()
            V["fps"].set("30 (stock)")
            fps_note.config(text="Not available for the Ultimate edition: rates above 30 (60, 120, "
                                 "144, 165, 180, 240, Unlocked, Match monitor) are greyed out because "
                                 "the frame-rate code stands down on the JP 1.27 program. It runs at "
                                 "the stock 30.")
        else:
            fps_box.config(state="readonly")
            vs_box.config(state="normal")
            V["fps"].set(state["fps_saved"] if state["fps_saved"] else "30 (stock)")
            fps_note.config(text="")
        refresh_hints()
        profile_info()
        check()

    def refresh_hints():
        cur = tmp_settings()
        for k, lbl in hint_lbl.items():
            if k == "exe":
                lbl.config(text="Blank = %s" % find_exe(cur, state["file"]))
            elif k == "savedata":
                lbl.config(text="Blank = %s" % (eff_path(cur, state["file"], k) or
                                                "the game's own default (<exe folder>/savedata)"))
            else:
                lbl.config(text="Blank = %s" % (eff_path(cur, state["file"], k) or
                                                "the exe's own default (<exe folder>/%s)" % k.replace("_", "-")))

    def refresh_all():
        refresh_hints()
        profile_info()
        check()

    def check():
        cur = tmp_settings()
        errs, warns = validate(cur, state["file"])
        head = "%s, profile %s\n" % (EDITIONS[cur["edition"]], cur["profile"])
        if errs:
            show(head + "ERROR\n" + "\n".join(errs), "#b00")
        else:
            argv, env, _ = build_command(cur, state["file"])
            show(head + "OK\n" + "\n".join(warns + [format_command(argv, env)]), "#060" if not warns else "#a60")
        return cur, errs

    def commit():
        cur = tmp_settings()
        for k in GLOBAL_KEYS:
            s[k] = cur[k]
        s["editions"] = cur["editions"]
        s["profile"] = cur["profile"]
        s["edition"] = cur["edition"]
        return cur

    def save():
        cur = commit()
        check()
        save_settings(state["file"], cur)
        messagebox.showinfo("Saved", "Saved to " + state["file"])

    def play():
        cur = commit()
        _, errs = check()
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
            refresh_all()

    bf = ttk.Frame(root)
    bf.pack(fill="x", padx=8, pady=8)
    ttk.Button(bf, text="Check", command=check).pack(side="left")
    ttk.Button(bf, text="Settings folder...", command=choose_folder).pack(side="left", padx=4)
    ttk.Button(bf, text="Save", command=save).pack(side="right")
    ttk.Button(bf, text="Save and Play", command=play).pack(side="right", padx=4)
    ed_box.bind("<<ComboboxSelected>>", apply_edition)
    prof_box.bind("<<ComboboxSelected>>", lambda e: (refresh_profiles(), profile_info(), check()), add="+")
    root.title("Hot Shots Golf Launcher - " + state["file"])
    load_paths()
    refresh_profiles()
    apply_edition()
    root.mainloop()


# --------------------------------------------------------------------- CLI main

def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if FROZEN and argv:
        attach_stdio()
    if argv and argv[0] in ("--ultimate-setup", "--pkg-extract"):
        return run_tool(argv)
    ap = argparse.ArgumentParser(description="Hot Shots Golf launcher")
    ap.add_argument("--settings", help="settings file or folder (default: hsg_settings.json beside the launcher)")
    ap.add_argument("--exe", help="override the exe path of the chosen edition for this run")
    ap.add_argument("--edition", choices=sorted(EDITIONS), help="us or ult, for this run")
    ap.add_argument("--profile", help="save profile name, for this run")
    ap.add_argument("--set", action="append", default=[], metavar="KEY=VALUE",
                    help="override a top-level setting for this run (value is JSON, else text)")
    ap.add_argument("--out-file", help="also write the --print-command text to this file")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--print-command", action="store_true", help="print the command and env, do not launch")
    g.add_argument("--run", action="store_true", help="launch from the saved settings, no window")
    a = ap.parse_args(argv)

    sf = settings_path(a.settings)
    if a.print_command or a.run:
        s = load_settings(sf)
        if a.edition:
            s["edition"] = a.edition
        if a.profile:
            s["profile"] = a.profile
            if a.profile != DEFAULT_PROFILE and a.profile not in s["profiles"]:
                s["profiles"].append(a.profile)     # this run only; nothing is saved here
        for kv in a.set:
            k, _, v = kv.partition("=")
            if k not in GLOBAL_KEYS:
                print("error: unknown setting " + k, file=sys.stderr)
                return 2
            try:
                s[k] = json.loads(v)
            except ValueError:
                s[k] = v
        if a.exe:
            s["editions"][s["edition"]]["exe"] = os.path.abspath(a.exe)
        errs, warns = validate(s, sf)
        for w in warns:
            print("warning: " + w, file=sys.stderr)
        for e in errs:
            print("error: " + e, file=sys.stderr)
        if a.print_command:
            cmd, env, _ = build_command(s, sf)
            text = format_command(cmd, env)
            print(text)
            if a.out_file:
                with open(a.out_file, "w", encoding="utf-8") as f:
                    f.write("edition=%s profile=%s errors=%d\n%s\n" % (s["edition"], s["profile"], len(errs), text))
            return 1 if errs else 0
        if errs:
            return 1
        return launch(s, sf, wait=True).returncode
    run_gui(sf)
    return 0


if __name__ == "__main__":
    sys.exit(main())
