// JP 1.27 build only (HSG_TARGET_PROFILE=jp-1.27, pipeline-jp127.toml).
//
// Archive entry-name fallback. FB archives (.xb) find an entry by a hash of its
// internal path (FB_FindEntryByPath: lowercase, h = h*31 + c). The JP program
// asks for "data/chara/..." and "data/course/...", while the base data it runs
// on was packed under other names: the US archives hash "data/chara_localize/..."
// and "data/course_localize/...", the Asia ones "data/course_localize/...". The
// JP updates' own archives use the JP names. So when a lookup of a JP name
// misses, it is retried once with the base name; payloads are the same in all
// regions, only the key differs.
//
// tools/jp_lift_hooks.py renames the lifted FB_FindEntryByPath (JP 0x00788B64,
// US 0x00779228, same code) to func_00788B64_lifted, so every lifted call lands
// here first. Signature: r3 archive, r4 entry out (byte 0 = already found),
// r5 entry name; returns r3 = 1 found, 0 not found (after the title's own
// loose-file fallback).
#include "ppu_recomp.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>

extern "C" PPU_THREAD_LOCAL void (*g_trampoline_fn)(void*);
void func_00788B64_lifted(ppu_context* ctx);

namespace {

struct Alias { const char* jp; const char* base; };
const Alias k_alias[] = {
    {"data/chara/", "data/chara_localize/"},
    {"data/course/", "data/course_localize/"},
};

void drain(ppu_context* ctx)
{
    while (g_trampoline_fn) {
        void (*f)(void*) = g_trampoline_fn;
        g_trampoline_fn = 0;
        f(ctx);
    }
}

bool prefix_ci(const char* s, const char* p)
{
    for (; *p; s++, p++)
        if (tolower((unsigned char)*s) != *p) return false;
    return true;
}

int log_limit()
{
    static int n = -1;
    if (n < 0) { const char* e = getenv("HSG_JP_FB_LOG"); n = e ? atoi(e) : 8; }
    return n;
}

}  // namespace

void func_00788B64(ppu_context* ctx)
{
    const uint64_t r1 = ctx->gpr[1], r2 = ctx->gpr[2], r3 = ctx->gpr[3], r4 = ctx->gpr[4],
                   r5 = ctx->gpr[5], lr = ctx->lr;
    func_00788B64_lifted(ctx);
    drain(ctx);
    if ((ctx->gpr[3] & 0xFF) != 0 || !r5 || !vm_base) return;

    char name[256];
    size_t n = 0;
    for (; n < sizeof name - 1; n++) {
        name[n] = (char)vm_read8((uint32_t)(r5 + n));
        if (!name[n]) break;
    }
    if (n == sizeof name - 1) return;
    name[n] = 0;

    for (const Alias& a : k_alias) {
        if (!prefix_ci(name, a.jp)) continue;
        char alt[0x170];
        if ((size_t)snprintf(alt, sizeof alt, "%s%s", a.base, name + strlen(a.jp)) >= sizeof alt) return;
        // The alternative name lives in a frame of our own below the caller's
        // stack pointer; the callee's frame goes below that.
        const uint64_t sp = (r1 - 0x200) & ~0xFull;
        vm_write64((uint32_t)sp, r1);
        const uint32_t buf = (uint32_t)sp + 0x80;
        for (size_t i = 0; i <= strlen(alt); i++) vm_write8(buf + (uint32_t)i, (uint8_t)alt[i]);
        ctx->gpr[1] = sp; ctx->gpr[2] = r2; ctx->gpr[3] = r3; ctx->gpr[4] = r4; ctx->gpr[5] = buf;
        ctx->lr = lr;
        func_00788B64_lifted(ctx);
        drain(ctx);
        ctx->gpr[1] = r1;
        ctx->gpr[5] = r5;
        static int logged = 0, missed = 0;
        const bool hit = (ctx->gpr[3] & 0xFF) != 0;
        if (hit ? logged++ < log_limit() : missed++ < 64) {
            fprintf(stderr, "[jp-fb] %s -> %s: %s\n", name, alt, hit ? "found" : "missing");
        }
        return;
    }
}

// Ordinal suffix (JP 0x00772D94, r3 = rank, returns the suffix index; callers add it to a
// chip base, e.g. result_01 th_000..003, or 1 + it to a message group st/nd/rd/th). The JP
// program runs with region index 0, for which the game returns 0 (the one JP suffix) for
// every rank; with the English data in place chip 0 is "st", so ranks read "5st". When the
// data is English (<game dir>/LANG.txt says "en", written by tools/jp127_english.py) this
// returns the game's own English rule (its region 1 path): 0 st, 1 nd, 2 rd, 3 th, and th
// for 11-13 of each hundred. Japanese data keeps the lifted function.
void func_00772D94_lifted(ppu_context* ctx);

namespace {
bool english_data()
{
    static int on = -1;
    if (on < 0) {
        on = 0;
        const char* root = getenv("PS3_VFS_ROOT");
        char path[1024];
        if (root && *root && (size_t)snprintf(path, sizeof path, "%s/LANG.txt", root) < sizeof path) {
            if (FILE* f = fopen(path, "rb")) {
                char buf[8] = {0};
                fread(buf, 1, sizeof buf - 1, f);
                fclose(f);
                on = (tolower((unsigned char)buf[0]) == 'e' && tolower((unsigned char)buf[1]) == 'n');
            }
        }
        fprintf(stderr, "[jp-ordinal] %s suffixes\n", on ? "English" : "game's own (Japanese)");
    }
    return on != 0;
}
}  // namespace

void func_00772D94(ppu_context* ctx)
{
    if (!english_data()) { func_00772D94_lifted(ctx); return; }
    int32_t n = (int32_t)ctx->gpr[3];
    if (n < 0) n = -n;
    int idx = 3;
    if (n % 100 < 11 || n % 100 > 13) {
        switch (n % 10) {
        case 1: idx = 0; break;
        case 2: idx = 1; break;
        case 3: idx = 2; break;
        default: break;
        }
    }
    ctx->gpr[3] = (uint64_t)(int64_t)idx;
}
