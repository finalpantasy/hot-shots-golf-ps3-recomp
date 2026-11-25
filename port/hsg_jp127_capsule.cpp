// JP 1.27 build only. The game's own online capsule machine, hosted offline in the Shop
// (HSG_UNLOCKS=grind). Called from the gashapon manager tick (hsg_jp127_unlocks.cpp).
//
// Entry: in the offline Shop's top category list (sequence 63, ShopManager active and its
// +0x154 == 0) a hint toast offers Triangle. Triangle builds the lobby capsule shop the online
// lobby uses (singleton *(0x0183EC90): new 0x504 -> ctor 0x00224E64 -> load 0x002217BC ->
// post-load 0x002207F8), connects the gashapon manager's TUS (0x0044507C) and opens it
// (0x00223408). While it is open we run its update (0x00222348) and draw (0x00222FA0) each
// tick and stop the walker from visiting the ShopManager task (phase bytes node+0xD+p*8 = 0
// for update/late/draw) and the Menu task's draw phase, so the machine owns the screen and
// the input: the game draws its own header, 3D machine, capsule drop/open animation, sounds
// and result screen. Circle clears shop flag 0x4; 30 ticks later (the Circle press is gone
// and the game's own auto-save has run) we destroy the shop the way the lobby does (dtor
// 0x00223D50, free 0x0079037C, global 0) and give the ShopManager/Menu back.
//
// Server: patch 0077 answers TUS from an in-memory table (libs/network/sceNpTus.c). Before the
// first open we seed slots 1-63 from the store: rare bits (slots 1-2, bit pc*7 + level-1),
// gauges (slots 5-6, 6 bits at (pc%10)*6), slot 9 (draw lock) idle 0x800006, the rest from the
// store's "tus" lines. Every write the game makes is copied back to the store (not 1,2,5,6,9:
// those come from the save and the TUS object after each draw).
//
// Tickets: the store count is shown in the ticket object (*(0x0184AB8C) +0x34 count, +0x40
// state 3 = ready). The machine draws first, then consumes (0x0042B334: state 1, count -= n,
// sceNpManagerRequestTicket2 answered locally by patch 0077); we save the lower count to the
// store at once and set the state back to ready.
//
// Odds: online the manager parsed the server's gacha_odds.csv (parser 0x0044882C: rows
// "ID,odds"; an ID containing "Pc" adds a float to the per-character vector mgr+0x00 in row
// order = Pc_000.., one containing "Rare" adds to the per-star vector mgr+0x10 = stars 1..7;
// then mgr+0x60 = 1). Offline nothing is parsed, so before the first open we push the same
// vectors (feed_odds: 15 x 1.0, stars from star_odds()) with the game's own
// vector<float>::push_back. The game then builds its odds table itself (0x0044A1A0: per
// character weight / sum over characters below 7 stars (0x004496F0) x per star weight / sum
// (0x00446038)) and the machine shows it on the odds table page.
//
// Outcome and pity: the game's roll 0x0044A6C0 (hooked) uses those same weights but draws
// r = rand % 100 and takes the first entry with r <= 100 x cumulative weight, so it rounds
// every chance to whole percents and gives the first entry one extra (star 1 25%, star 7 7%
// instead of 24/8 with our table; characters 6 or 7% instead of 6.67). So that the shown
// table and the real draws agree, our roll decides (store_roll: uniform over the characters
// below 7 stars, stars by star_odds(), pity), which is exactly the table's model, and fills the
// record (+0/+8 pc, +4 star-1). HSG_CAPSULE_GAMEROLL=1 keeps the game's own result (pity still
// forces red); HSG_CAPSULE_ODDS_SELFTEST=<n> rolls the game's roll n times at the first open
// and logs its counts next to the table ("[hsg-capsule] selftest:"). After the game's draw (0x0044ABF4, hooked) succeeds we put each capsule
// into the store by the game's rule (0x0044B0A8), log it ("[hsg-unlocks] draw:") and save.
// The game itself writes the save's rare level later (result screen), so the store-to-save
// sync (apply) pauses while the machine is open; on close we compare the store with the save
// and the TUS table ("[hsg-capsule] check:").
//
// HSG_CAPSULE_DEBUG=1 logs task/state details and every TUS rare/write-all call.
#include "hsg_jp127_unlocks.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

