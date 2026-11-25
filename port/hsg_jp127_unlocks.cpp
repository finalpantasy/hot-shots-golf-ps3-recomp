// JP 1.27 build only (HSG_TARGET_PROFILE=jp-1.27, pipeline-jp127.toml).
//
// Offline rare-character ownership (HSG_UNLOCKS).
//
// In JP 1.27 the capsule machine granted rare versions of Pc_000-014. The game
// keeps each one's star level (0 = not owned, 1-7) in the save: per-character
// record byte 0, low 6 bits (record = 0x000333E4(save + 0x11B40, pc); save =
// *(u32*)0x017C90F4). Character select, profile, VS and the capsule draw odds all
// read that byte. Online, the level came from Title User Storage: the gashapon
// manager read a 105-bit field (bit pc*7 + stars-1) and its SyncFromTus
// (0x0044B9D4) called SetRareLevel (0x0044B7D8: r4 pc, r5 level, r6 save+0x11B40;
// r3 unused) for all 15. SetRareLevel writes the level and unlocks the rare
// costume entries (cos 2 colours) the way the server sync did. Offline the TUS
// read fails and nothing calls it.
//
// Here the offline store stands in for TUS: tools/jp_lift_hooks.py splits the
// gashapon manager tick (0x004452C8, called from Main_Tick when the manager
// exists), and after each tick (every 30th) any character whose saved level
// differs from the store gets the game's own SetRareLevel.
//
// HSG_UNLOCKS:
//   unset / original  no change (the hooks return after the original code)
//   all               every rare character owned at 7 stars; no file written
//   store             levels from <PS3_SAVEDATA_ROOT>/hsg_unlocks.txt (read-only)
//   grind             tickets earned by play, spent on offline capsule draws;
//                     the store file is read at boot and written on every change
// Store file (text, one entry per line, '#' comments):
//   rare <pc 0-14> <stars 0-7>
//   cpoints <n>                grind progress toward the next ticket, in 1/100 points
//                              (an older "points <n>" line is read as whole points)
//   tickets <count>            unspent tickets
//   gauge <pc 0-14> <n>        grind duplicate gauge toward the next star (0-63, as the game)
//   earned <n> / draws <n>     grind lifetime totals: tickets earned, capsules drawn
//   pity <n>                   draws since the last red capsule
//   won <event 0-48>           first win taken for that Challenge event (one line each)
//   last <event> <n>           the last paying event and how many times in a row
//   tier <n>                   highest Challenge tier reached (anti-farm reference)
//   shop <n>                   lifetime shop points paid for tickets after everything was maxed
//   tus <slot 1-63> <value>    capsule machine Title User Storage slots other than the rare
//                              bits and gauges (those come from rare/gauge; capsule.cpp)
// (An older two-number "points <pc> <n>" line is read as gauge.)
// Levels persist in the game save once applied (the game writes the record).
// HSG_UNLOCKS_DEBUG=1 logs game-mode changes and save words changed by each round.
// HSG_UNLOCKS_TEST_AWARD=<points> (grind, testing) grants that many points once, ~10 s after
// boot, through award_points() as Event::Test (no anti-farm, rate applies).
// HSG_UNLOCKS_SEED=<n> (testing) seeds the capsule RNG so tools/grind_sim.py --replay <n>
// prints the same draws. HSG_UNLOCKS_TEST_ONEHOLE=1 (testing) ends every Challenge round
// after its first hole (writes the round's last-hole index, game info +0x323, to 0).
// HSG_UNLOCKS_TEST_PLACE=<1-20> (testing) overwrites the player's placement (result +0x66) at
// round end, so the results screen and the award use that rank (ordinal suffix checks).
//
// Grind earning (milestone 3, design: memory note grind-ticket-economy):
//  - The round-end prize screen is built by PrizeManager's constructor (0x00348384,
//    called from the game.cpp prize step 0x0068C500 when a round is over; quitting
//    from the pause menu does not reach it); tools/jp_lift_hooks.py splits it. At
//    that point the round is final, and on_round_end() reads it from game state:
//      game info gi = *(u32)0x0186FA50 (set by 0x006ABE90 when a Challenge event starts):
//        +0x394 mode (2 = Challenge tournament, 1 = Challenge VS / Cosplay match)
//        +0x379 tier (s8, 0-6), +0x37A slot in the tier (s8, 0-6), +0x37C event record
//        +0x321 holes in the round (u8; copied from record +0x15)
//      event record (Challenge_ChallengeList row, parser 0x00295454): +0x00 label number
//        (u16), +0x0A kind (0 Tournament_, 1 VS_, 2 Cosplay_), +0x15 holes
//      local player result = 0x006AE704(*(u32)0x0186FAD0) (what the prize code reads,
//        0x0033F168): +0x66 placement (u16, 0 = 1st; set by 0x0068DF40), +0x6B VS outcome
//        (s8, 0..2 = won: the prize code 0x003494E0 counts it a win the same way),
//        +0x26 handicap (u16), +0xD0 round score: +0x1C strokes, +0x24 par.
//      Score vs par = strokes - par - handicap (the prize code 0x00340D14, prize +0x27C).
//      Tournament won = placement 0 (0x003494E0, prize +0x99C).
//    Event id = tier * 7 + slot (0-48).
//  - award_points(kind, tier, holes, placement, under_par, event_id) is the single place
//    progress is granted (points in 1/100 so halves and quarters add up):
//      tournament placement 1st 10 / 2nd-3rd 6 / 4th-10th 3 / 11th-20th 1, half under 18 holes
//      under par +2, +4 at -5 or better over 18 holes
//      first win of each of the 35 tournaments +10 once; of each of the 14 VS/Cosplay +20 once
//      VS/Cosplay rematch win at the current tier +5, lower tiers 0
//      anti-farm on the ordinary points (not the one-time bonuses): one tier below the
//      current (highest reached) tier 25%, two or more below 0; the same event back to back
//      100/50/25/10%, reset by a different event; tier 6 is always full
//      HSG_TICKET_RATE multiplies everything (0.5, 1, 2; default 1)
//    Only modes that pay (default 1 and 2; HSG_TICKET_MODES overrides) reach it, so
//    practice, free play and quit pay nothing.
//  - Drawing: in the game's own capsule machine (the online lobby capsule shop, hosted
//    offline in the Shop by hsg_jp127_capsule.cpp: Triangle on the Shop's top menu). Earned
//    tickets bank in the store; the machine shows the store's count and each ticket it uses
//    is taken from the store at once. The outcome: offline the game's roll (0x0044A6C0)
//    has no odds table (server CSV) and fails, so capsule.cpp supplies ours: a capsule is
//    blue (1-3 stars), purple (4-6) or red (7) by kOddsBlue/kOddsPurple/kOddsRed, star
//    uniform within the colour, for a character picked uniformly among those below 7 stars
//    (the game's pick 0x004496F0 starts each candidate at weight 1.0 and multiplies in
//    server-fed modifier lists, empty offline). After kPityDraws draws without a red, the
//    next capsule is red (also forced on the game's own roll once it has odds). Then the
//    game's own result code applies it (0x0044ABF4, its 0x0044B0A8-0x0044B1A0 block; the
//    game works in star-1 / level-1, 0x00444FF8 = saved level - 1):
//      capsule star > level            -> level = capsule star
//      level 1-6, capsule <= level     -> gauge += T(capsule - 1); if gauge >= T(level):
//                                         gauge -= T(level), level + 1 (one step)
//      level 7                         -> no change (the pick skips 7-star characters)
//    So a duplicate at 6 stars can also reach 7 (T(6) = 20). The gauge is clamped 0-63 (the
//    game's 6-bit field in the TUS blob, 0x0044BF64/0x0044B6D0). T is 0x00444924, a jump
//    table: T(0..6) = 1,2,4,8,12,16,20 and 0 above 6. tools/grind_sim.py runs the same rule.
//    capsule.cpp copies the result (levels, gauges, pity, draws) into the store and saves it
//    right after each draw; every capsule logs one "[hsg-unlocks] draw:" line on stderr.
//    HSG_TICKET_AUTODRAW=1 (old behaviour, testing) still draws every ticket at round end
//    with draw_one(), the same rule without the machine.
//  - After all 15 are at 7 stars each ticket pays kShopPointsPerTicket shop points
//    through the game's own AddMoney (0x00036C9C(save + 0x11B40, n); balance at
//    +0x7D3D8, capped at 999,999,999 by the game).
//  - On-screen notice: the prize screen's layouts are built from fixed parts
//    (0x0033A0EC) and no cheap message path was found, so the results are a host toast
//    (rsx_overlay_post, external/ps3recomp libs/video/rsx_overlay.c, patch 0076) drawn
//    by the renderer over the frame: the award and each draw at round end (6 s), and the
//    totals once at boot (4 s). Grind only. Also logged ("[hsg-unlocks] award:").
#include "hsg_jp127_unlocks.h"
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <map>
#include <set>
#include <string>
#include <vector>

