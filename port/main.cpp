/*
 * ps3recomp game project -- entry point template.
 *
 * This is the runner. It boots a lifted title through the toolkit's PPU
 * scaffold: allocate the flat guest VM, load the PPU ELF named on the command
 * line, register the lifted function table and the HLE NID handlers, start a
 * frame clock, and dispatch the entry OPD.
 *
 * The scaffold does the work; nothing below reimplements it. ppu_load_elf,
 * ppu_recomp_register, ppu_hle_init, ppu_sysprx_register, ppu_fs_register,
 * lv2_init_syscalls and ppu_run all come from the toolkit, compiled into this
 * project from PS3RECOMP_DIR (see CMakeLists.txt). What is left here is the
 * part a port owns: which backend to present through, how the frame clock is
 * paced, and whatever diagnostics the title turns out to need.
 *
 * runtime/ppu/tests/boot_main.cpp in the toolkit is the same boot in its
 * fully-instrumented form -- crash filter, hang watchdog, guest-PC sampling
 * profiler. Read it when a boot goes wrong; copy from it what the title
 * needs. It is deliberately not what a fresh project starts with.
 *
 * The one part that IS duplicated from it is the frame clock below, because a
 * port is expected to change its pacing and a shared one would be the wrong
 * shape for that. It was copied faithfully, comments and all. If a pacing bug
 * is fixed in one of the two, look at the other.
 *
 * This builds on Windows, macOS and Linux. CI builds and runs it against the
 * boot smoke title on the last two, and compile-checks it against clang-cl on
 * the first (tools/check_ppu_scaffold.py).
 */

/* The lifter's generated header, which declares ppu_context and the function
 * table. It comes first: everything below is written against that struct. */
#include "ppu_recomp.h"

/* The Win32 names -- Sleep, GetTickCount64, CreateThread, InterlockedIncrement,
 * VirtualAlloc, the scalar typedefs -- from one place. On Windows this is a
 * passthrough to <windows.h>; off Windows the toolkit's shim supplies the same
 * names over pthreads and mmap, so the call sites below are written once. */
#include "win32_compat.h"
#include "cli_options.h"

#include <chrono>
#include <filesystem>
#include <memory>
#include <string>

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifndef _WIN32
#include <sys/stat.h>
#include <sys/mman.h>   /* mmap: the guest arena, see alloc_guest_vm */
#include <unistd.h>
#endif

#if defined(__APPLE__)
#include <CoreFoundation/CoreFoundation.h>   /* the main thread's run loop, see run_guest */
#include <pthread.h>
#endif

#ifdef _WIN32
/* timeBeginPeriod: <windows.h> arrives with WIN32_LEAN_AND_MEAN set, which
 * excludes the multimedia timer API, so it is asked for by name -- and after
 * windows.h, since timeapi.h uses UINT. No shim exists off Windows because
 * there is nothing to shim: the 15.6 ms default timer granularity this works
 * around is a Windows problem. */
#include <timeapi.h>
#include <bcrypt.h>
#include <io.h>
#include <share.h>
#endif

/* ---------------------------------------------------------------------------
 * What the scaffold gives this file
 * -----------------------------------------------------------------------*/
extern "C" {
uint32_t ppu_load_elf(const char* path);      /* ELF -> guest RAM, returns entry OPD */
void     ppu_recomp_register(void);           /* generated: lifted table -> address map */
void     ppu_hle_init(void);                  /* firmware import NID -> HLE handler */
void     ppu_sysprx_register(void);           /* boot-critical CRT (sys_initialize_tls, ...) */
void     ppu_fs_register(void);               /* cellFs over the real game directory */
void     lv2_init_syscalls(void);             /* the lv2 syscall table */
int      ppu_run(uint32_t entry_opd, uint32_t stack_top);

/* This project's own: load whatever real system PRX modules the title needs
 * into guest RAM and register their exports. stubs.cpp has the empty version
 * a game with no lifted PRX wants. */
void     ps3_load_prx_modules(void);
void     ps3_register_peripheral_imports(void);

extern const char* ppu_vfs_root;              /* host dir the PS3 mount points map into */
int      cellGame_init_from_paramsfo(const char* sfo_path);   /* cellGame.c: 0 ok, -1 failed */
const char* cellGame_get_title(void);
const char* cellGame_get_title_id(void);
void     ps3_host_quit(const char* why);      /* cellSysutil.c: REQUEST_EXITGAME, then exit 0 */

/* sys_ppu_thread.c: the main thread's stack, as sys_ppu_thread_get_stack_information
 * reports it. Left at 0 it names VM_STACK_BASE, the first created thread's stack. */
extern uint32_t g_ppu_main_stack_addr;
extern uint32_t g_ppu_main_stack_size;

/* The status the guest handed to sys_process_exit. A title that exits that way
 * never returns through ppu_run, so this is only read on the path where the
 * entry function unwound instead. */
extern int     g_sys_process_exit_called;
extern int32_t g_sys_process_exit_code;

/* Host-provided symbols the runtime and the HLE libraries link against. */
uint8_t* vm_base = nullptr;
extern uint32_t ppu_vm_size;                  /* ppu_loader.cpp: the OOB guard */

/* Guest-callback dispatch. g_ps3_guest_caller is the hook the HLE runtime
 * calls back into recompiled code through -- cellSysutil events and the GCM
 * vblank/flip handlers. ppu_guest_call does the OPD -> dispatch. */
typedef void (*ps3_guest_caller_fn)(uint32_t, uint64_t, uint64_t, uint64_t, uint64_t,
                                    uint64_t, uint64_t, uint64_t, uint64_t);
extern ps3_guest_caller_fn g_ps3_guest_caller;
uint64_t ppu_guest_call(uint32_t, uint64_t, uint64_t, uint64_t, uint64_t,
                        uint64_t, uint64_t, uint64_t, uint64_t);

/* The GCM half of the frame clock. */
void     cellGcmTickVBlank(void);
void     cellGcmTickFlip(void);
int      cellGcm_take_flip_pending(void);
void     cellGcm_rsx_process_fifo(void);      /* drain get -> put */
void     cellGcm_fifo_kick_wait(unsigned ms);
unsigned cellGcm_flip_request_count(void);
}