extern "C" {
int hsg_tus_local_on(void);
void hsg_tus_local_enable(void);
unsigned hsg_tus_local_writes(void);
void hsg_tus_local_poke(int slot, long long value);
int hsg_tus_local_peek(int slot, long long* value);
}

void func_0044A6C0_lifted(ppu_context* ctx);   // roll one capsule (mgr, rec)
void func_00A78A28(ppu_context* ctx);   // std::vector<float>::push_back (vec, &value), core TOC
void func_0044A1A0(ppu_context* ctx);   // odds table (mgr, vector of {f32 chance, star-1, pc})
void func_0044ABF4_lifted(ppu_context* ctx);   // draw n capsules (mgr, recs, n, ...)
void func_0044BD0C_lifted(ppu_context* ctx);   // TUS rare bit set (tus, pc, star-1)
void func_0044C4E4_lifted(ppu_context* ctx);   // TUS write slots 1-63
void func_000333E4(ppu_context* ctx);   // chara record of (save + 0x11B40, pc)
void func_00790578(ppu_context* ctx);   // operator new(size, file, line)
void func_0079037C(ppu_context* ctx);   // operator delete
void func_00224E64(ppu_context* ctx);   // lobby capsule shop ctor
void func_00223D50(ppu_context* ctx);   // lobby capsule shop dtor
void func_002217BC(ppu_context* ctx);   // load
void func_002207F8(ppu_context* ctx);   // post-load
void func_00223408(ppu_context* ctx);   // open
void func_00222348(ppu_context* ctx);   // update
void func_00222FA0(ppu_context* ctx);   // draw
void func_0044507C(ppu_context* ctx);   // gashapon manager: connect TUS (0x0044BBF0)
void func_0044B748(ppu_context* ctx);   // TUS object: read slots 1-63 (0x0044C610)