void func_004452C8_lifted(ppu_context* ctx);
void func_00348384_lifted(ppu_context* ctx);   // PrizeManager ctor (round over)
void func_000333E4(ppu_context* ctx);   // chara record of (save + 0x11B40, pc)
void func_0044B7D8(ppu_context* ctx);   // SetRareLevel(mgr, pc, level, save + 0x11B40)
void func_00444924(ppu_context* ctx);   // star level -> capsule points (0..6; else 0)
void func_006AE704(ppu_context* ctx);   // local player's round result (results array)
void func_00036C9C(ppu_context* ctx);   // AddMoney(save + 0x11B40, n)
extern "C" void rsx_overlay_post(const char* const* lines, int n, int ms);   // rsx_overlay.c

namespace {

using namespace hsg;

// ---- grind rates (edit here) -----------------------------------------------------------
constexpr int kCent = 100;              // store unit: 1/100 point
constexpr int kPointsPerTicket = 12;    // award_points() progress per ticket
// Tournament placement points (18 holes; half below 18 holes).
constexpr int kPlace1st = 10, kPlace2nd3rd = 6, kPlace4th10th = 3, kPlace11th20th = 1;
constexpr int kUnderPar = 2, kUnderPar5 = 4;   // under par; -5 or better over 18 holes
constexpr int kFirstWinTournament = 10;  // once per tournament (35)
constexpr int kFirstWinVs = 20;          // once per VS / Cosplay rival (14)
constexpr int kVsRematch = 5;            // VS / Cosplay rematch win at the current tier
constexpr int kRepeatPct[] = {100, 50, 25, 10};   // same event back to back
constexpr int kOneTierBelowPct = 25;     // two or more tiers below: 0
constexpr int kFullTier = 6;             // this tier always pays in full
// Capsule colour odds (relative weights): blue 1-3 stars, purple 4-6, red 7.
// Original-like odds (a JP player's logged pulls; approved 11-24). tools/grind_sim.py with
// pity 25 and the game's real rule: mean ~110 tickets to max all 15 (p10 ~90, p90 ~131).
constexpr int kOddsBlue = 72;
constexpr int kOddsPurple = 20;
constexpr int kOddsRed = 8;
constexpr int kPityDraws = 25;           // after this many draws without red, the next is red
constexpr int kShopPointsPerTicket = 5000;   // per ticket once all 15 are at 7 stars

constexpr uint32_t kSavePtr = 0x017C90F4;   // *(u32) = save data
constexpr uint32_t kSaveSub = 0x11B40;      // save + this = chara block / AddMoney base
constexpr uint32_t kMoneyOff = 0x7D3D8;     // AddMoney base + this = shop point balance
constexpr uint32_t kGameInfoPtr = 0x0186FA50;  // *(u32) = game setup (offsets above)
constexpr uint32_t kResultsPtr = 0x0186FAD0;   // *(u32) = players' round results
constexpr int kTiers = 7, kSlots = 7;       // Challenge: 7 tiers x 7 events

enum class Mode { Original, All, Store, Grind };

struct Store {
    int rare[kRareChars] = {};
    int gauge[kRareChars] = {};
    long long cpoints = 0;
    int tickets = 0;
    int earned = 0;
    int draws = 0;
    int pity = 0;
    int last_event = -1, last_count = 0;
    int top_tier = 0;
    long long shop = 0;
    std::set<int> won;
    std::map<int, long long> tus;   // capsule machine TUS slots other than rare bits / gauges

