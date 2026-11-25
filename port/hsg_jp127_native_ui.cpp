// JP 1.27 build only: grind feedback through the game's own UI (HSG_UNLOCKS=grind).
// (The host toast of hsg_jp127_unlocks.cpp is a fallback behind HSG_GRIND_OVERLAY=1.)
//
// 1. Round results panel. The single-player results panel is the "st" group of
//    layout_result_ranking.lay (prize_layout_ranking.hpp; layout object built by 0x003386B8,
//    group node at +0x24). Score / Points are label chips (result_01 index001/002) next to digit
//    parts. tools/jp127_english.py adds a second block to that group in the same style: label
//    chips "Ticket Pts" / "Tickets" (our renders in result_03), digit parts tkpts0 / tkfrac0 /
//    tickets0 with a '.' chip, and a score_bg shadow (tk_bg0). The panel is filled by 0x00334020
//    (r3 holder, holder+8 = layout object; tools/jp_lift_hooks.py splits it). After it runs we
//    look the parts up by name (0x0079FDAC group, name -> node) and, in grind mode after a round
//    that paid, set the digits (0x007B30EC widget = node+0x1C, value, show sign), show the block
//    (0x0079E078 node, visible) and move the game's Score / Points block left (node+0x40 is the
//    local translation, x first; 0x007A1EA8 recomputes the node's matrix) so the two sit side
//    by side under the name bar. Otherwise the block is hidden and nothing moves.
//
// 2. Shop. The offline Shop's help bar (bottom) shows the help text of the highlighted category,
//    message table 21 (560a838c) group 13, set through 0x00168730 (r3 ShopManager task, r4
//    text -> help bar 0x007B863C). On the category list (ShopManager +0x154 == 0) we pass our
//    own copy of that text with the capsule machine and the banked tickets appended
//    ("\x0bC" is the game's Triangle button glyph), so the game's help bar carries it.
//
// HSG_UI_TRACE=1 also logs message-table lookups (0x0052C658: r3 table, r4 group, r5 index ->
// char*) and sprintf (0x00A46050: r3 dest, r4 fmt) once per call site, with the guest return
// address, to map which code builds which screen text.
#include "hsg_jp127_unlocks.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <map>
#include <mutex>
#include <set>
#include <string>
#include <tuple>

void func_0052C658_lifted(ppu_context* ctx);   // message text (table, group, index) -> char*
void func_00A46050_lifted(ppu_context* ctx);   // sprintf(dest, fmt, ...)
void func_00334020_lifted(ppu_context* ctx);   // results panel "st": fill (holder, name, score, ...)
void func_00168730_lifted(ppu_context* ctx);   // Shop: set the help bar text (shop task, text)
void func_0079FDAC(ppu_context* ctx);   // layout: find node by name (group, name)
void func_0079E078(ppu_context* ctx);   // layout: node visible (node, on)
void func_007B30EC(ppu_context* ctx);   // layout: digit widget value (widget, value, sign)
void func_007A1EA8(ppu_context* ctx);   // layout: recompute node matrix (node)
void func_0052B47C(ppu_context* ctx);   // message table by id
void func_00790578(ppu_context* ctx);   // operator new(size, file, line)

using namespace hsg;