namespace {
using namespace hsg;

constexpr uint32_t kSeqPtr = 0x00DC8F68;      // *(u32) = global sequence; +0xC current id
constexpr int kSeqShop = 63;
constexpr uint32_t kTaskRootPtr = 0x018710CC; // *(u32) = root task
constexpr uint32_t kInputPtr = 0x018B1990;    // *(u32) = input; +4.. controllers, +0x20 index
constexpr uint32_t kShopPtr = 0x0183EC90;     // *(u32) = lobby capsule shop
constexpr uint32_t kTicketObjPtr = 0x0184AB8C;
constexpr uint32_t kSavePtr = 0x017C90F4;
constexpr uint32_t kSaveSub = 0x11B40;
constexpr uint32_t kPadTriangle = 0x1000;
constexpr int kCloseTicks = 30;

bool env_on(const char* name)
{
    const char* e = getenv(name);
    return e && *e && *e != '0';
}

bool dbg()
{
    static const bool on = [] {
        const char* e = getenv("HSG_CAPSULE_DEBUG");
        return e && *e && *e != '0';
    }();
    return on;
}

// ---- task tree ----------------------------------------------------------------------------
// Node: +0 vtable (+0x50 name getter "lwz r3, d(r2); blr"), +0x44 child list head, +0x48
// count; list entry +0 next, +8 child. Phase bytes: +0xC/+0xD + phase*8 (0 update, 1 late,
// 2 draw); the walker skips a node and its children while +0xD + phase*8 is 0.
const char* task_name(uint32_t node)
{
    static char buf[64];
    const uint32_t vt = vm_read32(node);
    if (vt < 0x00D00000 || vt > 0x00E00000) return "?";
    const uint32_t opd = vm_read32(vt + 0x50);
    if (opd < 0x00D00000 || opd > 0x00E00000) return "?";
    const uint32_t fn = vm_read32(opd), toc = vm_read32(opd + 4);
    if (fn < 0x10000 || fn > 0x00D27698) return "?";
    const uint32_t w = vm_read32(fn), w2 = vm_read32(fn + 4);
    if ((w >> 16) != 0x8062 || w2 != 0x4E800020) return "-";
    const uint32_t s = vm_read32(toc + (uint32_t)(int32_t)(int16_t)(w & 0xFFFF));
    int i = 0;
    for (; i < 63; i++) {
        const uint8_t c = vm_read8(s + i);
        if (!c || c < 0x20 || c > 0x7E) break;
        buf[i] = (char)c;
    }
    buf[i] = 0;
    return buf;
}

uint32_t find_task(uint32_t node, const char* name, int depth = 0)
{
    if (!node || depth > 6) return 0;
    if (!strcmp(task_name(node), name)) return node;
    const uint32_t head = vm_read32(node + 0x44);
    if (!head || !vm_read32(node + 0x48)) return 0;
    uint32_t cur = vm_read32(head);
    for (int n = 0; cur && cur != head && n < 64; n++) {
        if (uint32_t r = find_task(vm_read32(cur + 8), name, depth + 1)) return r;
        cur = vm_read32(cur);
    }
    return 0;
}

int seq_id()
{
    const uint32_t s = vm_read32(kSeqPtr);
    return s ? (int)vm_read32(s + 0xC) : -1;
}

bool triangle_pressed()
{
    const uint32_t in = vm_read32(kInputPtr);
    if (!in) return false;
    const uint32_t idx = vm_read32(in + 0x20);
    if (idx > 6) return false;
    const uint32_t c = vm_read32(in + 4 + idx * 4);
    return c && (vm_read32(c + 0x290 + 0x64) & kPadTriangle);   // layer 0 trigger
}

// ---- save / TUS object --------------------------------------------------------------------
int save_level(ppu_context* ctx, int pc)
{
    const uint32_t save = vm_read32(kSavePtr);
    if (!save) return -1;
    GuestCall g(ctx);
    const uint32_t rec = (uint32_t)g.call(func_000333E4, kTocCore, save + kSaveSub, (uint64_t)pc);
    return rec ? (vm_read8(rec) & 0x3F) : -1;
}

uint32_t tus_obj()
{
    const uint32_t mgr = vm_read32(kMgrPtr);
    return mgr ? vm_read32(mgr + 0x64) : 0;
}

// Gauge of pc in the local TUS table (slot 5: pc 0-9, slot 6: pc 10-14, 6 bits each).
int table_gauge(int pc)
{
    long long v = 0;
    if (!hsg_tus_local_peek(5 + pc / 10, &v)) return -1;
    return (int)(((unsigned long long)v >> ((pc % 10) * 6)) & 0x3F);
}

// After the machine closes: the store's levels/gauges against the save and the TUS table the
// game wrote (log only; a mismatch means our copy of the rule and the game's differ).
void check_against_game(ppu_context* ctx)
{
    int bad = 0;
    for (int pc = 0; pc < kRareChars; pc++) {
        const int lv = save_level(ctx, pc), gauge = table_gauge(pc);
        if ((lv >= 0 && lv != store_rare(pc)) || (gauge >= 0 && gauge != store_gauge(pc))) {
            bad++;
            fprintf(stderr, "[hsg-capsule] check: Pc_%03d game level %d gauge %d, store %d/%d\n", pc, lv,
                    gauge, store_rare(pc), store_gauge(pc));
        }
    }
    fprintf(stderr, "[hsg-capsule] check: %s\n", bad ? "store differs from the game (see above)"
                                                     : "store matches the game's levels and gauges");
}

int star_need(int n)   // the game's table 0x00444924 for 0-6
{
    static const int t[] = {1, 2, 4, 8, 12, 16, 20};
    return n >= 0 && n <= 6 ? t[n] : 0;
}

// Slots 1-63 from the store (see the header).
void seed_tus()
{
    long long rare[2] = {0, 0}, gauge[2] = {0, 0};
    for (int pc = 0; pc < kRareChars; pc++) {
        const int lv = store_rare(pc);
        if (lv > 0) {
            const int bit = pc * 7 + lv - 1;
            rare[bit / 64] |= 1LL << (bit % 64);
        }
        gauge[pc / 10] |= (long long)(store_gauge(pc) & 0x3F) << ((pc % 10) * 6);
    }
    for (int s = 1; s <= 63; s++) {
        int64_t v = 0;
        store_tus(s, &v);
        hsg_tus_local_poke(s, v);
    }
    hsg_tus_local_poke(1, rare[0]);
    hsg_tus_local_poke(2, rare[1]);
    hsg_tus_local_poke(5, gauge[0]);
    hsg_tus_local_poke(6, gauge[1]);
    hsg_tus_local_poke(9, 0x800006);
}

// ---- odds (see the header) ------------------------------------------------------------------
constexpr uint32_t kMgrPcOdds = 0x00, kMgrStarOdds = 0x10, kMgrOddsLoaded = 0x60;

uint32_t vec_size(uint32_t v, uint32_t elem)
{
    return vm_read32(v + 4) ? (vm_read32(v + 8) - vm_read32(v + 4)) / elem : 0;
}

void push_float(GuestCall& g, uint32_t vec, float f)
{
    const uint32_t tmp = (uint32_t)g.sp + 0x180;   // inside the 0x200 gap above the callee frame
    uint32_t bits;
    memcpy(&bits, &f, 4);
    vm_write32(tmp, bits);
    g.call(func_00A78A28, kTocCore, vec, tmp);
}

void feed_odds(ppu_context* ctx)
{
    const uint32_t mgr = vm_read32(kMgrPtr);
    if (!mgr || vm_read8(mgr + kMgrOddsLoaded)) return;
    GuestCall g(ctx);
    if (!vec_size(mgr + kMgrPcOdds, 4))
        for (int pc = 0; pc < kRareChars; pc++) push_float(g, mgr + kMgrPcOdds, 1.0f);
    if (!vec_size(mgr + kMgrStarOdds, 4))
        for (int star = 1; star <= kMaxStars; star++)
            push_float(g, mgr + kMgrStarOdds, (float)(star_odds(star) * 100.0));
    vm_write8(mgr + kMgrOddsLoaded, 1);
    fprintf(stderr, "[hsg-capsule] odds fed: %u characters, %u stars (%.4g/%.4g/%.4g %% per blue/purple/red star)\n",
            vec_size(mgr + kMgrPcOdds, 4), vec_size(mgr + kMgrStarOdds, 4), star_odds(1) * 100,
            star_odds(4) * 100, star_odds(7) * 100);
}

// The game's own odds table (0x0044A1A0 (mgr, vector of 12-byte rows {f32 chance 0-1, star-1,
// pc}), what the odds table page lists) against our roll's model: 1/(characters below 7 stars)
// x star_odds(star). Logged at each open. The row buffer comes from the manager's allocator and
// is left (a few hundred bytes per open).
void check_table(ppu_context* ctx)
{
    const uint32_t mgr = vm_read32(kMgrPtr);
    if (!mgr || !vm_read8(mgr + kMgrOddsLoaded)) return;
    GuestCall g(ctx);
    const uint32_t v = (uint32_t)g.sp + 0x1A0;
    vm_write32(v, vm_read32(mgr + kMgrPcOdds));   // allocator word of a vector the game made
    vm_write32(v + 4, 0); vm_write32(v + 8, 0); vm_write32(v + 12, 0);
    g.call(func_0044A1A0, kTocGasha, mgr, v);
    const uint32_t n = vec_size(v, 12), b = vm_read32(v + 4);
    int below = 0;
    for (int pc = 0; pc < kRareChars; pc++) below += store_rare(pc) < kMaxStars;
    double sum = 0, star_sum[8] = {0}, worst = 0;
    for (uint32_t i = 0; i < n && i < 1000; i++) {
        const uint32_t r = b + i * 12;
        const uint32_t bits = vm_read32(r);
        float f;
        memcpy(&f, &bits, 4);
        const int star = (int)vm_read32(r + 4) + 1, pc = (int)vm_read32(r + 8);
        sum += f;
        if (star >= 1 && star <= 7) star_sum[star] += f;
        const double model = (pc >= 0 && pc < kRareChars && store_rare(pc) < kMaxStars && below)
                                 ? star_odds(star) / below : 0.0;
        const double d = f > model ? f - model : model - f;
        if (d > worst) worst = d;
    }
    fprintf(stderr, "[hsg-capsule] odds table: %u rows (%d characters below 7 stars), sum %.5f, stars 1-7 %.3f %.3f "
            "%.3f %.3f %.3f %.3f %.3f %%, largest row difference from our roll %.2e\n", n, below, sum,
            star_sum[1] * 100, star_sum[2] * 100, star_sum[3] * 100, star_sum[4] * 100, star_sum[5] * 100,
            star_sum[6] * 100, star_sum[7] * 100, worst);
}

// HSG_CAPSULE_ODDS_SELFTEST=<n>: the game's own roll n times (no draw, nothing saved).
void selftest_game_roll(ppu_context* ctx)
{
    const char* e = getenv("HSG_CAPSULE_ODDS_SELFTEST");
    const int n = e ? atoi(e) : 0;
    const uint32_t mgr = vm_read32(kMgrPtr);
    if (n <= 0 || !mgr) return;
    GuestCall g(ctx);
    const uint32_t rec = (uint32_t)g.sp + 0x1C0;
    static int pcs[kRareChars], stars[8];
    int fails = 0;
    for (int i = 0; i < n; i++) {
        vm_write32(rec, 0xFFFFFFFF); vm_write32(rec + 4, 0xFFFFFFFF); vm_write32(rec + 8, 0xFFFFFFFF);
        if (!(uint8_t)g.call(func_0044A6C0_lifted, kTocGasha, mgr, rec)) { fails++; continue; }
        const int pc = (int)vm_read32(rec), star = (int)vm_read32(rec + 4) + 1;
        if (pc >= 0 && pc < kRareChars) pcs[pc]++;
        if (star >= 1 && star <= 7) stars[star]++;
    }
    fprintf(stderr, "[hsg-capsule] selftest: game roll x%d (fails %d): stars 1-7 %.2f %.2f %.2f %.2f %.2f %.2f %.2f %% "
            "(table %.2f %.2f %.2f %.2f %.2f %.2f %.2f)\n", n, fails,
            stars[1] * 100.0 / n, stars[2] * 100.0 / n, stars[3] * 100.0 / n, stars[4] * 100.0 / n,
            stars[5] * 100.0 / n, stars[6] * 100.0 / n, stars[7] * 100.0 / n, star_odds(1) * 100,
            star_odds(2) * 100, star_odds(3) * 100, star_odds(4) * 100, star_odds(5) * 100,
            star_odds(6) * 100, star_odds(7) * 100);
    char line[400];
    int o = snprintf(line, sizeof line, "[hsg-capsule] selftest: characters %%:");
    for (int pc = 0; pc < kRareChars && o < (int)sizeof line - 8; pc++)
        o += snprintf(line + o, sizeof line - o, " %.2f", pcs[pc] * 100.0 / n);
    fprintf(stderr, "%s\n", line);
}

void copy_tus_writes()
{
    static unsigned seen = 0;
    const unsigned w = hsg_tus_local_writes();
    if (w == seen) return;
    seen = w;
    bool any = false;
    for (int s = 1; s <= 63; s++) {
        if (s == 1 || s == 2 || s == 5 || s == 6 || s == 9) continue;
        long long v;
        int64_t old = 0;
        if (!hsg_tus_local_peek(s, &v)) continue;
        const bool had = store_tus(s, &old);
        if (had ? old == v : v == 0) continue;
        store_set_tus(s, v);
        any = true;
    }
    if (any) store_save();
}

// ---- one draw (0x0044ABF4) -----------------------------------------------------------------
struct Pending { int pc, star, lv0, lv1, g0, g1; bool forced; };
struct DrawState {
    bool active = false;
    int levels[kRareChars], gauges[kRareChars], pity = 0, n = 0;
    Pending p[16];   // a draw is 1 or up to 10 capsules (10-spin)
} g_draw;

void draw_begin()
{
    g_draw.active = true;
    g_draw.n = 0;
    g_draw.pity = store_pity();
    for (int pc = 0; pc < kRareChars; pc++) {
        g_draw.levels[pc] = store_rare(pc);
        g_draw.gauges[pc] = store_gauge(pc);
    }
}

// ---- the machine ---------------------------------------------------------------------------
enum class St { Idle, Open, Closing };
struct Machine {
    St st = St::Idle;
    int close_ticks = 0;
    uint32_t shop_node = 0, menu_node = 0;
    uint8_t shop_keep[3] = {0, 0, 0}, menu_keep = 0;
    uint32_t tob = 0, tob_count = 0, tob_state = 0;
    bool seeded = false;
    int hint_ticks = 0;
    bool hinted = false;
    int opens = 0;
} g_m;

// HSG_CAPSULE_DEBUG: the task tree (name, update/late/draw phase bytes) when the machine opens.
void dump_tree(uint32_t node, int depth)
{
    if (!node || depth > 5) return;
    fprintf(stderr, "[hsg-capsule] task %*s%s %08X phases %d/%d/%d\n", depth * 2, "", task_name(node), node,
            vm_read8(node + 0xD), vm_read8(node + 0xD + 8), vm_read8(node + 0xD + 16));
    const uint32_t head = vm_read32(node + 0x44);
    if (!head || !vm_read32(node + 0x48)) return;
    uint32_t cur = vm_read32(head);
    for (int n = 0; cur && cur != head && n < 64; n++) {
        dump_tree(vm_read32(cur + 8), depth + 1);
        cur = vm_read32(cur);
    }
}

// Tasks whose draw phase is switched off while the machine is open, besides the ShopManager's
// update/late phases and the Menu's draw (HSG_CAPSULE_HIDE=name,name adds more, for tests).
struct Hidden { uint32_t node; uint8_t keep; };
Hidden g_hidden[8];
int g_nhidden = 0;

void freeze(bool on)
{
    // HSG_CAPSULE_BG: 0 (default) = the ShopManager's and the Menu's draw off (machine on black);
    // 1 = both keep drawing (the ShopManager's update stops): the shop room shows behind, but the
    // ShopManager (no child tasks) draws the room, its list and its button prompts together, so the
    // list and doubled prompts show through. Keeping only the Menu's draw gives black (tested).
    static const int bg = [] {
        const char* e = getenv("HSG_CAPSULE_BG");
        return e && *e ? atoi(e) : 0;
    }();
    const bool keep_shop_draw = bg >= 1, keep_menu_draw = bg >= 1;
    if (on) {
        const uint32_t root = vm_read32(kTaskRootPtr);
        if (dbg()) dump_tree(root, 0);
        g_m.shop_node = find_task(root, "ShopManager");
        g_m.menu_node = find_task(root, "Menu");
        if (g_m.shop_node)
            for (int p = 0; p < 3; p++) {
                g_m.shop_keep[p] = vm_read8(g_m.shop_node + 0xD + p * 8);
                if (p < 2 || !keep_shop_draw) vm_write8(g_m.shop_node + 0xD + p * 8, 0);
            }
        if (g_m.menu_node) {
            g_m.menu_keep = vm_read8(g_m.menu_node + 0xD + 16);
            if (!keep_menu_draw) vm_write8(g_m.menu_node + 0xD + 16, 0);
        }
        g_nhidden = 0;
        if (const char* e = getenv("HSG_CAPSULE_HIDE")) {
            char names[256];
            snprintf(names, sizeof names, "%s", e);
            for (char* t = strtok(names, ","); t && g_nhidden < 8; t = strtok(nullptr, ",")) {
                const uint32_t n = find_task(root, t);
                if (!n) continue;
                g_hidden[g_nhidden++] = {n, vm_read8(n + 0xD + 16)};
                vm_write8(n + 0xD + 16, 0);
            }
        }
    } else {
        if (g_m.shop_node)
            for (int p = 0; p < 3; p++) vm_write8(g_m.shop_node + 0xD + p * 8, g_m.shop_keep[p]);
        if (g_m.menu_node) vm_write8(g_m.menu_node + 0xD + 16, g_m.menu_keep);
        for (int i = 0; i < g_nhidden; i++) vm_write8(g_hidden[i].node + 0xD + 16, g_hidden[i].keep);
        g_nhidden = 0;
        g_m.shop_node = g_m.menu_node = 0;
    }
}

void sync_tickets()
{
    const uint32_t tob = vm_read32(kTicketObjPtr);
    if (!tob) return;
    const int have = (int)vm_read32(tob + 0x34);
    if (vm_read32(tob + 0x40) == 1 && have < store_tickets()) {
        store_set_tickets(have);   // saves
        fprintf(stderr, "[hsg-capsule] ticket spent, %d left\n", have);
    }
    vm_write32(tob + 0x34, (uint32_t)store_tickets());
    vm_write32(tob + 0x40, 3);
}

bool open_machine(ppu_context* ctx)
{
    const uint32_t mgr = vm_read32(kMgrPtr);
    const uint32_t tob = vm_read32(kTicketObjPtr);
    if (!mgr || !tob) {
        fprintf(stderr, "[hsg-capsule] cannot open: manager %08X ticket object %08X\n", mgr, tob);
        return false;
    }
    if (!g_m.seeded) {
        seed_tus();
        hsg_tus_local_enable();
        g_m.seeded = true;
    }
    feed_odds(ctx);
    GuestCall g(ctx);
    uint32_t shop = vm_read32(kShopPtr);
    if (!shop) {
        shop = (uint32_t)g.call(func_00790578, kTocGasha, 0x504, 0xC800F0, 0x4E0);
        if (!shop) {
            fprintf(stderr, "[hsg-capsule] cannot open: out of memory\n");
            return false;
        }
        g.call(func_00224E64, kTocCore, shop);
        vm_write32(kShopPtr, shop);
        g.call(func_002217BC, kTocCore, shop);
        g.call(func_002207F8, kTocCore, shop);
    }
    g_m.tob = tob;
    g_m.tob_count = vm_read32(tob + 0x34);
    g_m.tob_state = vm_read32(tob + 0x40);
    sync_tickets();
    g.call(func_0044507C, kTocGasha, mgr);
    // Start the TUS read now (0x0044B748 -> GetMulti of slots 1-63); otherwise the first
    // draw finds no data (state tus+0x10 != 0x3F), fails with -6 and only then reads.
    if (const uint32_t tus = tus_obj()) g.call(func_0044B748, kTocGasha, tus);
    g.call(func_00223408, kTocCore, shop);
    if (g_m.opens == 0) selftest_game_roll(ctx);
    check_table(ctx);
    freeze(true);
    g_m.opens++;
    fprintf(stderr, "[hsg-capsule] open #%d: shop %08X flags %08X tickets %d tus %08X\n", g_m.opens,
            shop, vm_read32(shop), store_tickets(), tus_obj());
    return true;
}

void destroy_shop(ppu_context* ctx)
{
    const uint32_t shop = vm_read32(kShopPtr);
    if (shop) {
        GuestCall g(ctx);
        g.call(func_00223D50, kTocCore, shop);
        g.call(func_0079037C, kTocGasha, shop);
        vm_write32(kShopPtr, 0);
    }
    if (g_m.tob && g_m.tob == vm_read32(kTicketObjPtr)) {
        vm_write32(g_m.tob + 0x34, g_m.tob_count);
        vm_write32(g_m.tob + 0x40, g_m.tob_state);
    }
    g_m.tob = 0;
}

}  // namespace