    static std::string path()
    {
        const char* root = getenv("PS3_SAVEDATA_ROOT");
        return std::string(root && *root ? root : ".") + "/hsg_unlocks.txt";
    }

    bool load()
    {
        FILE* f = fopen(path().c_str(), "rb");
        if (!f) return false;
        char line[256];
        while (fgets(line, sizeof line, f)) {
            int a = 0, b = 0;
            long long q = 0;
            if (sscanf(line, " rare %d %d", &a, &b) == 2 && a >= 0 && a < kRareChars)
                rare[a] = b < 0 ? 0 : b > kMaxStars ? kMaxStars : b;
            else if ((sscanf(line, " gauge %d %d", &a, &b) == 2 ||
                      sscanf(line, " points %d %d", &a, &b) == 2) && a >= 0 && a < kRareChars)
                gauge[a] = b < 0 ? 0 : b > kGaugeMax ? kGaugeMax : b;
            else if (sscanf(line, " cpoints %lld", &q) == 1)
                cpoints = q < 0 ? 0 : q;
            else if (sscanf(line, " points %d", &a) == 1)
                cpoints = a < 0 ? 0 : (long long)a * kCent;
            else if (sscanf(line, " tickets %d", &a) == 1)
                tickets = a < 0 ? 0 : a;
            else if (sscanf(line, " earned %d", &a) == 1)
                earned = a < 0 ? 0 : a;
            else if (sscanf(line, " draws %d", &a) == 1)
                draws = a < 0 ? 0 : a;
            else if (sscanf(line, " pity %d", &a) == 1)
                pity = a < 0 ? 0 : a;
            else if (sscanf(line, " won %d", &a) == 1 && a >= 0 && a < kTiers * kSlots)
                won.insert(a);
            else if (sscanf(line, " last %d %d", &a, &b) == 2)
                last_event = a, last_count = b < 0 ? 0 : b;
            else if (sscanf(line, " tier %d", &a) == 1)
                top_tier = a < 0 ? 0 : a >= kTiers ? kTiers - 1 : a;
            else if (sscanf(line, " shop %lld", &q) == 1)
                shop = q < 0 ? 0 : q;
            else if (sscanf(line, " tus %d %lld", &a, &q) == 2 && a >= 1 && a <= 63)
                tus[a] = q;
        }
        fclose(f);
        return true;
    }