/* ---------------------------------------------------------------------------
 * RSX present backend
 * -----------------------------------------------------------------------*/
/* D3D12 on Windows, Metal on Apple, and the null backend's headless software
 * path anywhere else -- the same selection runtime/host/host_posix.c and the
 * toolkit's boot harness make. All three expose the same three entry points,
 * so the frame clock below is backend-agnostic. */
#if defined(_WIN32)
extern "C" int  rsx_d3d12_backend_init(uint32_t w, uint32_t h, const char* title);
extern "C" void rsx_d3d12_backend_set_window_mode(int fullscreen, int hidden);
extern "C" void rsx_d3d12_backend_present(void);
extern "C" int  rsx_d3d12_backend_pump_messages(void);
#  define rsx_backend_init    rsx_d3d12_backend_init
#  define rsx_backend_present rsx_d3d12_backend_present
#  define rsx_backend_pump    rsx_d3d12_backend_pump_messages
#  define RSX_BACKEND_NAME    "D3D12"
#elif defined(__APPLE__)
extern "C" int  rsx_metal_backend_init(uint32_t w, uint32_t h, const char* title);
extern "C" void rsx_metal_backend_present(void);
extern "C" int  rsx_metal_backend_pump_messages(void);
#  define rsx_backend_init    rsx_metal_backend_init
#  define rsx_backend_present rsx_metal_backend_present
#  define rsx_backend_pump    rsx_metal_backend_pump_messages
#  define RSX_BACKEND_NAME    "Metal"
#elif defined(PS3RECOMP_RSX_VULKAN)
extern "C" int  rsx_vulkan_backend_init(uint32_t w, uint32_t h, const char* title);
extern "C" void rsx_vulkan_backend_present(void);
extern "C" int  rsx_vulkan_backend_pump_messages(void);
#  define rsx_backend_init    rsx_vulkan_backend_init
#  define rsx_backend_present rsx_vulkan_backend_present
#  define rsx_backend_pump    rsx_vulkan_backend_pump_messages
#  define RSX_BACKEND_NAME    "Vulkan"
#else
extern "C" int  rsx_null_backend_init(uint32_t w, uint32_t h, const char* title);
extern "C" void rsx_null_backend_present(void);
extern "C" int  rsx_null_backend_pump_messages(void);
#  define rsx_backend_init    rsx_null_backend_init
#  define rsx_backend_present rsx_null_backend_present
#  define rsx_backend_pump    rsx_null_backend_pump_messages
#  define RSX_BACKEND_NAME    "null (headless software)"
#endif

/* ---------------------------------------------------------------------------
 * Configuration
 * -----------------------------------------------------------------------*/
/* The flat VM must span every region the PS3 memory map uses, not just the
 * game image: sys_ppu_thread_create puts thread stacks at 0xD0000000, so a
 * smaller arena makes every spawned thread's stack access out of bounds. */
#define VM_SIZE       0x100010000ull   /* the full 32-bit guest space + a 64K guard */
#define STACK_TOP     0x0FF00000u      /* main-thread stack, below the 0x10000000 segment */
#define STACK_SIZE    0x00100000u      /* what the main thread is told it has */
#define WINDOW_WIDTH  1280
#define WINDOW_HEIGHT 720

/* Set from the command line before the frame clock starts. */
static std::string g_window_title;
static uint32_t    g_window_w = WINDOW_WIDTH;
static uint32_t    g_window_h = WINDOW_HEIGHT;
static bool        g_window_hidden = false;

/* ---------------------------------------------------------------------------
 * Frame clock
 * -----------------------------------------------------------------------*/
/* On real hardware the RSX raises a vblank interrupt about 60 times a second
 * and that is what drives the game's frame loop. With no RSX it is synthesized
 * here: a host thread calls cellGcmTickVBlank/TickFlip, which invoke the
 * handlers the guest registered, and drains the GCM FIFO. Without this the
 * title initialises, registers its handlers and then waits forever.
 *
 * The ticks are driven off real elapsed time rather than off how long present()
 * took. A hidden or occluded window makes present block hard, and pacing the
 * ticks behind it paces the whole game behind it. */
static volatile LONG g_frames_presented = 0;

/* Frames handed to the backend at a guest FLIP boundary -- one per frame the
 * guest actually finished. The presents made before the guest's first flip, so
 * a fresh window is not left blank through a long boot, carry no guest frame
 * and are deliberately not counted. */
extern "C" unsigned ppu_boot_frames_presented(void)
{
    return (unsigned)g_frames_presented;
}

static void present_guest_frame(void)
{
    rsx_backend_present();
    /* This thread increments and guest threads read, so interlocked rather
     * than a volatile ++, which on arm64 is neither atomic nor a fence. */
    InterlockedIncrement(&g_frames_presented);
}

/* FRAME_WD=<ms>: watch the frame clock thread (FIFO walker, present and the
 * Win32 message pump). When one pass of its loop takes longer than <ms>, the
 * window stops answering (Windows shows "Not Responding" after 5 s): log the
 * stall and its host call stack (image RVAs; symbolize with llvm-nm), again
 * every <ms> while it lasts, and its length when it ends. Off by default. */
