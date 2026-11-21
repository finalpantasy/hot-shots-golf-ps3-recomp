#include "cli_options.h"

#include <cerrno>
#include <climits>
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
"Usage: HotShotsGolfRecomp [options] [path/to/EBOOT.elf]\n"
"\n"
"Default paths start next to the executable or in the folder set by --build-dir.\n"
"Command-line flags take precedence over environment variables.\n"
"\n"
"  --elf <file>        PPU ELF to boot. Default: <game-dir>/USRDIR/EBOOT.elf.\n"
"                      A bare path with no flag also works.\n"
"  --build-dir <dir>   Base folder for game files and runtime storage.\n"
"  --game-dir <dir>    Game folder (VFS root, holds PARAM.SFO and USRDIR).\n"
"                      Env PS3_VFS_ROOT. Default: <build dir>/game, then <build dir>.\n"
"  --hdd0 <dir>        Folder for /dev_hdd0. Env PS3_HDD0_ROOT. Default: <build dir>/hdd0.\n"
"  --hdd1 <dir>        Folder for /dev_hdd1. Env PS3_HDD1_ROOT. Default: <build dir>/hdd1.\n"
"  --savedata <dir>    Save data folder. Env PS3_SAVEDATA_ROOT. Default: <build dir>/savedata.\n"
"  --dev-flash <dir>   Firmware folder. Env PS3_DEV_FLASH. Default: <build dir>/dev_flash.\n"
"  --title <text>      Window caption. Env PS3_TITLE. Default: TITLE from PARAM.SFO.\n"
"  --fullscreen        Cover the primary monitor with a borderless window (Windows).\n"
"  --windowed          Start in a window (default).\n"
"  --width <px>        Window width. Default 1280.\n"
"  --height <px>       Window height. Default 720.\n"
"  --aspect <mode>     stretch (default) or fit: center 16:9 without distortion.\n"
"                      Env RSX_ASPECT.\n"
"  --verbose <n>       Runtime diagnostics: 0 off, 1 to 9 on. Env PS3_VERBOSE.\n"
"  --rsx-shader-cache <dir|0>  D3D12 bytecode cache directory or 0 to disable.\n"
"                      Env RSX_SHADER_CACHE. Default: <build dir>/shader_cache_d3d12.\n"
"  --rsx-disp-tex <0|1>  Sample the D3D12 display buffer as a texture.\n"
"                      Env RSX_DISP_TEX. Default: 1 (on).\n"
"  --rsx-disp-depth-tex <0|1>  Sample GPU display depth as a texture.\n"
"                      Env RSX_DISP_DEPTH_TEX. Enabled by default.\n"
"  --rsx-disp-depth-keep <0|1>  Preserve display depth across offscreen passes.\n"
"                      Env RSX_DISP_DEPTH_KEEP. Enabled by default.\n"
"  --rsx-keep-display <0|1>  Restore display color for batches without a clear.\n"
"                      Env RSX_KEEP_DISPLAY. Enabled by default.\n"
"  --rsx-vp-scale <0|1>  Scale the D3D12 viewport to the backbuffer.\n"
"                      Env RSX_VP_SCALE. Enabled by default.\n"
"  --rsx-flip-mark <0|1>  Present at the D3D12 flip marker.\n"
"                      Env RSX_FLIP_MARK. Enabled by default.\n"
"  --gcm-flip-wrap-wait <0|1>  Wait for the RSX walker when the flip FIFO wraps.\n"
"                      Env GCM_FLIP_WRAP_WAIT. Enabled by default.\n"
"  --gcm-fifo-kick <0|1>  Wake the frame clock on a FIFO kick.\n"
"                      Env GCM_FIFO_KICK. Enabled by default.\n"
"  --rsx-full-split <0|1>  Submit a full D3D12 batch with display draws.\n"
"                      Env RSX_FULL_SPLIT. Enabled by default.\n"
"  --rsx-vs-memo <0|1>  Reuse recently decoded vertex shader slots.\n"
"                      Env RSX_VS_MEMO. Enabled by default.\n"
"  --rsx-pso-reuse <0|1>  Reuse pipeline state from the render prepass.\n"
"                      Env RSX_PSO_REUSE. Enabled by default.\n"
"  --rsx-tex-memo <0|1>  Reuse texture lookups within a frame.\n"
"                      Env RSX_TEX_MEMO. Enabled by default.\n"
"  --rsx-srv-dedup <0|1>  Reuse matching shader resource descriptor tables.\n"
"                      Env RSX_SRV_DEDUP. Enabled by default.\n"
"  --rsx-vtx-fast <0|1>  Use the per-draw vertex fetch plan.\n"
"                      Env RSX_VTX_FAST. Enabled by default.\n"
"  --rsx-strip-ix <0|1>  Use indices for triangle strips, fans, and polygons.\n"
"                      Env RSX_STRIP_IX. Enabled by default.\n"
"  --rsx-prof <0|1|2>  D3D12 timing. Use 1 for a summary or 2 for details.\n"
"                      Env RSX_PROF. Disabled by default.\n"
"  --rsx-speed-check <n>  Compare optimized results with the original path.\n"
"                      Env RSX_SPEED_CHECK. 0 disables. Report with --rsx-prof.\n"
"  --mute              Silence Windows audio output while the mixer keeps running.\n"
"                      Env PS3_MUTE.\n"
"  --audio-wav <file>  Record the stereo audio mix to a WAV file.\n"
"                      Env AUDIO_WAV. Disabled by default.\n"
"  --tex-dump <dir>    Dump stable game textures for an HD pack. Env TEX_DUMP.\n"
"  --tex-replace <dir> Load matching PNG/DDS textures from an HD pack.\n"
"                      Env TEX_REPLACE. Disabled by default.\n"
"  --tex-replace-mb <MB>  GPU memory budget for replacement textures.\n"
"                      Env TEX_REPLACE_MB. Default: 768.\n"
"  --jc-parallel <n>   SPURS job-chain lanes, 0 to 8. Use 0 or 1 for serial.\n"
"                      Env JC_PARALLEL. Default: 4.\n"
"  --pad-script-hold <polls>  Positive poll count for each scripted press.\n"
"                      Env PAD_SCRIPT_HOLD. Default: 40.\n"
"  --log <file>        Write all output to this file. A bare name goes in\n"
"                      <build dir>/logs. Default: console.\n"
"  --hidden            Create the window without showing it or taking focus.\n"
"                      For automated test runs on Windows.\n"
"  --exit-after <sec>  Quit cleanly after this many seconds.\n"
"  --help              Show this text.\n"
"  --version           Show the version.\n";