    bool save() const
    {
        const std::string p = path(), tmp = p + ".tmp";
        FILE* f = fopen(tmp.c_str(), "wb");
        if (!f) return false;
        fprintf(f, "# Hot Shots Golf Ultimate offline unlocks (HSG_UNLOCKS store / grind)\n");
        for (int i = 0; i < kRareChars; i++) fprintf(f, "rare %d %d\n", i, rare[i]);
        fprintf(f, "cpoints %lld\ntickets %d\n", cpoints, tickets);
        for (int i = 0; i < kRareChars; i++)
            if (gauge[i]) fprintf(f, "gauge %d %d\n", i, gauge[i]);
        fprintf(f, "earned %d\ndraws %d\npity %d\ntier %d\n", earned, draws, pity, top_tier);
        if (last_event >= 0) fprintf(f, "last %d %d\n", last_event, last_count);
        for (int e : won) fprintf(f, "won %d\n", e);
        if (shop) fprintf(f, "shop %lld\n", shop);
        for (const auto& t : tus)
            if (t.second) fprintf(f, "tus %d %lld\n", t.first, t.second);
        const bool ok = fclose(f) == 0;
        remove(p.c_str());
        return ok && rename(tmp.c_str(), p.c_str()) == 0;
    }
};

Store g_store;
bool g_debug = false;

// ---- on-screen toast (grind) ---------------------------------------------------------------
// Lines collected while an award is handled, posted as one toast by toast_flush(). UTF-8;
// "\x1b" + letter picks a colour (rsx_overlay.h).
#define STAR "\xE2\x98\x85"
#define ARROW "\xE2\x86\x92"
#define TRIANGLE "\xE2\x96\xB3"
constexpr int kToastLines = 6;
std::vector<std::string> g_toast;

void toast(const char* fmt, ...)
{
    char buf[200];
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(buf, sizeof buf, fmt, ap);
    va_end(ap);
    g_toast.push_back(buf);
}

// The host overlay is a fallback (HSG_GRIND_OVERLAY=1): by default the grind news shows in the
// game's own UI (hsg_jp127_native_ui.cpp) and the lines only go to the log.
bool overlay_on()
{
    static int on = -1;
    if (on < 0) { const char* e = getenv("HSG_GRIND_OVERLAY"); on = e && *e == '1'; }
    return on != 0;
}

void toast_flush(int ms)
{
    if (g_toast.empty()) return;
    if (!overlay_on()) { g_toast.clear(); return; }
    if ((int)g_toast.size() > kToastLines) {   // keep the first lines, summarize the rest
        const int more = (int)g_toast.size() - (kToastLines - 1);
        g_toast.resize(kToastLines - 1);
        toast("\x1b" "dand %d more", more);
    }
    std::vector<const char*> p;
    for (const std::string& l : g_toast) p.push_back(l.c_str());
    rsx_overlay_post(p.data(), (int)p.size(), ms);
    g_toast.clear();
}

// Display names of Pc_000-014 (the base characters the rares are versions of).
const char* chara_name(int pc)
{
    static const char* const k[kRareChars] = {
        "Yuna", "Yamato", "Isabelle", "Chang", "Lani", "Pancho", "Grace", "Stuart",
        "Xiao Ling", "Max", "Pandora", "Izzak", "Amy", "Gloria", "Erika"};
    return pc >= 0 && pc < kRareChars ? k[pc] : "?";
}

std::string with_commas(long long v)
{
    std::string d = std::to_string(v < 0 ? -v : v), o;
    for (size_t i = 0; i < d.size(); i++) {
        if (i && (d.size() - i) % 3 == 0) o += ',';
        o += d[i];
    }
    return v < 0 ? "-" + o : o;
}

int env_int(const char* name, int dflt)
{
    const char* e = getenv(name);
    return e && *e ? atoi(e) : dflt;
}

Mode init_mode()
{
    g_debug = env_int("HSG_UNLOCKS_DEBUG", 0) != 0;
    const char* e = getenv("HSG_UNLOCKS");
    if (!e || !*e || !strcmp(e, "original")) return Mode::Original;
    if (!strcmp(e, "all")) {
        for (int& r : g_store.rare) r = kMaxStars;
        fprintf(stderr, "[hsg-unlocks] mode all: rare Pc_000-014 at %d stars\n", kMaxStars);
        return Mode::All;
    }
    if (!strcmp(e, "store") || !strcmp(e, "grind")) {
        const bool ok = g_store.load();
        const bool grind = e[0] == 'g';
        if (grind && !ok) g_store.save();   // a fresh profile starts with an empty store
        fprintf(stderr, "[hsg-unlocks] mode %s: %s %s (tickets %d)\n", e, Store::path().c_str(),
                ok ? "loaded" : grind ? "created" : "missing (all levels 0)", g_store.tickets);
        return grind ? Mode::Grind : Mode::Store;
    }
    fprintf(stderr, "[hsg-unlocks] unknown HSG_UNLOCKS=%s, using original\n", e);
    return Mode::Original;
}

Mode mode()
{
    static const Mode m = init_mode();
    return m;
}

void apply(ppu_context* ctx)
{
    const uint32_t save = vm_read32(kSavePtr);
    if (!save) return;
    const uint32_t sub = save + kSaveSub;
    GuestCall g(ctx);
    static int logged = 0;
    for (int pc = 0; pc < kRareChars; pc++) {
        const uint32_t rec = (uint32_t)g.call(func_000333E4, kTocCore, sub, (uint64_t)pc);
        if (!rec) continue;
        const int have = vm_read8(rec) & 0x3F, want = g_store.rare[pc];
        if (have == want) continue;
        g.call(func_0044B7D8, kTocGasha, vm_read32(kMgrPtr), (uint64_t)pc, (uint64_t)want, sub);
        if (logged++ < 64)
            fprintf(stderr, "[hsg-unlocks] Pc_%03d rare %d -> %d (now %d)\n", pc, have, want,
                    vm_read8(rec) & 0x3F);
    }
}

// ---- grind -------------------------------------------------------------------------------

uint32_t game_info() { return vm_read32(kGameInfoPtr); }

int game_mode()
{
    const uint32_t gi = game_info();
    return gi ? (int)vm_read32(gi + 0x394) : -1;
}

// T(n): the game's star/points table 0x00444924 (jump table; 1,2,4,8,12,16,20 for 0-6, else 0).
int star_points(ppu_context* ctx, int n)
{
    static const int known[] = {1, 2, 4, 8, 12, 16, 20};
    if (!vm_read32(kMgrPtr)) return n >= 0 && n <= 6 ? known[n] : 0;
    GuestCall g(ctx);
    return (int)(int8_t)g.call(func_00444924, kTocGasha, vm_read32(kMgrPtr), (uint64_t)n);
}

// xorshift32; tools/grind_sim.py --replay mirrors it (and the call order in draw_one).
unsigned rng()
{
    static unsigned s = [] {
        const char* e = getenv("HSG_UNLOCKS_SEED");
        unsigned v = e && *e ? (unsigned)strtoul(e, nullptr, 10)
                             : (unsigned)time(nullptr) * 2654435761u + 12345u;
        return v ? v : 1u;
    }();
    s ^= s << 13; s ^= s >> 17; s ^= s << 5;
    return s;
}

// One capsule by our odds and pity for a character below 7 stars (levels: 0-7 per
// character). pity: draws since the last red. False when every rare is at 7 stars.
// tools/grind_sim.py --replay mirrors the rng() call order.
bool roll_capsule(const int* levels, int pity, int* pc_out, int* star_out, bool* forced_out)
{
    std::vector<int> pool;
    for (int pc = 0; pc < kRareChars; pc++)
        if (levels[pc] < kMaxStars) pool.push_back(pc);
    if (pool.empty()) return false;
    const int pc = pool[rng() % pool.size()];
    const bool forced = kPityDraws > 0 && pity >= kPityDraws;
    int star;
    if (forced) {
        star = 7;
    } else {
        const int roll = (int)(rng() % (unsigned)(kOddsBlue + kOddsPurple + kOddsRed));
        if (roll < kOddsBlue) star = 1 + (int)(rng() % 3);
        else if (roll < kOddsBlue + kOddsPurple) star = 4 + (int)(rng() % 3);
        else star = 7;
    }
    *pc_out = pc; *star_out = star; *forced_out = forced;
    return true;
}

const char* colour_of(int star) { return star == 7 ? "red" : star >= 4 ? "purple" : "blue"; }

// Store and log one drawn capsule (the result already decided: lv0/g0 before, lv1/g1 after).
void record_draw(int pc, int star, int lv0, int lv1, int g0, int g1, bool forced)
{
    const int pity0 = g_store.pity;
    g_store.pity = star == 7 ? 0 : g_store.pity + 1;
    g_store.rare[pc] = lv1;
    g_store.gauge[pc] = g1;
    g_store.draws++;
    fprintf(stderr, "[hsg-unlocks] draw: pc=%d capsule=%s star=%d gauge %d->%d level %d->%d%s"
            " (draw %d, pity %d%s)\n", pc, colour_of(star), star, g0, g1, lv0, lv1,
            lv0 == 0 ? " NEW" : "", g_store.draws, pity0, forced ? " forced" : "");
}

// One capsule without the machine (HSG_TICKET_AUTODRAW=1), the game's rule (see the header).
// Returns the character drawn, or -1 when every rare is at 7 stars.
int draw_one(ppu_context* ctx)
{
    int pc, star;
    bool forced;
    if (!roll_capsule(g_store.rare, g_store.pity, &pc, &star, &forced)) return -1;
    const int lv0 = g_store.rare[pc], g0 = g_store.gauge[pc];
    int lv = lv0, gauge = g0, need = 0;
    if (star > lv) {
        lv = star;
    } else if (lv <= 6) {                 // 0x0044B0A8, in star-1 / level-1 terms
        gauge += star_points(ctx, star - 1);
        if (gauge > kGaugeMax) gauge = kGaugeMax;
        need = star_points(ctx, lv);
        if (gauge >= need) { gauge -= need; lv++; }
    }
    record_draw(pc, star, lv0, lv, g0, gauge, forced);
    const char* head = star == 7 ? "\x1br" "Red capsule!" : star >= 4 ? "\x1bp" "Purple capsule:"
                                                                      : "\x1b" "bBlue capsule:";
    const char* name = chara_name(pc);
    if (lv0 == 0)
        toast("%s Rare %s " STAR "%d NEW", head, name, star);
    else if (star > lv0)
        toast("%s Rare %s " STAR "%d (was " STAR "%d)", head, name, star, lv0);
    else if (lv > lv0)
        toast("%s Rare %s " STAR "%d " ARROW " level up " STAR "%d", head, name, star, lv);
    else
        toast("%s Rare %s " STAR "%d " ARROW " gauge %d%%", head, name, star,
              need > 0 ? gauge * 100 / need : 0);
    return pc;
}

bool all_maxed()
{
    for (int r : g_store.rare)
        if (r < kMaxStars) return false;
    return true;
}

uint32_t money_base()
{
    const uint32_t save = vm_read32(kSavePtr);
    return save ? save + kSaveSub : 0;
}

// Round end with new tickets. They bank for the capsule machine; once every rare is at 7
// stars they become shop points instead. HSG_TICKET_AUTODRAW=1 draws them all here (old way).
void spend_tickets(ppu_context* ctx)
{
    const bool autodraw = env_int("HSG_TICKET_AUTODRAW", 0) != 0;
    if (!autodraw && !all_maxed()) return;
    bool any = false;
    int shop_tickets = 0;
    while (g_store.tickets > 0) {
        if (all_maxed() || draw_one(ctx) < 0) {
            // Everything maxed: each ticket becomes shop points (the game's AddMoney).
            const uint32_t base = money_base();
            if (!base) break;
            shop_tickets = g_store.tickets;
            break;
        }
        g_store.tickets--;
        any = true;
    }
    if (shop_tickets > 0) {
        const uint32_t base = money_base();
        const long long pts = (long long)shop_tickets * kShopPointsPerTicket;
        const uint32_t before = vm_read32(base + kMoneyOff);
        {
            GuestCall g(ctx);
            g.call(func_00036C9C, kTocCore, base, (uint64_t)(int64_t)(int32_t)pts);
        }
        g_store.tickets -= shop_tickets;
        g_store.shop += pts;
        any = true;
        toast("\x1bg+%d ticket%s " ARROW " %s points", shop_tickets, shop_tickets == 1 ? "" : "s",
              with_commas(pts).c_str());
        fprintf(stderr, "[hsg-unlocks] all %d rares at %d stars: %d ticket(s) -> %lld shop points"
                " (balance %u -> %u)\n", kRareChars, kMaxStars, shop_tickets, pts, before,
                vm_read32(base + kMoneyOff));
    }
    if (any) g_store.save();
}

// Game modes (+0x394) whose rounds pay. 2 = Challenge tournament, 1 = Challenge VS/Cosplay
// (both set by 0x006ABE90 from the event row). Other values in the program: main menu sets 7
// and 8 (0x0060D17C), training 3 (0x006A9F60), 0 is the boot default (0x002D8D38), 9/10 get
// their own prize layouts, 12-15 are tested by the online helpers 0x006A8080/0x006A805C/
// 0x006A8294. HSG_TICKET_MODES=<n>[,<n>...] replaces the list (testing, house rules);
// HSG_UNLOCKS_DEBUG=1 logs every mode change.
bool mode_pays(int m)
{
    static std::vector<int> modes = [] {
        std::vector<int> v;
        const char* e = getenv("HSG_TICKET_MODES");
        if (!e || !*e) return std::vector<int>{1, 2};
        for (const char* p = e; *p;) {
            char* end = nullptr;
            const long n = strtol(p, &end, 10);
            if (end == p) { p++; continue; }
            v.push_back((int)n);
            p = end;
        }
        return v;
    }();
    for (int x : modes)
        if (x == m) return true;
    return false;
}

// HSG_TICKET_RATE: multiplier on every award (0.5, 1, 2; default 1), in percent.
int rate_pct()
{
    static const int r = [] {
        const char* e = getenv("HSG_TICKET_RATE");
        double v = e && *e ? atof(e) : 1.0;
        if (!(v >= 0)) v = 1.0;
        if (v > 10) v = 10;
        return (int)(v * 100 + 0.5);
    }();
    return r;
}

// Event kinds for award_points().
enum class Event { Tournament, Vs, Cosplay, Test };   // Vs opens the next tier when won
const char* kind_name(Event k)
{
    return k == Event::Tournament ? "tournament" : k == Event::Vs ? "vs"
         : k == Event::Cosplay ? "cosplay" : "test";
}
int g_test_points = 0;   // Event::Test amount (HSG_UNLOCKS_TEST_AWARD)
int g_round_serial = 0;   // round ends seen (PrizeManager ctor, grind)
int g_award_serial = -1;  // g_round_serial of the last round that paid
long long g_last_add = 0; // its points, 1/100

// The one place grind progress is granted. Tournament / Vs / Cosplay: tier 0-6, holes,
// placement (1-based; for Vs and Cosplay 1 = won, 2 = lost), under_par (strokes under par, negative = over),
// event_id (tier * 7 + slot). Returns the 1/100 points added.
long long award_points(ppu_context* ctx, Event kind, int tier, int holes, int placement,
                       int under_par, int event_id)
{
    long long base = 0, bonus = 0;   // 1/100 points: ordinary (anti-farm applies), one-time
    long long raw = 0;               // ordinary before anti-farm (log)
    int farm_pct = 100;
    const char* why = "";
    if (kind == Event::Test) {
        bonus = (long long)g_test_points * kCent;
    } else {
        const bool vs = kind == Event::Vs || kind == Event::Cosplay;
        const bool won = placement == 1;
        // Ordinary points.
        if (!vs) {
            const int p = placement <= 0 ? 0 : placement == 1 ? kPlace1st
                        : placement <= 3 ? kPlace2nd3rd : placement <= 10 ? kPlace4th10th
                        : placement <= 20 ? kPlace11th20th : 0;
            base += (long long)p * kCent;
            if (holes > 0 && holes < 18) base /= 2;   // short events pay half
        } else if (won && g_store.won.count(event_id) && tier >= g_store.top_tier) {
            base += (long long)kVsRematch * kCent;
        }
        if (under_par > 0)
            base += (long long)(under_par >= 5 && holes >= 18 ? kUnderPar5 : kUnderPar) * kCent;
        // One-time first wins.
        if (won && event_id >= 0 && !g_store.won.count(event_id)) {
            bonus += (long long)(vs ? kFirstWinVs : kFirstWinTournament) * kCent;
            g_store.won.insert(event_id);
        }
        // Anti-farm (ordinary points only). Tier 6 always pays in full.
        const int cur = g_store.top_tier;
        if (event_id == g_store.last_event) g_store.last_count++;
        else g_store.last_event = event_id, g_store.last_count = 1;
        if (tier < kFullTier) {
            if (tier <= cur - 2) farm_pct = 0, why = " (2+ tiers below)";
            else if (tier == cur - 1) farm_pct = kOneTierBelowPct, why = " (tier below)";
            const int n = g_store.last_count;
            const int rep = kRepeatPct[n - 1 < 3 ? n - 1 : 3];
            if (rep < 100) why = farm_pct < 100 ? " (tier below, repeat)" : " (repeat)";
            farm_pct = farm_pct * rep / 100;
        }
        raw = base;
        base = base * farm_pct / 100;
        // The reference tier: highest reached (played, or opened by a VS win).
        if (tier > g_store.top_tier) g_store.top_tier = tier;
        if (kind == Event::Vs && won && tier + 1 < kTiers && tier + 1 > g_store.top_tier)
            g_store.top_tier = tier + 1;
    }
    const long long add = (base + bonus) * rate_pct() / 100;
    g_store.cpoints += add;
    if (kind != Event::Test) g_award_serial = g_round_serial, g_last_add = add;
    const long long per = (long long)kPointsPerTicket * kCent;
    const int t = (int)(g_store.cpoints / per);
    g_store.cpoints -= t * per;
    g_store.tickets += t;
    g_store.earned += t;
    g_store.save();             // persist before drawing
    fprintf(stderr, "[hsg-unlocks] award: %s tier=%d event=%d holes=%d place=%d under_par=%d:"
            " ordinary %.2f x %d%%%s + bonus %.2f, rate %d%% -> +%.2f points, +%d ticket(s)"
            " (tickets %d, progress %.2f/%d)\n", kind_name(kind), tier, event_id, holes, placement,
            under_par, raw / (double)kCent, farm_pct, why,
            bonus / (double)kCent, rate_pct(), add / (double)kCent, t, g_store.tickets,
            g_store.cpoints / (double)kCent, kPointsPerTicket);
    {
        // Header first, before the draws: points added, tickets completed, progress.
        char tickets[48] = "";
        if (t > 0) snprintf(tickets, sizeof tickets, ", %d ticket%s", t, t == 1 ? "" : "s");
        char h[160];
        snprintf(h, sizeof h, "\x1bgGrind: +%.1f pts%s (next ticket %.1f/%d pts)",
                 add / (double)kCent, tickets, g_store.cpoints / (double)kCent, kPointsPerTicket);
        g_toast.insert(g_toast.begin(), std::string(h));
    }
    if (t > 0) { spend_tickets(ctx); apply(ctx); }
    if (t > 0 && g_store.tickets > 0)   // banked for the capsule machine (Shop, Triangle)
        toast("%d ticket%s banked " ARROW " Shop " TRIANGLE " Capsule Machine", g_store.tickets,
              g_store.tickets == 1 ? "" : "s");
    toast_flush(6500);
    return add;
}

// What the round-end hook reads (see the header).
struct RoundInfo {
    int mode = -1, tier = -1, slot = -1, kind = -1, label = -1, holes = -1;
    int place0 = -1, vs_outcome = -1, strokes = 0, par = 0, handicap = 0;
    uint32_t record = 0, result = 0;
};

RoundInfo read_round(ppu_context* ctx)
{
    RoundInfo r;
    const uint32_t gi = game_info();
    if (!gi) return r;
    r.mode = (int)vm_read32(gi + 0x394);
    r.tier = (int)(int8_t)vm_read8(gi + 0x379);
    r.slot = (int)(int8_t)vm_read8(gi + 0x37A);
    r.record = vm_read32(gi + 0x37C);
    r.holes = vm_read8(gi + 0x321);
    if (r.record) {
        r.label = vm_read16(r.record + 0x00);
        r.kind = vm_read8(r.record + 0x0A);
    }
    const uint32_t results = vm_read32(kResultsPtr);
    if (results) {
        GuestCall g(ctx);
        r.result = (uint32_t)g.call(func_006AE704, kTocGasha, results);
    }
    if (r.result) {
        r.place0 = vm_read16(r.result + 0x66);
        static const int test_place = env_int("HSG_UNLOCKS_TEST_PLACE", 0);
        if (test_place >= 1 && test_place <= 20 && r.place0 != test_place - 1) {
            fprintf(stderr, "[hsg-unlocks] test: placement %d -> %d\n", r.place0 + 1, test_place);
            r.place0 = test_place - 1;
            vm_write16(r.result + 0x66, (uint16_t)r.place0);
        }
        r.vs_outcome = (int)(int8_t)vm_read8(r.result + 0x6B);
        r.handicap = vm_read16(r.result + 0x26);
        r.strokes = (int)vm_read32(r.result + 0xD0 + 0x1C);
        r.par = (int)vm_read32(r.result + 0xD0 + 0x24);
    }
    return r;
}

void on_round_end(ppu_context* ctx)
{
    const RoundInfo r = read_round(ctx);
    const bool pays = mode_pays(r.mode);
    const int score = (int)(int16_t)(r.strokes - r.par - r.handicap);   // as prize +0x27C
    fprintf(stderr, "[hsg-unlocks] round over: mode %d tier %d slot %d record 0x%08X (kind %d"
            " label %d) holes %d result 0x%08X place0 %d vs %d strokes %d par %d handicap %d"
            " score %+d%s\n", r.mode, r.tier, r.slot, r.record, r.kind, r.label, r.holes, r.result,
            r.place0, r.vs_outcome, r.strokes, r.par, r.handicap, score, pays ? "" : ": no reward");
    if (!pays) return;
    if (r.tier < 0 || r.tier >= kTiers || r.slot < 0 || r.slot >= kSlots || !r.record) {
        fprintf(stderr, "[hsg-unlocks] round over: no Challenge event, no reward\n");
        return;
    }
    const int event_id = r.tier * kSlots + r.slot;
    if (r.kind == 0 || (r.kind < 0 && r.mode == 2)) {
        award_points(ctx, Event::Tournament, r.tier, r.holes, r.place0 + 1, -score, event_id);
    } else {
        const bool won = r.vs_outcome >= 0 && r.vs_outcome <= 2;   // as 0x003494E0
        award_points(ctx, r.kind == 1 ? Event::Vs : Event::Cosplay, r.tier, r.holes, won ? 1 : 2,
                     -score, event_id);
    }
}

// HSG_UNLOCKS_DEBUG: save-data words that change after a round ends (for tracing).
std::vector<uint8_t> g_snap;
unsigned g_tick = 0;
unsigned g_snap_tick = 0;
constexpr uint32_t kSnapSize = 0x110000;

void snap_take()
{
    const uint32_t save = vm_read32(kSavePtr);
    if (!save) return;
    g_snap.assign(((const uint8_t*)vm_base + save), ((const uint8_t*)vm_base + save) + kSnapSize);
}

void snap_diff(const char* when)
{
    const uint32_t save = vm_read32(kSavePtr);
    if (!save || g_snap.empty()) return;
    const uint8_t* now = ((const uint8_t*)vm_base + save);
    int n = 0;
    for (uint32_t o = 0; o < kSnapSize; o += 4) {
        if (memcmp(&g_snap[o], now + o, 4) == 0) continue;
        if (n++ < 120)
            fprintf(stderr, "[hsg-unlocks] diff %s save+0x%05X: %02X%02X%02X%02X -> %02X%02X%02X%02X\n",
                    when, o, g_snap[o], g_snap[o + 1], g_snap[o + 2], g_snap[o + 3],
                    now[o], now[o + 1], now[o + 2], now[o + 3]);
    }
    fprintf(stderr, "[hsg-unlocks] diff %s: %d words changed\n", when, n);
    g_snap.assign(now, now + kSnapSize);
}

// HSG_UNLOCKS_TEST_ONEHOLE=1: a Challenge round ends after its first hole. The round-over
// test 0x0068B488 is "round hole index (Game data +0xF8) >= game info +0x323".
void test_one_hole()
{
    static const bool on = env_int("HSG_UNLOCKS_TEST_ONEHOLE", 0) != 0;
    if (!on) return;
    const uint32_t gi = game_info();
    if (!gi) return;
    const int m = (int)vm_read32(gi + 0x394);
    if (m != 1 && m != 2) return;
    const int last = (int)(int8_t)vm_read8(gi + 0x323);
    if (last <= 0) return;
    fprintf(stderr, "[hsg-unlocks] test one hole: mode %d holes %d last-hole index %d -> 0\n", m,
            vm_read8(gi + 0x321), last);
    vm_write8(gi + 0x323, 0);
}

}  // namespace