static volatile LONG g_fc_beat = 0;
#ifdef _WIN32
static HANDLE g_fc_thread = NULL;
/* The game window, for IsHungAppWindow: whether Windows counts it as Not
 * Responding (its thread has not read its message queue for 5 s). With
 * RT_WINDOW_THREAD (default) the window has a thread of its own and this stays
 * 0 through frame-thread stalls. */
static int fc_wd_window_hung(void)
{
    HWND w = NULL;
    while ((w = FindWindowExA(NULL, w, "ps3recomp_d3d12", NULL)) != NULL) {
        DWORD pid = 0;
        GetWindowThreadProcessId(w, &pid);
        if (pid == GetCurrentProcessId()) return IsHungAppWindow(w) ? 1 : 0;
    }
    return -1;   /* no window */
}
static int g_fc_hung_samples = 0;
static void fc_wd_sample(unsigned long long stuck_ms)
{
    DWORD64 pcs[32];
    int n = 0;
    if (SuspendThread(g_fc_thread) == (DWORD)-1) return;
    CONTEXT c;
    memset(&c, 0, sizeof c);
    c.ContextFlags = CONTEXT_FULL;
    if (GetThreadContext(g_fc_thread, &c)) {
        /* No CRT, heap or stdio call while the thread is suspended: it may
         * hold their locks. */
        for (; n < 32 && c.Rip; n++) {
            pcs[n] = c.Rip;
            DWORD64 base = 0;
            PRUNTIME_FUNCTION f = RtlLookupFunctionEntry(c.Rip, &base, NULL);
            if (f) {
                PVOID hd; DWORD64 ef;
                RtlVirtualUnwind(UNW_FLAG_NHANDLER, base, c.Rip, f, &c, &hd, &ef, NULL);
            } else {
                c.Rip = *(DWORD64*)c.Rsp;   /* leaf function */
                c.Rsp += 8;
            }
        }
    }
    ResumeThread(g_fc_thread);
    const DWORD64 img = (DWORD64)GetModuleHandleA(NULL);
    char line[2048];
    const int hung = fc_wd_window_hung();
    if (hung > 0) g_fc_hung_samples++;
    int len = snprintf(line, sizeof line, "[FRAME-WD] frame thread stuck %llums (window-hung=%d):", stuck_ms, hung);
    for (int i = 0; i < n && len < (int)sizeof line - 80; i++) {
        HMODULE m = NULL;
        char name[MAX_PATH] = "?";
        if (GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS |
                               GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                               (LPCSTR)pcs[i], &m) && m && (DWORD64)m != img) {
            GetModuleFileNameA(m, name, sizeof name);
            const char* b = strrchr(name, '\\');
            len += snprintf(line + len, sizeof line - len, " %s+0x%llX", b ? b + 1 : name,
                            (unsigned long long)(pcs[i] - (DWORD64)m));
        } else {
            len += snprintf(line + len, sizeof line - len, " 0x%llX",
                            (unsigned long long)(pcs[i] - img));
        }
    }
    fprintf(stderr, "%s\n", line);
    fflush(stderr);
}
static DWORD WINAPI fc_wd(LPVOID p)
{
    const unsigned long long lim = (unsigned long long)(uintptr_t)p;
    LONG last = g_fc_beat;
    unsigned long long since = GetTickCount64(), next = lim, longest = 0;
    int samples = 0;
    for (;;) {
        Sleep(lim >= 400 ? 100 : 25);
        LONG b = g_fc_beat;
        unsigned long long now = GetTickCount64();
        if (b != last) {
            if (next > lim) {
                if (now - since > longest) longest = now - since;
                fprintf(stderr, "[FRAME-WD] frame thread resumed after %llums (longest %llums; window Not Responding samples so far: %d)\n",
                        now - since, longest, g_fc_hung_samples);
            }
            last = b; since = now; next = lim;
            continue;
        }
        if (now - since >= next) {
            if (samples < 400) { samples++; fc_wd_sample(now - since); }
            next += lim;
        }
    }
    return 0;
}
static void fc_wd_start(void)
{
    const char* e = getenv("FRAME_WD");
    int ms = e ? atoi(e) : 0;
    if (ms <= 0) return;
    DuplicateHandle(GetCurrentProcess(), GetCurrentThread(), GetCurrentProcess(), &g_fc_thread,
                    THREAD_SUSPEND_RESUME | THREAD_GET_CONTEXT | THREAD_QUERY_INFORMATION,
                    FALSE, 0);
    if (!g_fc_thread) return;
    fprintf(stderr, "[FRAME-WD] frame thread watchdog armed: %dms\n", ms);
    HANDLE h = CreateThread(NULL, 64u * 1024, fc_wd, (LPVOID)(uintptr_t)ms, 0, NULL);
    if (h) CloseHandle(h);
}
#else
static void fc_wd_start(void) {}
#endif