const char* cli_help_text(void) { return kHelp; }

static bool take_value(int argc, char** argv, int& i, const char* eq_val,
                       std::string& out, std::string& err)
{
    if (eq_val) { out = eq_val; return true; }
    if (i + 1 >= argc || strncmp(argv[i + 1], "--", 2) == 0) {
        err = std::string("missing value for ") + argv[i];
        return false;
    }
    out = argv[++i];
    return true;
}

static bool to_int(const std::string& s, int lo, int hi, int& out, const char* flag,
                   std::string& err)
{
    char* end = nullptr;
    errno = 0;
    long v = strtol(s.c_str(), &end, 10);
    if (end == s.c_str() || *end || errno == ERANGE || v < lo || v > hi) {
        err = std::string("bad value '") + s + "' for " + flag;
        return false;
    }
    out = (int)v;
    return true;
}

static bool take_switch(int argc, char** argv, int& i, const char* eq_val,
                        const std::string& name, int& out, std::string& err)
{
    std::string value;
    return take_value(argc, argv, i, eq_val, value, err) &&
           to_int(value, 0, 1, out, name.c_str(), err);
}

struct RsxOption {
    const char* flag;
    const char* env;
    int CliOptions::*value;
    int max;
};

static constexpr RsxOption kRsxOptions[] = {
    {"--rsx-disp-tex", "RSX_DISP_TEX", &CliOptions::rsx_disp_tex, 1},
    {"--rsx-disp-depth-tex", "RSX_DISP_DEPTH_TEX", &CliOptions::rsx_disp_depth_tex, 1},
    {"--rsx-disp-depth-keep", "RSX_DISP_DEPTH_KEEP", &CliOptions::rsx_disp_depth_keep, 1},
    {"--rsx-keep-display", "RSX_KEEP_DISPLAY", &CliOptions::rsx_keep_display, 1},
    {"--rsx-vp-scale", "RSX_VP_SCALE", &CliOptions::rsx_vp_scale, 1},
    {"--rsx-flip-mark", "RSX_FLIP_MARK", &CliOptions::rsx_flip_mark, 1},
    {"--rsx-full-split", "RSX_FULL_SPLIT", &CliOptions::rsx_full_split, 1},
    {"--rsx-vs-memo", "RSX_VS_MEMO", &CliOptions::rsx_vs_memo, 1},
    {"--rsx-pso-reuse", "RSX_PSO_REUSE", &CliOptions::rsx_pso_reuse, 1},
    {"--rsx-tex-memo", "RSX_TEX_MEMO", &CliOptions::rsx_tex_memo, 1},
    {"--rsx-srv-dedup", "RSX_SRV_DEDUP", &CliOptions::rsx_srv_dedup, 1},
    {"--rsx-vtx-fast", "RSX_VTX_FAST", &CliOptions::rsx_vtx_fast, 1},
    {"--rsx-strip-ix", "RSX_STRIP_IX", &CliOptions::rsx_strip_ix, 1},
    {"--rsx-prof", "RSX_PROF", &CliOptions::rsx_prof, 2},
    {"--rsx-speed-check", "RSX_SPEED_CHECK", &CliOptions::rsx_speed_check, INT_MAX},
};