// ---- store access for hsg_jp127_capsule.cpp (hsg_jp127_unlocks.h) ---------------------------
namespace hsg {
bool grind_mode() { return mode() == Mode::Grind; }
int store_tickets() { return g_store.tickets; }
void store_set_tickets(int n) { g_store.tickets = n < 0 ? 0 : n; g_store.save(); }
int store_rare(int pc) { return pc >= 0 && pc < kRareChars ? g_store.rare[pc] : 0; }
int store_gauge(int pc) { return pc >= 0 && pc < kRareChars ? g_store.gauge[pc] : 0; }
int store_pity() { return g_store.pity; }
bool store_tus(int slot, int64_t* v)
{
    const auto it = g_store.tus.find(slot);
    if (it == g_store.tus.end()) return false;
    *v = it->second;
    return true;
}
void store_set_tus(int slot, int64_t v) { if (slot >= 1 && slot <= 63) g_store.tus[slot] = v; }
void store_set_level(int pc, int level, int gauge)
{
    if (pc < 0 || pc >= kRareChars) return;
    g_store.rare[pc] = level < 0 ? 0 : level > kMaxStars ? kMaxStars : level;
    g_store.gauge[pc] = gauge < 0 ? 0 : gauge > kGaugeMax ? kGaugeMax : gauge;
}
void store_record_draw(int pc, int star, int lv0, int lv1, int g0, int g1, bool forced)
{
    record_draw(pc, star, lv0, lv1, g0, g1, forced);
}
void store_save() { g_store.save(); }
bool store_all_maxed() { return all_maxed(); }
bool store_roll(const int* levels, int pity, int* pc, int* star, bool* forced)
{
    return roll_capsule(levels, pity, pc, star, forced);
}
int pity_draws() { return kPityDraws; }
double star_odds(int star)
{
    const double tot = kOddsBlue + kOddsPurple + kOddsRed;
    if (star >= 1 && star <= 3) return kOddsBlue / tot / 3.0;
    if (star >= 4 && star <= 6) return kOddsPurple / tot / 3.0;
    return star == 7 ? kOddsRed / tot : 0.0;
}
bool round_award(long long* add_cents, int* tickets, long long* progress_cents, int* per_ticket)
{
    if (g_award_serial != g_round_serial || g_round_serial == 0) return false;
    *add_cents = g_last_add;
    *tickets = g_store.tickets;
    *progress_cents = g_store.cpoints;
    *per_ticket = kPointsPerTicket;
    return true;
}
bool overlay_enabled() { return overlay_on(); }
void toast_line(const char* utf8) { g_toast.push_back(utf8); }
void toast_post(int ms) { toast_flush(ms); }
}  // namespace hsg