static DWORD WINAPI frame_clock(LPVOID)
{
    const char* title = g_window_title.empty() ? "ps3recomp" : g_window_title.c_str();
    fc_wd_start();
#ifdef _WIN32
    /* This thread owns the window and pumps its messages between FIFO drains.
     * A drain that compiles shaders or loads HD textures can hold it for 5 to
     * 20 s with a cold shader cache; after 5 s Windows swaps the game window
     * for a "Not Responding" ghost and offers to close it, so a pause reads as
     * a crash. Keep the real window (the game resumes by itself; FRAME_WD logs
     * the stall). RT_WINDOW_GHOSTING=1 keeps the Windows default. */
    {
        const char* g = getenv("RT_WINDOW_GHOSTING");
        if (!(g && g[0] == '1')) DisableProcessWindowsGhosting();
    }
#endif

    int rsx_ok = (rsx_backend_init(g_window_w, g_window_h, title) == 0);
    fprintf(stderr, "[rsx] %s backend init %s\n", RSX_BACKEND_NAME,
            rsx_ok ? (g_window_hidden ? "OK -- window hidden" : "OK -- window open") : "FAILED");

    bool window_open = rsx_ok;
    unsigned  last_flip = 0;
    /* Vblank period from steady_clock (QueryPerformanceCounter on Windows):
     * 59.94 Hz like the PS3's NTSC-rate output. The old GetTickCount64 tick
     * stepped `+= 16` ms in 15.6 ms units, so it ran at 62.5 Hz and the game
     * logic (paced on the vblank count) ran about 4% fast and in bursts.
     * RT_VBLANK_HZ=<hz> overrides (for example 60, or 62.5 for the old rate). */
    double vblank_hz = 59.94;
    if (const char* e = getenv("RT_VBLANK_HZ")) {
        double v = atof(e);
        if (v >= 10.0 && v <= 1000.0) vblank_hz = v;
    }
    fprintf(stderr, "[rsx] vblank ticker %.3f Hz\n", vblank_hz);
    typedef std::chrono::steady_clock vclock;
    const vclock::time_point t0 = vclock::now();
    const double period_s = 1.0 / vblank_hz;
    unsigned long long tick_index = 0;     /* ticks fired since t0 */

    for (;;) {
        /* Wake when a guest thread needs the FIFO walker. */
        cellGcm_fifo_kick_wait(4);
        InterlockedIncrement(&g_fc_beat);   /* FRAME_WD */
        const double now_s =
            std::chrono::duration<double>(vclock::now() - t0).count();

        int fired = 0;
        while ((double)tick_index * period_s <= now_s && fired < 240) {
            cellGcmTickVBlank();
            cellGcmTickFlip();
            /* Present a pending flip BEFORE draining any further. The flip
             * fires at a get==put frame boundary on the guest thread, so the
             * batch held right now is exactly the completed frame; presenting
             * after the drain races the guest's next-frame writes and shows a
             * mixed one. */
            if (rsx_ok && cellGcm_take_flip_pending()) {
                if (window_open) present_guest_frame();
                last_flip = cellGcm_flip_request_count();
            }
            /* Drain the FIFO every tick. This is what writes the RSX sync-fence
             * labels the game's per-frame logic blocks on, so it has to keep
             * advancing at 60 Hz even while present() throttles. */
            if (rsx_ok) cellGcm_rsx_process_fifo();
            tick_index++;
            fired++;
        }
        /* Fell too far behind -- resync to now. */
        if (fired >= 240) tick_index = (unsigned long long)(now_s / period_s) + 1;

        /* Drain at the outer cadence too, not only on the 16 ms tick: titles
         * fence every render pass on a label the drain writes, and one wave of
         * those at 16 ms apiece paces the guest into single-figure frame rates.
         * The real RSX writes them in microseconds. */
        if (rsx_ok) {
            if (cellGcm_take_flip_pending()) {
                if (window_open) present_guest_frame();
                last_flip = cellGcm_flip_request_count();
            }
            cellGcm_rsx_process_fifo();

            if (!window_open) continue;
            if (rsx_backend_pump() != 0) {
                window_open = false;
                /* Keep retiring FIFO fences while the guest handles its
                 * exit callbacks. The backend still owns the GPU resources. */
                ps3_host_quit("window closed");
                continue;
            }
            /* Present on a guest flip. A present on a fixed clock can catch the
             * drain mid-frame and flash a partial one. Before the first flip
             * present freely, so the window is not blank during boot. */
            unsigned fc = cellGcm_flip_request_count();
            if (fc != last_flip) {
                present_guest_frame();
                last_flip = fc;
            } else if (fc == 0) {
                rsx_backend_present();
            }
        }
    }
    return 0;
}

/* ---------------------------------------------------------------------------
 * Helpers
 * -----------------------------------------------------------------------*/
static bool file_exists(const std::string& p)
{
    std::error_code error;
    return std::filesystem::is_regular_file(p, error);
}

static std::string find_game_files(const CliOptions& options, ResolvedPaths& paths)
{
    const std::string sfo = paths.vfs_root + "/PARAM.SFO";
    if (file_exists(sfo) && file_exists(paths.elf)) return sfo;

    const std::string disc = paths.vfs_root + "/PS3_GAME";
    const std::string disc_sfo = disc + "/PARAM.SFO";
    const std::string disc_elf = options.elf.empty() ? disc + "/USRDIR/EBOOT.elf" : paths.elf;
    if (file_exists(disc_sfo) && file_exists(disc_elf)) {
        paths.elf = disc_elf;
        return disc_sfo;
    }

    const char* vfs_environment = getenv("PS3_VFS_ROOT");
    if (options.elf.empty() && options.game_dir.empty() && (!vfs_environment || !*vfs_environment)) {
        const std::string flat_sfo = paths.build_dir + "/PARAM.SFO";
        const std::string flat_elf = paths.build_dir + "/USRDIR/EBOOT.elf";
        if (file_exists(flat_sfo) && file_exists(flat_elf)) {
            paths.vfs_root = paths.build_dir;
            paths.elf = flat_elf;
            return flat_sfo;
        }
    }
    return {};
}

static void keep_explorer_message_open(int argc)
{
#ifdef _WIN32
    DWORD console_processes[2];
    if (argc == 1 && _isatty(_fileno(stdin)) && GetConsoleProcessList(console_processes, 2) == 1) {
        fputs("Press Enter to close.\n", stderr);
        getchar();
    }
#else
    (void)argc;
#endif
}