namespace hsg {

bool capsule_busy() { return g_m.st != St::Idle; }

void capsule_tick(ppu_context* ctx)
{
    if (!vm_base) return;
    if (g_m.seeded) copy_tus_writes();
    if (g_m.st == St::Idle) {
        const bool in_shop = seq_id() == kSeqShop;
        uint32_t node = 0;
        if (in_shop) {
            static uint32_t cached = 0;
            if (!cached || strcmp(task_name(cached), "ShopManager"))
                cached = find_task(vm_read32(kTaskRootPtr), "ShopManager");
            node = cached;
        }
        const bool at_top = node && vm_read8(node + 0xD) == 1 && vm_read32(node + 0x154) == 0;
        if (!at_top || store_all_maxed()) {
            g_m.hint_ticks = 0;
            if (!in_shop) g_m.hinted = false;
            return;
        }
        if (++g_m.hint_ticks < 20) return;
        if (!g_m.hinted) {
            char line[128];
            const int t = store_tickets();
            // Top centre under the bar: the Shop's Back / Confirm prompts sit in the bar at the top right.
            snprintf(line, sizeof line, "\x1b@3" "\x1bg" "\xE2\x96\xB3  Capsule Machine (%d ticket%s)",
                     t, t == 1 ? "" : "s");
            toast_line(line);
            toast_post(5000);
            g_m.hinted = true;
        }
        if (triangle_pressed() && open_machine(ctx)) g_m.st = St::Open;
        return;
    }
    const uint32_t shop = vm_read32(kShopPtr);
    if (!shop) {   // gone under us: give the menu back
        freeze(false);
        g_m.st = St::Idle;
        return;
    }
    sync_tickets();
    {
        GuestCall g(ctx);
        g.call(func_00222348, kTocCore, shop);
        g.call(func_00222FA0, kTocCore, shop);
    }
    sync_tickets();
    if (g_m.st == St::Open && !(vm_read32(shop) & 4)) {
        g_m.st = St::Closing;
        g_m.close_ticks = 0;
        fprintf(stderr, "[hsg-capsule] closed by the player, flags %08X\n", vm_read32(shop));
    }
    if (g_m.st == St::Closing && ++g_m.close_ticks >= kCloseTicks) {
        check_against_game(ctx);
        destroy_shop(ctx);
        freeze(false);
        store_save();
        g_m.st = St::Idle;
        g_m.hint_ticks = 0;
        g_m.hinted = false;   // show the hint again on the shop list
        fprintf(stderr, "[hsg-capsule] shop destroyed, back to the Shop (%d tickets)\n", store_tickets());
    }
}

}  // namespace hsg