namespace {

bool trace_on()
{
    static int on = -1;
    if (on < 0) { const char* e = getenv("HSG_UI_TRACE"); on = e && *e == '1'; }
    return on != 0;
}

std::string guest_str(uint32_t a, size_t max = 80)
{
    std::string s;
    if (!a || !vm_base) return s;
    for (size_t i = 0; i < max; i++) {
        uint8_t c = vm_read8(a + i);
        if (!c) break;
        if (c < 0x20) { char b[8]; snprintf(b, sizeof b, "\\x%02x", c); s += b; }
        else s += (char)c;
    }
    return s;
}

std::mutex g_trace_mu;

// ---- guest scratch: names for the layout lookups and the help texts ----------------------
constexpr uint32_t kScratchSize = 0x800;
constexpr uint32_t kNamesOff = 0x000;     // part names, 32 bytes each
constexpr uint32_t kHelpOff = 0x400;      // help texts, 0x80 each (7 categories)
uint32_t g_scratch = 0;

uint32_t scratch(GuestCall& g)
{
    if (!g_scratch) {
        g_scratch = (uint32_t)g.call(func_00790578, kTocGasha, kScratchSize, 0xC800F0, 0x4E0);
        if (g_scratch) for (uint32_t i = 0; i < kScratchSize; i++) vm_write8(g_scratch + i, 0);
    }
    return g_scratch;
}

void put_str(uint32_t at, const char* s, uint32_t cap)
{
    uint32_t i = 0;
    for (; s[i] && i + 1 < cap; i++) vm_write8(at + i, (uint8_t)s[i]);
    vm_write8(at + i, 0);
}

// ---- results panel ------------------------------------------------------------------------
enum Part { TkBg, IdxTkPts, IdxTickets, TkPts, TkDot, TkFrac, Tickets, kOurs,
            IdxScore = kOurs, IdxPoints, IdxHandi, Score, Points, Handi, ScoreBg, kParts };
const char* const kPartName[kParts] = {
    "tk_bg0", "idx_tkpts0", "idx_tickets0", "tkpts0", "tkdot0", "tkfrac0", "tickets0",
    "idx_score0", "idx_points0", "idx_handi0", "score0", "points0", "handi0", "score_bg0"};
constexpr float kBlockShift = 88.0f;   // layout units: the two blocks 236..404 -> 148..316 | 324..492

float rd_f32(uint32_t a) { uint32_t u = vm_read32(a); float f; memcpy(&f, &u, 4); return f; }
void wr_f32(uint32_t a, float f) { uint32_t u; memcpy(&u, &f, 4); vm_write32(a, u); }

void results_panel(ppu_context* ctx, uint32_t holder)
{
    const uint32_t lay = vm_read32(holder + 8);
    const uint32_t group = lay ? vm_read32(lay + 0x24) : 0;
    if (trace_on() && !group) fprintf(stderr, "[hsg-native] results fill: holder %08X lay %08X no group\n", holder, lay);
    if (!group) return;
    GuestCall g(ctx);
    const uint32_t names = scratch(g);
    if (!names) return;
    uint32_t node[kParts];
    for (int i = 0; i < kParts; i++) {
        put_str(names + kNamesOff + i * 32, kPartName[i], 32);
        node[i] = (uint32_t)g.call(func_0079FDAC, kTocGasha, group, names + kNamesOff + i * 32);
    }
    for (int i = 0; i < kOurs; i++)
        if (!node[i]) {   // data without our parts (Japanese data, older English build)
            static bool said = false;
            if (!said) fprintf(stderr, "[hsg-native] results: no %s part in the layout, data not patched\n",
                               kPartName[i]);
            said = true;
            return;
        }
    long long add = 0, progress = 0;
    int tickets = 0, per = 12;
    const bool show = grind_mode() && round_award(&add, &tickets, &progress, &per);
    if (trace_on())
        fprintf(stderr, "[hsg-native] results fill: holder %08X group %08X tk_bg %08X score_bg %08X show %d\n",
                holder, group, node[TkBg], node[ScoreBg], show ? 1 : 0);
    // 0x0079E078(part, hide): sets bit0 of part+0x16, which hides the part.
    for (int i = 0; i < kOurs; i++) g.call(func_0079E078, kTocGasha, node[i], show ? 0 : 1);
    if (show) {
        // Ticket Pts: points this round to one decimal, "3" "." "0". No sign: awards are never
        // negative and the widget's sign mode prints a zero int part with a plus-minus sign.
        const long long tenths = (add + 5) / 10;
        g.call(func_007B30EC, kTocGasha, vm_read32(node[TkPts] + 0x1C), (uint64_t)(int64_t)(tenths / 10), 0);
        g.call(func_007B30EC, kTocGasha, vm_read32(node[TkFrac] + 0x1C), (uint64_t)(int64_t)(tenths % 10), 0);
        g.call(func_007B30EC, kTocGasha, vm_read32(node[Tickets] + 0x1C), (uint64_t)(int64_t)tickets, 0);
    }
    // Part = {+0 rgba, +4 x0, +8 y0, +0xC x1, +0x10 y1 (f32 layout units), +0x16 flags, +0x1C widget
    // or 0 (chips)}. The game's block sits kBlockShift left of ours in the data; with the rows shown
    // it moves another kBlockShift left so the two sit side by side, else it goes back. Idempotent:
    // the shift is taken from where score_bg0 is now.
    const float target = rd_f32(node[TkBg] + 4) - kBlockShift * (show ? 2.0f : 1.0f);
    const float dx = target - rd_f32(node[ScoreBg] + 4);
    // Widgets (digits) carry their own matrix (widget+0x40 = x translation). Fit x = a*x0 + b*x1 + c
    // from our three digit parts, then a rect move of dx moves the widget (a + b) * dx.
    float k = 0.0f;
    {
        const int dp[3] = {TkPts, TkFrac, Tickets};
        double m[3][4];
        bool ok = true;
        for (int r = 0; r < 3; r++) {
            const uint32_t w = vm_read32(node[dp[r]] + 0x1C);
            if (!w) { ok = false; break; }
            m[r][0] = rd_f32(node[dp[r]] + 4); m[r][1] = rd_f32(node[dp[r]] + 0xC); m[r][2] = 1.0;
            m[r][3] = rd_f32(w + 0x40);
        }
        // Cramer's rule
        auto det3 = [](double a[3][3]) {
            return a[0][0] * (a[1][1] * a[2][2] - a[1][2] * a[2][1]) - a[0][1] * (a[1][0] * a[2][2] - a[1][2] * a[2][0]) +
                   a[0][2] * (a[1][0] * a[2][1] - a[1][1] * a[2][0]);
        };
        if (ok) {
            double A[3][3], Ba[3][3], Bb[3][3];
            for (int r = 0; r < 3; r++)
                for (int c = 0; c < 3; c++) {
                    A[r][c] = m[r][c];
                    Ba[r][c] = c == 0 ? m[r][3] : m[r][c];
                    Bb[r][c] = c == 1 ? m[r][3] : m[r][c];
                }
            const double d = det3(A);
            if (d > 1e-6 || d < -1e-6) k = (float)((det3(Ba) + det3(Bb)) / d);
        }
        if (!(k > -0.01f && k < 8.0f)) k = 0.0f;
    }
    if (dx > 0.5f || dx < -0.5f) {
        for (int i = kOurs; i < kParts; i++) {
            if (!node[i]) continue;
            wr_f32(node[i] + 4, rd_f32(node[i] + 4) + dx);
            wr_f32(node[i] + 0xC, rd_f32(node[i] + 0xC) + dx);
            const uint32_t w = vm_read32(node[i] + 0x1C);
            if (!w || k == 0.0f) continue;
            wr_f32(w + 0x40, rd_f32(w + 0x40) + k * dx);
            g.call(func_007A1EA8, kTocGasha, w);
        }
    }
    if (trace_on())
        fprintf(stderr, "[hsg-native] results: show %d, +%lld cents, %d tickets; moved %.1f (widget k %.3f)\n",
                show ? 1 : 0, add, tickets, dx, k);
}

// ---- shop help bar ---------------------------------------------------------------------------
constexpr int kHelpTable = 21, kHelpGroup = 13, kHelpMax = 7;

uint32_t shop_help(ppu_context* ctx, uint32_t shop, uint32_t text)
{
    if (!grind_mode() || !text || vm_read32(shop + 0x154) != 0 || store_all_maxed()) return text;
    GuestCall g(ctx);
    const uint32_t tbl = (uint32_t)g.call(func_0052B47C, kTocGasha, kHelpTable);
    if (!tbl || !vm_read32(tbl + 4)) return text;
    const uint32_t grp = vm_read32(tbl + 0xC) + kHelpGroup * 12;
    const uint32_t arr = vm_read32(grp), cnt = vm_read32(grp + 4);
    int idx = -1;
    for (uint32_t i = 0; i < cnt && i < (uint32_t)kHelpMax; i++)
        if (vm_read32(arr + i * 4) == text) idx = (int)i;
    const uint32_t buf = idx >= 0 ? scratch(g) : 0;
    if (!buf) return text;
    const int t = store_tickets();
    char s[0x80];
    // Help font button glyphs "\x0b" + letter (seen 11-24): @ Triangle, A Cross, B Square, C Circle,
    // D L1, E R1, F d-pad, G L stick, H/I/J d-pad directions.
    snprintf(s, sizeof s, "%s   \x0b" "@ Capsule Machine (%d ticket%s)", guest_str(text, 0x50).c_str(), t,
             t == 1 ? "" : "s");
    const uint32_t at = buf + kHelpOff + (uint32_t)idx * 0x80;
    put_str(at, s, 0x80);
    return at;
}

}  // namespace