#ifdef _WIN32
static bool matches_target_elf(FILE* file)
{
    // SHA-256 of the selected profile's decrypted_elf_sha256 in config/target.json.
    static const uint8_t expected[] = {
#ifdef HSG_TARGET_OFFICIAL_1_03
        0x8c, 0xb1, 0x8c, 0x2e, 0xc0, 0x6c, 0x8a, 0x0e,
        0xd2, 0xde, 0x12, 0xd3, 0xdd, 0x3b, 0xdd, 0x09,
        0xca, 0xa3, 0x6a, 0xf5, 0x5d, 0x49, 0xc1, 0x8a,
        0x86, 0x9d, 0xba, 0xc0, 0xf5, 0x2e, 0x14, 0x0b,
#else
        0x42, 0xbd, 0xdd, 0xc5, 0xe4, 0x19, 0xf7, 0xe1,
        0x8b, 0xcb, 0xec, 0xdf, 0x02, 0xeb, 0x24, 0x74,
        0x8d, 0xd1, 0xda, 0x91, 0x1e, 0xa7, 0x25, 0x7d,
        0x86, 0xd8, 0x47, 0x7e, 0x24, 0x77, 0x7a, 0x8b,
#endif
    };
    // Reject incomplete or oversized inputs before the hash reads their data.
    constexpr int64_t expected_size = 14340360;
    if (!file || _fseeki64(file, 0, SEEK_END) != 0 ||
        _ftelli64(file) != expected_size || _fseeki64(file, 0, SEEK_SET) != 0)
        return false;

    BCRYPT_ALG_HANDLE algorithm = nullptr;
    if (BCryptOpenAlgorithmProvider(&algorithm, BCRYPT_SHA256_ALGORITHM, nullptr, 0) != 0)
        return false;

    BCRYPT_HASH_HANDLE hash = nullptr;
    bool matches = false;
    if (BCryptCreateHash(algorithm, &hash, nullptr, 0, nullptr, 0, 0) == 0) {
        uint8_t buffer[64 * 1024];
        size_t total = 0;
        bool read_ok = true;
        while (size_t count = fread(buffer, 1, sizeof buffer, file)) {
            total += count;
            if (total > expected_size ||
                BCryptHashData(hash, buffer, static_cast<ULONG>(count), 0) != 0) {
                read_ok = false;
                break;
            }
        }
        uint8_t digest[sizeof expected];
        matches = read_ok && !ferror(file) && total == expected_size &&
            BCryptFinishHash(hash, digest, sizeof digest, 0) == 0 &&
            memcmp(digest, expected, sizeof expected) == 0;
        BCryptDestroyHash(hash);
    }
    BCryptCloseAlgorithmProvider(algorithm, 0);
    return matches;
}
#endif

static void make_one_dir(const std::string& p)
{
#ifdef _WIN32
    CreateDirectoryA(p.c_str(), NULL);
#else
    mkdir(p.c_str(), 0755);
#endif
}

static void make_dirs(const std::string& path)
{
    std::string t = path;
    for (size_t i = 1; i < t.size(); i++) {
        if (t[i] == '/' || t[i] == '\\') {
            char c = t[i];
            t[i] = 0;
            make_one_dir(t);
            t[i] = c;
        }
    }
    make_one_dir(t);
}

#ifdef _WIN32
static bool configure_windows_profile(const std::string& build_dir)
{
    const auto profile = std::filesystem::path(build_dir) / "cache" / "profile";
    const auto local = profile / "AppData" / "Local";
    const auto local_low = profile / "AppData" / "LocalLow";
    const auto roaming = profile / "AppData" / "Roaming";
    const auto temporary = profile / "Temp";
    for (const auto& directory : {local, local_low, roaming, temporary}) {
        std::error_code error;
        std::filesystem::create_directories(directory, error);
        if (error) {
            fprintf(stderr, "error: cannot create the Windows cache folder under %s (%s)\n",
                    build_dir.c_str(), error.message().c_str());
            return false;
        }
    }

    // Direct3D and the display driver resolve cache folders against this process's profile.
    if (_wputenv_s(L"USERPROFILE", profile.c_str()) ||
        _wputenv_s(L"LOCALAPPDATA", local.c_str()) ||
        _wputenv_s(L"APPDATA", roaming.c_str()) ||
        _wputenv_s(L"TEMP", temporary.c_str()) ||
        _wputenv_s(L"TMP", temporary.c_str())) {
        fprintf(stderr, "error: cannot configure the Windows cache paths under %s\n", build_dir.c_str());
        return false;
    }
    return true;
}
#endif

static bool redirect_log(const std::string& path)
{
    size_t cut = path.rfind('/');
    if (cut != std::string::npos) make_dirs(path.substr(0, cut));
    if (!freopen(path.c_str(), "w", stdout)) return false;

    // Share the file position so one stream cannot overwrite the other.
#ifdef _WIN32
    return _dup2(_fileno(stdout), _fileno(stderr)) == 0;
#else
    return dup2(fileno(stdout), fileno(stderr)) >= 0;
#endif
}

static bool make_absolute(std::string& path)
{
    if (path.empty()) return true;
    std::error_code error;
    const auto resolved = std::filesystem::absolute(path, error);
    if (error) {
        fprintf(stderr, "error: cannot resolve %s (%s)\n", path.c_str(), error.message().c_str());
        return false;
    }
    path = resolved.generic_string();
    return true;
}