static const RsxOption* find_rsx_option(const std::string& flag)
{
    for (const auto& option : kRsxOptions) {
        if (flag == option.flag) return &option;
    }
    return nullptr;
}

bool cli_has_d3d12_options(const CliOptions& o)
{
    if (!o.rsx_shader_cache.empty() || !o.tex_dump.empty() || !o.aspect.empty() ||
        !o.tex_replace.empty() || o.tex_replace_mb >= 0) return true;
    for (const auto& option : kRsxOptions) {
        if (o.*option.value >= 0) return true;
    }
    return false;
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
        else if (name == "--mute") {
            if (eq_val) { err = "--mute takes no value"; return false; }
            o.mute = true;
        }
        else if (name == "--elf")        { if (!take_value(argc, argv, i, eq_val, o.elf, err)) return false;
                                           o.elf_was_positional = false; }
        else if (name == "--game-dir")   { if (!take_value(argc, argv, i, eq_val, o.game_dir, err)) return false; }
        else if (name == "--build-dir")  { if (!take_value(argc, argv, i, eq_val, o.build_dir, err)) return false; }
        else if (name == "--dev-flash")  { if (!take_value(argc, argv, i, eq_val, o.dev_flash, err)) return false; }
        else if (name == "--hdd0")       { if (!take_value(argc, argv, i, eq_val, o.hdd0, err)) return false; }
        else if (name == "--hdd1")       { if (!take_value(argc, argv, i, eq_val, o.hdd1, err)) return false; }
        else if (name == "--savedata")   { if (!take_value(argc, argv, i, eq_val, o.savedata, err)) return false; }
        else if (name == "--title")      { if (!take_value(argc, argv, i, eq_val, o.title, err)) return false; }
        else if (name == "--log")        { if (!take_value(argc, argv, i, eq_val, o.log_file, err)) return false; }
        else if (name == "--width")      { if (!take_value(argc, argv, i, eq_val, v, err)) return false;
                                           if (!to_int(v, 160, 16384, o.width, "--width", err)) return false; }
        else if (name == "--height")     { if (!take_value(argc, argv, i, eq_val, v, err)) return false;
                                           if (!to_int(v, 90, 16384, o.height, "--height", err)) return false; }
        else if (name == "--aspect") {
            if (!take_value(argc, argv, i, eq_val, o.aspect, err)) return false;
            if (o.aspect != "stretch" && o.aspect != "fit") {
                err = "--aspect requires 'stretch' or 'fit'";
                return false;
            }
        }
        else if (name == "--verbose")    { if (!take_value(argc, argv, i, eq_val, v, err)) return false;
                                           if (!to_int(v, 0, 9, o.verbose, "--verbose", err)) return false; }
        else if (name == "--rsx-shader-cache") {
            if (!take_value(argc, argv, i, eq_val, o.rsx_shader_cache, err)) return false;
            if (o.rsx_shader_cache.empty()) {
                err = "--rsx-shader-cache requires a directory or 0";
                return false;
            }
        }
        else if (name == "--audio-wav") {
            if (!take_value(argc, argv, i, eq_val, o.audio_wav, err)) return false;
            if (o.audio_wav.empty()) {
                err = "--audio-wav requires a file";
                return false;
            }
        }
        else if (name == "--tex-dump" || name == "--tex-replace") {
            std::string& path = name == "--tex-dump" ? o.tex_dump : o.tex_replace;
            if (!take_value(argc, argv, i, eq_val, path, err)) return false;
            if (path.empty()) {
                err = name + " requires a directory";
                return false;
            }
        }
        else if (name == "--tex-replace-mb") {
            if (!take_value(argc, argv, i, eq_val, v, err) ||
                !to_int(v, 1, 65536, o.tex_replace_mb, "--tex-replace-mb", err)) return false;
        }
        else if (const auto* option = find_rsx_option(name)) {
            if (!take_value(argc, argv, i, eq_val, v, err) ||
                !to_int(v, 0, option->max, o.*option->value, option->flag, err)) return false;
        }
        else if (name == "--gcm-flip-wrap-wait") {
            if (!take_switch(argc, argv, i, eq_val, name, o.gcm_flip_wrap_wait, err)) return false;
        }
        else if (name == "--gcm-fifo-kick") {
            if (!take_switch(argc, argv, i, eq_val, name, o.gcm_fifo_kick, err)) return false;
        }
        else if (name == "--jc-parallel") {
            if (!take_value(argc, argv, i, eq_val, v, err) ||
                !to_int(v, 0, 8, o.jc_parallel, "--jc-parallel", err)) return false;
        }
        else if (name == "--pad-script-hold") {
            if (!take_value(argc, argv, i, eq_val, v, err) ||
                !to_int(v, 1, INT_MAX, o.pad_script_hold, "--pad-script-hold", err)) return false;
        }
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
    if (cut == 0) return "/";
#ifdef _WIN32
    if (cut == 2 && path[1] == ':') return path.substr(0, 3);
#endif
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
    r.build_dir = o.build_dir.empty() ? exe_dir : o.build_dir;
    slashes(r.build_dir);
    r.vfs_root = pick(o.game_dir, "PS3_VFS_ROOT", "");
    if (r.vfs_root.empty()) {
        std::string d = r.build_dir + "/game";
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
    r.hdd0     = pick(o.hdd0,     "PS3_HDD0_ROOT",     r.build_dir + "/hdd0");
    r.hdd1     = pick(o.hdd1,     "PS3_HDD1_ROOT",     r.build_dir + "/hdd1");
    r.savedata = pick(o.savedata, "PS3_SAVEDATA_ROOT",
                     pick("", "PS3_GAMEDATA_ROOT", r.build_dir + "/savedata"));
    r.title    = pick(o.title,    "PS3_TITLE",         "");
    r.log_dir  = r.build_dir + "/logs";
    r.audio_wav = o.audio_wav;
    r.tex_dump = pick(o.tex_dump, "TEX_DUMP", "");
    r.tex_replace = pick(o.tex_replace, "TEX_REPLACE", "");
    slashes(r.audio_wav); slashes(r.tex_dump); slashes(r.tex_replace);
#ifdef _WIN32
    r.rsx_shader_cache = o.rsx_shader_cache;
    if (r.rsx_shader_cache.empty() && env_or_empty("RSX_SHADER_CACHE").empty())
        r.rsx_shader_cache = r.build_dir + "/shader_cache_d3d12";
#endif
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

void cli_apply_tuning(const CliOptions& o, const ResolvedPaths& r)
{
    if (!r.rsx_shader_cache.empty()) cli_setenv("RSX_SHADER_CACHE", r.rsx_shader_cache.c_str());
    if (o.mute) cli_setenv("PS3_MUTE", "1");
    if (!o.aspect.empty()) cli_setenv("RSX_ASPECT", o.aspect.c_str());
    if (!r.audio_wav.empty()) cli_setenv("AUDIO_WAV", r.audio_wav.c_str());
    if (!r.tex_dump.empty()) cli_setenv("TEX_DUMP", r.tex_dump.c_str());
    if (!r.tex_replace.empty()) cli_setenv("TEX_REPLACE", r.tex_replace.c_str());
    if (o.tex_replace_mb >= 0) cli_setenv("TEX_REPLACE_MB", std::to_string(o.tex_replace_mb).c_str());
    for (const auto& option : kRsxOptions) {
        const int value = o.*option.value;
        if (value >= 0) cli_setenv(option.env, std::to_string(value).c_str());
    }
    if (o.gcm_flip_wrap_wait >= 0) cli_setenv("GCM_FLIP_WRAP_WAIT", o.gcm_flip_wrap_wait ? "1" : "0");
    if (o.gcm_fifo_kick >= 0) cli_setenv("GCM_FIFO_KICK", o.gcm_fifo_kick ? "1" : "0");
    if (o.jc_parallel >= 0) cli_setenv("JC_PARALLEL", std::to_string(o.jc_parallel).c_str());
    if (o.pad_script_hold >= 0) cli_setenv("PAD_SCRIPT_HOLD", std::to_string(o.pad_script_hold).c_str());
}