// Roll one capsule: our odds and pity when the game has no odds table, pity forced otherwise.
void func_0044A6C0(ppu_context* ctx)
{
    const uint32_t rec = (uint32_t)ctx->gpr[4];
    func_0044A6C0_lifted(ctx);
    drain(ctx);
    if (!grind_mode() || !hsg_tus_local_on() || !rec) return;
    if (!g_draw.active) draw_begin();
    const bool game_ok = (uint8_t)ctx->gpr[3] != 0;
    int pc, star;
    bool forced = false;
    static const bool game_roll = env_on("HSG_CAPSULE_GAMEROLL");
    if (game_ok && game_roll) {
        pc = (int)vm_read32(rec);
        star = (int)vm_read32(rec + 4) + 1;
        if (pity_draws() > 0 && g_draw.pity >= pity_draws() && star != 7) { star = 7; forced = true; }
    } else if (!store_roll(g_draw.levels, g_draw.pity, &pc, &star, &forced)) {
        return;   // every rare at 7 stars: leave the failure
    }
    if (pc < 0 || pc >= kRareChars || star < 1 || star > 7) return;
    vm_write32(rec + 0, (uint32_t)pc);
    vm_write32(rec + 4, (uint32_t)(star - 1));
    vm_write32(rec + 8, (uint32_t)pc);
    ctx->gpr[3] = 1;
    // The game's rule (0x0044B0A8), to log this capsule; the save decides in the end.
    const int lv0 = g_draw.levels[pc], g0 = g_draw.gauges[pc];
    int lv = lv0, gauge = g0;
    if (star > lv) {
        lv = star;
    } else if (lv <= 6) {
        gauge += star_need(star - 1);
        if (gauge > kGaugeMax) gauge = kGaugeMax;
        if (gauge >= star_need(lv)) { gauge -= star_need(lv); lv++; }
    }
    g_draw.levels[pc] = lv;
    g_draw.gauges[pc] = gauge;
    g_draw.pity = star == 7 ? 0 : g_draw.pity + 1;
    if (g_draw.n < (int)(sizeof g_draw.p / sizeof g_draw.p[0]))
        g_draw.p[g_draw.n++] = {pc, star, lv0, lv, g0, gauge, forced};
    if (dbg())
        fprintf(stderr, "[hsg-capsule] roll %s: pc %d star %d%s\n", game_ok && game_roll ? "game" : "ours", pc, star,
                forced ? " (pity)" : "");
}