static bool resolve_firmware(std::string& roots, const CliOptions& options,
                             const std::string& build_dir)
{
    const char* configured = options.dev_flash.empty() ? getenv("PS3_DEV_FLASH") : options.dev_flash.c_str();
    if (!configured || !*configured) {
        roots = build_dir + "/dev_flash";
        return true;
    }
#ifdef _WIN32
    const char separator = ';';
#else
    const char separator = ':';
#endif
    const std::string list(configured);
    for (size_t start = 0;;) {
        const size_t end = list.find(separator, start);
        std::string root = list.substr(start, end - start);
        if (!make_absolute(root)) return false;
        roots += root;
        if (end == std::string::npos) return true;
        roots += separator;
        start = end + 1;
    }
}

/* --exit-after: a clean quit through the same path the console's Quit Game uses. */
static DWORD WINAPI exit_timer(LPVOID arg)
{
    Sleep((DWORD)((uintptr_t)arg * 1000u));
    ps3_host_quit("--exit-after reached");
    return 0;
}

/* ---------------------------------------------------------------------------
 * Guest VM
 * -----------------------------------------------------------------------*/
#ifdef _WIN32
/* Demand-paging for the flat VM: reserve the whole 4 GB guest space, which
 * costs no commit, and commit each 64 KB page on first access. Every 32-bit
 * guest offset is then valid, so a garbage guest pointer reads zero instead of
 * killing the process. Faults outside the arena fall through untouched. */
static LONG WINAPI vm_commit_veh(EXCEPTION_POINTERS* ep)
{
    if (ep->ExceptionRecord->ExceptionCode == EXCEPTION_ACCESS_VIOLATION) {
        ULONG_PTR fault = ep->ExceptionRecord->ExceptionInformation[1];
        uintptr_t base  = (uintptr_t)vm_base;
        if (vm_base && fault >= base && fault < base + VM_SIZE) {
            void* page = (void*)(fault & ~(uintptr_t)0xFFFF);
            if (VirtualAlloc(page, 0x10000, MEM_COMMIT, PAGE_READWRITE))
                return EXCEPTION_CONTINUE_EXECUTION;
        }
    }
    return EXCEPTION_CONTINUE_SEARCH;
}
#endif

static bool alloc_guest_vm(void)
{
#ifdef _WIN32
    AddVectoredExceptionHandler(1, vm_commit_veh);
    vm_base = (uint8_t*)VirtualAlloc(NULL, VM_SIZE, MEM_RESERVE, PAGE_READWRITE);
    ppu_vm_size = 0;              /* the whole space is backed; no OOB guard needed */
#else
    /* No vectored exception handlers off Windows, so the arena is mapped up
     * front and lazily backed by the OS: only pages the title touches cost
     * anything. It spans the whole 32-bit space plus the guard, as on Windows.
     * It used to stop below 0xE0000000, but the raw SPU windows (local store
     * and problem-state registers, runtime/spu/spu_raw.c) live from there up.
     * Every load and store a title made into one was reported as an
     * out-of-bounds access and dropped, so a raw SPU was never loaded or
     * started, and sys_raw_spu_create, which clears the registers through
     * vm_base directly, wrote past the end of the mapping. With the whole
     * space backed, ppu_vm_size 0 also gives the loader's bounds check the
     * one-compare fast path Windows already has.
     *
     * mmap, not calloc: vm_commit() hands vm_base + addr to mprotect, which
     * takes page-aligned addresses only. glibc serves an allocation this big
     * from its own mmap chunk and returns a pointer 16 bytes past the page
     * start, so every commit failed with EINVAL and sys_memory_allocate
     * answered ENOMEM to every call. mmap's base is page-aligned and zeroed. */
    void* p = mmap(NULL, VM_SIZE, PROT_READ | PROT_WRITE,
                   MAP_PRIVATE | MAP_ANONYMOUS | MAP_NORESERVE, -1, 0);
    vm_base = (p == MAP_FAILED) ? nullptr : (uint8_t*)p;
    ppu_vm_size = 0;              /* the whole space is backed; no OOB guard needed */
#endif
    return vm_base != nullptr;
}

/* ---------------------------------------------------------------------------
 * Main
 * -----------------------------------------------------------------------*/
static void harness_guest_caller(uint32_t opd, uint64_t a0, uint64_t a1,
                                 uint64_t a2, uint64_t a3, uint64_t a4,
                                 uint64_t a5, uint64_t a6, uint64_t a7)
{
    ppu_guest_call(opd, a0, a1, a2, a3, a4, a5, a6, a7);
}

/* ---------------------------------------------------------------------------
 * Running the guest
 * -----------------------------------------------------------------------*/
#if defined(__APPLE__)
/* AppKit only runs on the process's main thread. The Metal backend creates
 * its window and pumps its events with dispatch_sync onto the main queue
 * when it is called from any other thread, as it is from the frame clock.
 * With the guest on the main thread nothing ever serviced that queue: the
 * frame clock blocked in its first rsx_backend_init, no vblank or flip was
 * ever delivered and the FIFO never drained. A title that waits for a flip
 * hangs there. So the guest runs on a thread of its own, with the same
 * 256 MB host stack every guest thread gets (sys_ppu_thread.c), and the
 * main thread turns the run loop until ppu_run returns. Headless runs never
 * touch the main queue, which is why CI does not see the difference. */
struct guest_run { uint32_t entry, stack_top; int rc; volatile int done; };

static void* guest_thread(void* arg)
{
    guest_run* g = (guest_run*)arg;
    g->rc = ppu_run(g->entry, g->stack_top);
    __atomic_store_n(&g->done, 1, __ATOMIC_RELEASE);
    CFRunLoopStop(CFRunLoopGetMain());
    return nullptr;
}

