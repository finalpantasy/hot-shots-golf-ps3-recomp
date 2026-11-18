/* Command-line options for the runner. Parsing and default resolution only;
 * main.cpp decides what to do with the result. */
#ifndef PORT_CLI_OPTIONS_H
#define PORT_CLI_OPTIONS_H

#include <string>

#define PORT_VERSION_STRING "hotshots-port 0.1 (ps3recomp 0.19.0)"

struct CliOptions {
    /* Raw values from the command line; empty / 0 / -1 means "not given". */
    std::string elf;          /* --elf, or the positional argument */
    std::string game_dir;     /* --game-dir (VFS root) */
    std::string hdd0;
    std::string hdd1;
    std::string savedata;
    std::string title;        /* window caption */
    std::string log_file;     /* --log */
    int  verbose    = -1;     /* --verbose <n> */
    int  width      = 0;      /* --width, 0 = default */
    int  height     = 0;
    int  exit_after = 0;      /* --exit-after <seconds>, 0 = never */
    bool fullscreen = false;
    bool windowed   = false;
    bool hidden     = false;
    bool help       = false;
    bool version    = false;
    bool elf_was_positional = false;
};

/* Fills `o` from argv. Returns false and sets `err` on a bad flag or value. */
bool cli_parse(int argc, char** argv, CliOptions& o, std::string& err);

/* Text for --help. */
const char* cli_help_text(void);

/* Directory the executable lives in, no trailing slash, forward slashes. */
std::string cli_exe_dir(const char* argv0);

/* Final paths after applying precedence: CLI flag, then environment variable,
 * then the portable default under the executable's folder. */
struct ResolvedPaths {
    std::string vfs_root;
    std::string elf;
    std::string hdd0;
    std::string hdd1;
    std::string savedata;
    std::string log_dir;
    std::string log_file;     /* empty = log to the console */
    std::string title;        /* empty = use the title from PARAM.SFO */
    int verbose = 0;
};

void cli_resolve(const CliOptions& o, const std::string& exe_dir, ResolvedPaths& r);

/* Set an environment variable (the runtime reads its roots from the
 * environment). Overwrites. */
void cli_setenv(const char* name, const char* value);

#endif
