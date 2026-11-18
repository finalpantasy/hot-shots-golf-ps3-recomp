#include "cli_options.h"

#include <stdlib.h>
#include <string.h>
#include <string>

#ifdef _WIN32
#  define WIN32_LEAN_AND_MEAN
#  include <windows.h>
#else
#  include <unistd.h>
#  include <limits.h>
#endif

static const char kHelp[] =
"Usage: hotshots [options] [path/to/EBOOT.elf]\n"
"\n"
"Every path defaults to a folder next to the executable. Precedence for each\n"
"setting: command-line flag, then environment variable, then the default.\n"
"\n"
"  --elf <file>        PPU ELF to boot. Default: <game-dir>/USRDIR/EBOOT.elf.\n"
"                      A bare path with no flag also works.\n"
"  --game-dir <dir>    Game folder (VFS root, holds PARAM.SFO and USRDIR).\n"
"                      Env PS3_VFS_ROOT. Default: <exe dir>/game.\n"
"  --hdd0 <dir>        Folder for /dev_hdd0. Env PS3_HDD0_ROOT. Default: <exe dir>/hdd0.\n"
"  --hdd1 <dir>        Folder for /dev_hdd1. Env PS3_HDD1_ROOT. Default: <exe dir>/hdd1.\n"
"  --savedata <dir>    Save data folder. Env PS3_SAVEDATA_ROOT. Default: <exe dir>/savedata.\n"
"                      [not yet wired: the runtime does not read it]\n"
"  --title <text>      Window caption. Env PS3_TITLE. Default: TITLE from PARAM.SFO.\n"
"  --fullscreen        Start fullscreen.            [not yet wired]\n"
"  --windowed          Start in a window (default).\n"
"  --width <px>        Window width. Default 1280.\n"
"  --height <px>       Window height. Default 720.\n"
"  --verbose <n>       Log detail, 0 to 9. Env PS3_VERBOSE.\n"
"                      [not yet wired: exported to the environment only]\n"
"  --log <file>        Write all output to this file. A bare name goes in\n"
"                      <exe dir>/logs. Default: console.\n"
"  --hidden            Create the window without showing it or taking focus.\n"
"                      For automated test runs. Best effort, see docs/CLI.md.\n"
"  --exit-after <sec>  Quit cleanly after this many seconds.\n"
"  --help              Show this text.\n"
"  --version           Show the version.\n";

const char* cli_help_text(void) { return kHelp; }

static bool take_value(int argc, char** argv, int& i, const char* eq_val,
                       std::string& out, std::string& err)
{
    if (eq_val) { out = eq_val; return true; }
    if (i + 1 >= argc) { err = std::string("missing value for ") + argv[i]; return false; }
    out = argv[++i];
    return true;
}

static bool to_int(const std::string& s, int lo, int hi, int& out, const char* flag,
                   std::string& err)
{
    char* end = nullptr;
    long v = strtol(s.c_str(), &end, 10);
    if (s.empty() || *end || v < lo || v > hi) {
        err = std::string("bad value '") + s + "' for " + flag;
        return false;
    }
    out = (int)v;
    return true;
}

bool cli_parse(int argc, char** argv, CliOptions& o, std::string& err)
{
    for (int i = 1; i < argc; i++) {
        std::string arg = argv[i];
        if (arg.compare(0, 2, "--") != 0) {
            if (!o.elf.empty()) { err = "more than one ELF path: " + arg; return false; }
            o.elf = arg;
            o.elf_was_positional = true;
            continue;
        }
        std::string name = arg;
        const char* eq_val = nullptr;
        size_t eq = arg.find('=');
        if (eq != std::string::npos) { name = arg.substr(0, eq); eq_val = argv[i] + eq + 1; }

        std::string v;
        if      (name == "--help")       o.help = true;
        else if (name == "--version")    o.version = true;
        else if (name == "--fullscreen") o.fullscreen = true;
        else if (name == "--windowed")   o.windowed = true;
        else if (name == "--hidden")     o.hidden = true;
        else if (name == "--elf")        { if (!take_value(argc, argv, i, eq_val, o.elf, err)) return false;
                                           o.elf_was_positional = false; }
        else if (name == "--game-dir")   { if (!take_value(argc, argv, i, eq_val, o.game_dir, err)) return false; }
        else if (name == "--hdd0")       { if (!take_value(argc, argv, i, eq_val, o.hdd0, err)) return false; }
        else if (name == "--hdd1")       { if (!take_value(argc, argv, i, eq_val, o.hdd1, err)) return false; }
        else if (name == "--savedata")   { if (!take_value(argc, argv, i, eq_val, o.savedata, err)) return false; }
        else if (name == "--title")      { if (!take_value(argc, argv, i, eq_val, o.title, err)) return false; }
        else if (name == "--log")        { if (!take_value(argc, argv, i, eq_val, o.log_file, err)) return false; }
        else if (name == "--width")      { if (!take_value(argc, argv, i, eq_val, v, err)) return false;
                                           if (!to_int(v, 160, 16384, o.width, "--width", err)) return false; }
        else if (name == "--height")     { if (!take_value(argc, argv, i, eq_val, v, err)) return false;
                                           if (!to_int(v, 90, 16384, o.height, "--height", err)) return false; }
        else if (name == "--verbose")    { if (!take_value(argc, argv, i, eq_val, v, err)) return false;
                                           if (!to_int(v, 0, 9, o.verbose, "--verbose", err)) return false; }
        else if (name == "--exit-after") { if (!take_value(argc, argv, i, eq_val, v, err)) return false;
                                           if (!to_int(v, 1, 86400, o.exit_after, "--exit-after", err)) return false; }
        else { err = "unknown option " + name; return false; }
    }
    if (o.fullscreen && o.windowed) { err = "--fullscreen and --windowed cannot be used together"; return false; }
    return true;
}

