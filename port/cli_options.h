/* Command-line parsing, default resolution, and runtime tuning for the runner. */
#ifndef PORT_CLI_OPTIONS_H
#define PORT_CLI_OPTIONS_H

#include <string>

#define PORT_VERSION_STRING "hotshots-port 0.1 (ps3recomp 0.19.0)"

struct CliOptions {
    /* Raw values from the command line; empty / 0 / -1 means "not given". */
    std::string elf;          /* --elf, or the positional argument */
    std::string game_dir;     /* --game-dir (VFS root) */
    std::string build_dir;
    std::string dev_flash;
    std::string hdd0;
    std::string hdd1;
    std::string savedata;
    std::string title;        /* window caption */
    std::string log_file;     /* --log */
    std::string rsx_shader_cache;
    std::string audio_wav;
    int  verbose    = -1;     /* --verbose <n> */
    int  width      = 0;      /* --width, 0 = default */
    int  height     = 0;
    int  exit_after = 0;      /* --exit-after <seconds>, 0 = never */
    int  rsx_disp_tex = -1;
    int  rsx_disp_depth_tex = -1;
    int  rsx_disp_depth_keep = -1;
    int  rsx_keep_display = -1;
    int  rsx_vp_scale = -1;
    int  rsx_flip_mark = -1;
    int  gcm_flip_wrap_wait = -1;
    int  gcm_fifo_kick = -1;
    int  rsx_full_split = -1;
    int  rsx_vs_memo = -1;
    int  rsx_pso_reuse = -1;
    int  rsx_tex_memo = -1;
    int  rsx_srv_dedup = -1;
    int  rsx_vtx_fast = -1;
    int  rsx_strip_ix = -1;
    int  rsx_prof = -1;
    int  rsx_speed_check = -1;
    int  jc_parallel = -1;
    int  pad_script_hold = -1;
    bool fullscreen = false;
    bool windowed   = false;
    bool hidden     = false;
    bool mute       = false;
    bool help       = false;
    bool version    = false;
    bool elf_was_positional = false;
};

/* Fills `o` from argv. Returns false and sets `err` on a bad flag or value. */
bool cli_parse(int argc, char** argv, CliOptions& o, std::string& err);

/* True when the command line explicitly selects D3D12 tuning. */
bool cli_has_d3d12_options(const CliOptions& o);

/* Text for --help. */
const char* cli_help_text(void);

/* Directory the executable lives in, no trailing slash, forward slashes. */
std::string cli_exe_dir(const char* argv0);

/* Final paths after applying precedence: CLI flag, then environment variable,
 * then the portable default under the executable's folder. */
struct ResolvedPaths {
    std::string build_dir;
    std::string vfs_root;
    std::string elf;
    std::string hdd0;
    std::string hdd1;
    std::string savedata;
    std::string log_dir;
    std::string log_file;     /* empty = log to the console */
    std::string rsx_shader_cache; /* empty = inherit, "0" = disable */
    std::string audio_wav;    /* empty = inherit */
    std::string title;        /* empty = use the title from PARAM.SFO */
    int verbose = 0;
};

void cli_resolve(const CliOptions& o, const std::string& exe_dir, ResolvedPaths& r);

/* Export tuning values before the runtime reads the environment. */
void cli_apply_tuning(const CliOptions& o, const ResolvedPaths& r);

/* Set an environment variable (the runtime reads its roots from the
 * environment). Overwrites. */
void cli_setenv(const char* name, const char* value);

#endif