static int run_guest(uint32_t entry, uint32_t stack_top)
{
    static guest_run g;
    g.entry = entry; g.stack_top = stack_top; g.rc = 0; g.done = 0;
    pthread_attr_t attr;
    pthread_attr_init(&attr);
    pthread_attr_setstacksize(&attr, 256u * 1024u * 1024u);
    pthread_t th;
    int err = pthread_create(&th, &attr, guest_thread, &g);
    pthread_attr_destroy(&attr);
    if (err != 0) {
        fprintf(stderr, "[boot] could not start the guest thread (%d)\n", err);
        return -1;
    }
    /* Short slices: CFRunLoopStop only ends a run that is already going. */
    while (!__atomic_load_n(&g.done, __ATOMIC_ACQUIRE))
        CFRunLoopRunInMode(kCFRunLoopDefaultMode, 0.05, false);
    pthread_join(th, nullptr);
    return g.rc;
}
#else
static int run_guest(uint32_t entry, uint32_t stack_top) { return ppu_run(entry, stack_top); }
#endif

int main(int argc, char** argv)
{
    CliOptions opt;
    std::string err;
    if (!cli_parse(argc, argv, opt, err)) {
        fprintf(stderr, "error: %s\nRun with --help for the option list.\n", err.c_str());
        return 2;
    }
    if (opt.help)    { fputs(cli_help_text(), stdout); return 0; }
    if (opt.version) { puts(PORT_VERSION_STRING); return 0; }
#ifndef _WIN32
    if (opt.fullscreen || opt.hidden) {
        fputs("error: --fullscreen and --hidden require the Windows backend.\n", stderr);
        return 2;
    }
    if (cli_has_d3d12_options(opt)) {
        fputs("error: RSX renderer options require the D3D12 backend.\n", stderr);
        return 2;
    }
#endif

    std::string exe_dir = cli_exe_dir(argv[0]);
    if (!make_absolute(exe_dir)) return 1;
    ResolvedPaths rp;
    cli_resolve(opt, exe_dir, rp);
    for (auto* path : {&rp.build_dir, &rp.elf, &rp.vfs_root, &rp.hdd0, &rp.hdd1,
                       &rp.savedata, &rp.log_dir, &rp.log_file, &rp.audio_wav,
                       &rp.tex_dump, &rp.tex_replace})
        if (!make_absolute(*path)) return 1;
#ifdef _WIN32
    if (rp.rsx_shader_cache != "0" && !make_absolute(rp.rsx_shader_cache)) return 1;
#endif
    std::string firmware;
    if (!resolve_firmware(firmware, opt, rp.build_dir)) return 1;

    /* Log file first so it also captures setup errors. */
    if (!rp.log_file.empty() && !redirect_log(rp.log_file)) {
        fprintf(stderr, "error: cannot redirect output to %s\n", rp.log_file.c_str());
        return 1;
    }

    const std::string sfo = find_game_files(opt, rp);
    if (sfo.empty()) {
        fprintf(stderr,
                "Game files not found.\n"
                "Put PARAM.SFO and USRDIR/EBOOT.elf for this build's game profile in:\n"
                "  %s\n"
                "Use --game-dir or --elf to select another location.\n"
                "ELF path checked: %s\n",
                rp.vfs_root.c_str(), rp.elf.c_str());
        keep_explorer_message_open(argc);
        return 1;
    }

#ifdef _WIN32
    // Keep this read handle open through ppu_load_elf so the checked file
    // cannot be modified or replaced between the two reads.
    std::unique_ptr<FILE, decltype(&fclose)> pinned_elf(
        _fsopen(rp.elf.c_str(), "rb", _SH_DENYWR), fclose);
    if (!matches_target_elf(pinned_elf.get())) {
#ifdef HSG_TARGET_OFFICIAL_1_03
        const char* target_profile = "official 1.03";
#else
        const char* target_profile = "fixed 1.02";
#endif
        fprintf(stderr, "Unsupported or unreadable EBOOT.elf at %s. Use the decrypted %s ELF for this build.\n",
                rp.elf.c_str(), target_profile);
        keep_explorer_message_open(argc);
        return 1;
    }
    setvbuf(stdout, NULL, _IONBF, 0);
#endif
    if (cellGame_init_from_paramsfo(sfo.c_str()) != 0) {
        fprintf(stderr, "Game files are incomplete: could not read TITLE_ID from %s.\n", sfo.c_str());
        keep_explorer_message_open(argc);
        return 1;
    }
    if (strcmp(cellGame_get_title_id(), "NPUA80864") != 0) {
        fprintf(stderr, "Unsupported title ID in %s. Use the US NPUA80864 game files.\n", sfo.c_str());
        keep_explorer_message_open(argc);
        return 1;
    }
    g_window_title = rp.title.empty() ? cellGame_get_title() : rp.title;

    // Keep relative paths used internally by the runtime and graphics driver in the port folder.
    std::error_code cwd_error;
    std::filesystem::current_path(rp.build_dir, cwd_error);
    if (cwd_error) {
        fprintf(stderr, "error: cannot use the build folder %s (%s)\n",
                rp.build_dir.c_str(), cwd_error.message().c_str());
        return 1;
    }

    if (!rp.audio_wav.empty()) {
        const std::filesystem::path output(rp.audio_wav);
        std::error_code error;
        if (output.filename().empty() || std::filesystem::is_directory(output, error)) {
            fprintf(stderr, "error: audio WAV destination must name a file: %s\n", rp.audio_wav.c_str());
            return 1;
        }
        std::filesystem::create_directories(output.parent_path(), error);
        if (error) {
            fprintf(stderr, "error: cannot create the audio WAV directory for %s (%s)\n",
                    rp.audio_wav.c_str(), error.message().c_str());
            return 1;
        }
    }

#ifdef _WIN32
    if (rp.rsx_shader_cache.size() >= MAX_PATH) {
        fprintf(stderr, "error: D3D12 shader cache path must be shorter than %d bytes.\n", MAX_PATH);
        return 1;
    }
    if (!opt.rsx_shader_cache.empty() && rp.rsx_shader_cache != "0") {
        std::error_code error;
        std::filesystem::create_directories(rp.rsx_shader_cache, error);
        if (error) {
            fprintf(stderr, "error: cannot create D3D12 shader cache directory %s (%s)\n",
                    rp.rsx_shader_cache.c_str(), error.message().c_str());
            return 1;
        }
    }
    if (!configure_windows_profile(rp.build_dir)) return 1;
#endif

    /* The runtime reads its roots from the environment, so the resolved values
     * (flag, env, or default next to the exe) are exported before it starts. */
    make_dirs(rp.hdd0); make_dirs(rp.hdd1); make_dirs(rp.savedata); make_dirs(rp.log_dir);
    cli_setenv("PS3_VFS_ROOT", rp.vfs_root.c_str());
    cli_setenv("PS3_HDD0_ROOT", rp.hdd0.c_str());
    cli_setenv("PS3_HDD1_ROOT", rp.hdd1.c_str());
    cli_setenv("PS3_SAVEDATA_ROOT", rp.savedata.c_str());
    // cellSaveData uses the older variable for the same save tree.
    cli_setenv("PS3_GAMEDATA_ROOT", rp.savedata.c_str());
    cli_setenv("PS3_DEV_FLASH", firmware.c_str());
    cli_setenv("PS3_CAMERA", "0");
    cli_setenv("PS3_HTTP_OFFLINE", "1");
    /* HSG_MOVIES=0: skip the movies, as builds without a decoder did. The
     * runtime's cellSail then reports each one as played to its end at once. */
    if (const char* movies = getenv("HSG_MOVIES"); movies && movies[0] == '0')
        cli_setenv("PS3_SAIL_MOVIES", "0");
    cli_setenv("PS3_VERBOSE", std::to_string(rp.verbose).c_str());
    cli_apply_tuning(opt, rp);
    if (rp.verbose > 0)
        fprintf(stderr, "[boot] Verbose runtime logging enabled (PS3_VERBOSE=%d)\n", rp.verbose);
    if (opt.width)  g_window_w = (uint32_t)opt.width;
    if (opt.height) g_window_h = (uint32_t)opt.height;
    g_window_hidden = opt.hidden;

#ifdef _WIN32
    rsx_d3d12_backend_set_window_mode(opt.fullscreen, opt.hidden);
#pragma comment(lib, "winmm.lib")
    /* 1 ms timer resolution. The default granularity is about 15.6 ms, which
     * inflates every shorter wait the title makes and throttles the whole
     * thing. POSIX timers are already fine-grained. */
    timeBeginPeriod(1);
#endif

    printf("=== ps3recomp game runner ===\n");

    if (!alloc_guest_vm()) {
        fprintf(stderr, "ERROR: could not allocate the guest address space\n");
        return 1;
    }

    uint32_t entry = ppu_load_elf(rp.elf.c_str());
#ifdef _WIN32
    pinned_elf.reset();
#endif
    if (!entry) {
        fprintf(stderr, "ERROR: could not load %s\n", rp.elf.c_str());
        keep_explorer_message_open(argc);
        return 1;
    }

    ppu_vfs_root = rp.vfs_root.c_str();
    printf("[boot] VFS root: %s\n", ppu_vfs_root);
    printf("[boot] hdd0: %s\n[boot] hdd1: %s\n[boot] savedata: %s\n",
           rp.hdd0.c_str(), rp.hdd1.c_str(), rp.savedata.c_str());

    ppu_recomp_register();   /* lifted function table -> address map */
    ps3_load_prx_modules();  /* this game's lifted system PRX, if it has any */
    ppu_hle_init();          /* firmware import NID -> HLE handlers */
    ps3_register_peripheral_imports();
    ppu_sysprx_register();   /* boot-critical CRT */
    ppu_fs_register();       /* cellFs over the game directory */
    lv2_init_syscalls();     /* the lv2 syscall table */

    /* Install the guest-callback hook, then start the frame clock. It no-ops
     * until the title registers its vblank and flip handlers during init. */
    g_ps3_guest_caller = harness_guest_caller;
    CreateThread(NULL, 4u * 1024 * 1024, frame_clock, NULL, 0, NULL);
    if (opt.exit_after > 0)
        CreateThread(NULL, 64u * 1024, exit_timer, (LPVOID)(uintptr_t)opt.exit_after, 0, NULL);

    printf("\n[boot] dispatching entry OPD 0x%08X (stack top 0x%08X)\n\n",
           entry, STACK_TOP);

    /* A title that reads its own stack bounds (to find data its parent left
     * below the top, say) gets the stack it really runs on. */
    g_ppu_main_stack_addr = STACK_TOP - STACK_SIZE;
    g_ppu_main_stack_size = STACK_SIZE;

    int rc = run_guest(entry, STACK_TOP);
    printf("\n[boot] ppu_run returned %d (entry function unwound)\n", rc);

    /* A title that called sys_process_exit never reaches this line: that path
     * ends in the host exit(). Getting here means the entry function returned
     * instead, so hand back the status the guest published if it published
     * one. Returning a hardcoded 0 would report success for a run that never
     * got anywhere. */
    return g_sys_process_exit_called ? (int)g_sys_process_exit_code : 0;
}