static void slashes(std::string& s)
{
    for (char& c : s) if (c == '\\') c = '/';
}

std::string cli_exe_dir(const char* argv0)
{
    std::string path;
#ifdef _WIN32
    char buf[MAX_PATH * 2];
    DWORD n = GetModuleFileNameA(NULL, buf, sizeof buf);
    if (n > 0 && n < sizeof buf) path.assign(buf, n);
#else
    char buf[PATH_MAX];
    ssize_t n = readlink("/proc/self/exe", buf, sizeof buf - 1);
    if (n > 0) path.assign(buf, (size_t)n);
#endif
    if (path.empty() && argv0) path = argv0;
    slashes(path);
    size_t cut = path.rfind('/');
    if (cut == std::string::npos) return ".";
    return path.substr(0, cut);
}

void cli_setenv(const char* name, const char* value)
{
#ifdef _WIN32
    _putenv_s(name, value);
#else
    setenv(name, value, 1);
#endif
}

static std::string env_or_empty(const char* name)
{
    const char* e = getenv(name);
    return (e && *e) ? std::string(e) : std::string();
}

/* flag, then env, then default */
static std::string pick(const std::string& flag, const char* env, const std::string& def)
{
    if (!flag.empty()) return flag;
    std::string e = env ? env_or_empty(env) : std::string();
    return e.empty() ? def : e;
}

void cli_resolve(const CliOptions& o, const std::string& exe_dir, ResolvedPaths& r)
{
    r.vfs_root = pick(o.game_dir, "PS3_VFS_ROOT", "");
    if (r.vfs_root.empty()) {
        std::string d = exe_dir + "/game";
        if (!o.elf.empty() && o.elf_was_positional) {
            /* Old behavior: <root>/PS3_GAME/USRDIR/EBOOT.elf -> <root>. */
            std::string e = o.elf;
            slashes(e);
            for (int i = 0; i < 3; i++) {
                size_t c = e.rfind('/');
                if (c == std::string::npos) { e.clear(); break; }
                e.resize(c);
            }
            d = e.empty() ? "." : e;
        }
        r.vfs_root = d;
    }
    slashes(r.vfs_root);

    r.elf = o.elf.empty() ? r.vfs_root + "/USRDIR/EBOOT.elf" : o.elf;
    r.hdd0     = pick(o.hdd0,     "PS3_HDD0_ROOT",     exe_dir + "/hdd0");
    r.hdd1     = pick(o.hdd1,     "PS3_HDD1_ROOT",     exe_dir + "/hdd1");
    r.savedata = pick(o.savedata, "PS3_SAVEDATA_ROOT", exe_dir + "/savedata");
    r.title    = pick(o.title,    "PS3_TITLE",         "");
    r.log_dir  = exe_dir + "/logs";
    slashes(r.hdd0); slashes(r.hdd1); slashes(r.savedata);

    r.verbose = 0;
    if (o.verbose >= 0) r.verbose = o.verbose;
    else { std::string v = env_or_empty("PS3_VERBOSE"); if (!v.empty()) r.verbose = atoi(v.c_str()); }

    if (!o.log_file.empty()) {
        std::string l = o.log_file;
        slashes(l);
        bool absolute = l[0] == '/' || (l.size() > 1 && l[1] == ':');
        bool has_dir  = l.find('/') != std::string::npos;
        r.log_file = (absolute || has_dir) ? l : r.log_dir + "/" + l;
    }
}