// Draw n capsules: record each in the store after the game applied them, then save.
void func_0044ABF4(ppu_context* ctx)
{
    const bool ours = grind_mode() && hsg_tus_local_on();
    if (ours) draw_begin();
    const int n = (int)ctx->gpr[5];
    func_0044ABF4_lifted(ctx);
    drain(ctx);
    if (!ours) return;
    const int rc = (int)ctx->gpr[3];
    const ppu_context keep = *ctx;
    fprintf(stderr, "[hsg-capsule] draw of %d -> %d\n", n, rc);
    if (rc == 0) {
        for (int i = 0; i < g_draw.n; i++) {
            const Pending& p = g_draw.p[i];
            store_record_draw(p.pc, p.star, p.lv0, p.lv1, p.g0, p.g1, p.forced);
        }
        store_save();
    }
    g_draw.active = false;
    *ctx = keep;
}

void func_0044BD0C(ppu_context* ctx)
{
    if (dbg())
        fprintf(stderr, "[hsg-capsule] tus rare bit: pc %d star-1 %d\n", (int)ctx->gpr[4], (int)ctx->gpr[5]);
    func_0044BD0C_lifted(ctx);
    drain(ctx);
}

void func_0044C4E4(ppu_context* ctx)
{
    func_0044C4E4_lifted(ctx);
    drain(ctx);
    if (dbg()) {
        long long v[4] = {0, 0, 0, 0};
        const int slot[4] = {1, 2, 5, 6};
        for (int i = 0; i < 4; i++) hsg_tus_local_peek(slot[i], &v[i]);
        fprintf(stderr, "[hsg-capsule] tus write-all: slots 1/2 %016llX %016llX 5/6 %016llX %016llX\n",
                (unsigned long long)v[0], (unsigned long long)v[1], (unsigned long long)v[2],
                (unsigned long long)v[3]);
    }
}