void func_004452C8(ppu_context* ctx)
{
    func_004452C8_lifted(ctx);
    drain(ctx);
    const Mode m = mode();
    if (m == Mode::Original || !vm_base) return;
    if (m == Mode::Grind) hsg::capsule_tick(ctx);
    // While the machine is open the game writes the save's rare levels itself (result screen).
    if (g_tick++ % 30 == 0 && !(m == Mode::Grind && hsg::capsule_busy())) apply(ctx);
    if (m == Mode::Grind) test_one_hole();
    // Boot toast: the grind totals once the save is up.
    static bool boot_toast = false;
    if (m == Mode::Grind && !boot_toast && g_tick > 60 && vm_read32(kSavePtr)) {
        boot_toast = true;
        int stars = 0;
        for (int r : g_store.rare) stars += r;
        toast("\x1bgGrind: %d ticket%s earned so far, %d/%d stars", g_store.earned,
              g_store.earned == 1 ? "" : "s", stars, kRareChars * kMaxStars);
        if (g_store.tickets > 0) toast("%d ticket%s waiting", g_store.tickets,
                                       g_store.tickets == 1 ? "" : "s");
        toast_flush(4000);
    }
    // Test aid (HSG_UNLOCKS_TEST_AWARD=<points>, grind): one award ~10 s after boot, through
    // the same award_points() a finished round uses, to check draw/store/apply without
    // playing a whole round.
    static int test_award = env_int("HSG_UNLOCKS_TEST_AWARD", 0);
    if (test_award > 0 && m == Mode::Grind && g_tick > 300 && vm_read32(kSavePtr)) {
        g_test_points = test_award;
        fprintf(stderr, "[hsg-unlocks] test award (HSG_UNLOCKS_TEST_AWARD=%d)\n", test_award);
        test_award = 0;
        award_points(ctx, Event::Test, -1, -1, -1, -1, -1);
    }
    if (g_debug) {
        if (g_snap.empty()) snap_take();
        static int last = -2;
        const int gm = game_mode();
        if (gm != last) {
            const uint32_t gi = game_info();
            fprintf(stderr, "[hsg-unlocks] game mode %d -> %d (tier %d slot %d holes %d last %d)\n",
                    last, gm, gi ? (int)(int8_t)vm_read8(gi + 0x379) : -1,
                    gi ? (int)(int8_t)vm_read8(gi + 0x37A) : -1, gi ? vm_read8(gi + 0x321) : -1,
                    gi ? (int)(int8_t)vm_read8(gi + 0x323) : -1);
            last = gm;
        }
        static uint32_t money = 0xFFFFFFFF;
        const uint32_t base = money_base();
        if (base && vm_read32(base + kMoneyOff) != money) {
            money = vm_read32(base + kMoneyOff);
            fprintf(stderr, "[hsg-unlocks] shop point balance %u\n", money);
        }
        if (g_snap_tick && g_tick - g_snap_tick >= 600) {
            snap_diff("later");
            g_snap_tick = g_tick;
        }
    }
}

void func_00348384(ppu_context* ctx)
{
    func_00348384_lifted(ctx);
    drain(ctx);
    if (mode() != Mode::Grind || !vm_base) return;
    if (g_debug) { snap_diff("round-end"); g_snap_tick = g_tick; }
    g_round_serial++;
    on_round_end(ctx);
}
