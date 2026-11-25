// JP 1.27 build only: shared by hsg_jp127_unlocks.cpp (store, grind economy) and
// hsg_jp127_capsule.cpp (the game's capsule machine hosted offline).
#pragma once
#include "ppu_recomp.h"
#include <stdint.h>

extern "C" PPU_THREAD_LOCAL void (*g_trampoline_fn)(void*);

namespace hsg {

inline void drain(ppu_context* ctx)
{
    while (g_trampoline_fn) {
        void (*f)(void*) = g_trampoline_fn;
        g_trampoline_fn = 0;
        f(ctx);
    }
}

// Calls fn on a scratch frame below the caller's stack; ctx is restored after.
struct GuestCall {
    ppu_context* ctx;
    ppu_context keep;
    uint64_t sp;
    explicit GuestCall(ppu_context* c) : ctx(c), keep(*c)
    {
        sp = (keep.gpr[1] - 0x200) & ~0xFull;
        vm_write64((uint32_t)sp, keep.gpr[1]);
    }
    ~GuestCall() { *ctx = keep; }
    uint64_t call(void (*fn)(ppu_context*), uint64_t toc, uint64_t r3, uint64_t r4 = 0,
                  uint64_t r5 = 0, uint64_t r6 = 0)
    {
        ctx->gpr[1] = sp; ctx->gpr[2] = toc;
        ctx->gpr[3] = r3; ctx->gpr[4] = r4; ctx->gpr[5] = r5; ctx->gpr[6] = r6;
        fn(ctx);
        drain(ctx);
        return ctx->gpr[3];
    }
};

constexpr uint64_t kTocCore = 0xD8E348;     // r2 of the menu / lobby shop / save helpers
constexpr uint64_t kTocGasha = 0xD9E100;    // r2 of the gashapon manager code
constexpr uint32_t kMgrPtr = 0x01842080;    // *(u32) = gashapon manager
constexpr int kRareChars = 15;              // Pc_000-014
constexpr int kMaxStars = 7;
constexpr int kGaugeMax = 63;

// ---- unlocks.cpp -> capsule.cpp ---------------------------------------------------------
bool grind_mode();                 // HSG_UNLOCKS=grind
int store_tickets();
void store_set_tickets(int n);     // and saves the store
int store_rare(int pc);            // 0-7
int store_gauge(int pc);           // 0-63
int store_pity();                  // draws since the last red capsule
int pity_draws();                  // after this many draws without red the next is red
double star_odds(int star);        // chance of a star (1-7) per capsule, without pity (0-1)
bool store_tus(int slot, int64_t* v);          // other TUS slots kept in the store
void store_set_tus(int slot, int64_t v);       // (no save)
void store_set_level(int pc, int level, int gauge);   // (no save)
// One capsule drawn in the machine, as the game applied it: pc, capsule star 1-7, level and
// gauge before/after. Updates rare/gauge/pity/draws and logs "[hsg-unlocks] draw:" (no save).
void store_record_draw(int pc, int star, int lv0, int lv1, int g0, int g1, bool forced);
void store_save();
bool store_all_maxed();
// Our odds and pity for one capsule over levels[15] (no state change): pc, star 1-7.
// False when every rare is at 7 stars.
bool store_roll(const int* levels, int pity, int* pc, int* star, bool* forced);
void toast_line(const char* utf8);  // collect, then toast_post
void toast_post(int ms);

// ---- capsule.cpp -> unlocks.cpp ---------------------------------------------------------
void capsule_tick(ppu_context* ctx);   // every gashapon manager tick (grind only)
bool capsule_busy();                   // machine open: the game owns the save's rare levels

}  // namespace hsg