void func_00334020(ppu_context* ctx)
{
    const uint32_t holder = (uint32_t)ctx->gpr[3];
    func_00334020_lifted(ctx);
    drain(ctx);
    if (vm_base && holder) results_panel(ctx, holder);
}

void func_00168730(ppu_context* ctx)
{
    if (vm_base && ctx->gpr[3]) ctx->gpr[4] = shop_help(ctx, (uint32_t)ctx->gpr[3], (uint32_t)ctx->gpr[4]);
    func_00168730_lifted(ctx);
}

void func_0052C658(ppu_context* ctx)
{
    const uint32_t lr = (uint32_t)ctx->lr;
    const int t = (int32_t)ctx->gpr[3], g = (int32_t)ctx->gpr[4], i = (int32_t)ctx->gpr[5];
    func_0052C658_lifted(ctx);
    if (!trace_on()) return;
    static std::set<std::tuple<uint32_t, int, int, int>> seen;
    std::lock_guard<std::mutex> lk(g_trace_mu);
    if (!seen.insert({lr, t, g, i}).second) return;
    fprintf(stderr, "[ui-trace] msg lr=%08X t=%d g=%d i=%d -> \"%s\"\n", lr, t, g, i,
            guest_str((uint32_t)ctx->gpr[3]).c_str());
}

void func_00A46050(ppu_context* ctx)
{
    const uint32_t lr = (uint32_t)ctx->lr, dst = (uint32_t)ctx->gpr[3], fmt = (uint32_t)ctx->gpr[4];
    func_00A46050_lifted(ctx);
    if (!trace_on()) return;
    static std::set<std::pair<uint32_t, uint32_t>> seen;
    std::lock_guard<std::mutex> lk(g_trace_mu);
    if (!seen.insert({lr, fmt}).second) return;
    fprintf(stderr, "[ui-trace] fmt lr=%08X dst=%08X \"%s\" -> \"%s\"\n", lr, dst,
            guest_str(fmt).c_str(), guest_str(dst).c_str());
}
