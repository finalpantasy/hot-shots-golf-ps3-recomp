/*
 * ps3recomp game project -- game-specific hooks and overrides.
 *
 * main.cpp is the runner and is game-agnostic. This file is where a port puts
 * everything that is not: the PRX loading hook it must answer, overrides for
 * firmware functions the HLE library gets wrong for this title, and patches
 * over recompiled code.
 *
 * It starts out as the empty version of all of that, which is what a game with
 * no lifted PRX and no overrides needs.
 */

#include <cstdio>
#include <cstring>

#define PPU_NO_INLINE_LOADS
#include "ppu_recomp.h"
#include "ps3emu/nid.h"
#include "ps3emu/ps3types.h"
#include "ps3emu/error_codes.h"
#include "../external/ps3recomp/libs/font/cellFont.h"
#include "../external/ps3recomp/libs/font/cellFontFT.h"
#include "../external/ps3recomp/libs/network/cellHttp.h"
#include "../external/ps3recomp/libs/network/sceNp.h"
#include "../external/ps3recomp/libs/network/sysNet.h"
#include "../external/ps3recomp/libs/system/cellRtc.h"
#include "win32_compat.h"
#include "../external/ps3recomp/libs/hardware/cellGem.h"

extern "C" {
extern u8* vm_base;
void ps3_hle_register(u32 nid, const char* name, void* function);
void ps3_hle_register_ctx(u32 nid, const char* name, void (*function)(ppu_context*));
u32 vm_read32(u64 address);
s32 cellCameraGetBufferInfoEx(s32 device, void* info);
s32 cellGemGetImageState(u32 controller, void* state);
s32 cellGemPrepareCamera(s32 exposure, float quality);
s32 sceNpCustomMenuRegisterActions(const void* menu, u32 handler, u32 userArg, u64 options);
s32 sceNpCustomMenuActionSetActivation(const void* activation, u64 options);
s32 sys_crash_dump_set_user_log_area(u8 index, const void* info);
s32 sys_crash_dump_get_user_log_area(u8 index, void* info);
}

template <typename T>
static T* guest_arg(const ppu_context* ctx, unsigned reg)
{
    return reinterpret_cast<T*>(static_cast<uintptr_t>(static_cast<u32>(ctx->gpr[reg])));
}

static bool rtc_tick_accessible(u32 address, DWORD accepted_protections)
{
    if (!vm_base || !address || address > UINT32_MAX - (sizeof(CellRtcTick) - 1))
        return false;

    uintptr_t cursor = reinterpret_cast<uintptr_t>(vm_base) + address;
    const uintptr_t end = cursor + sizeof(CellRtcTick);
    while (cursor < end) {
        MEMORY_BASIC_INFORMATION page{};
        if (!VirtualQuery(reinterpret_cast<const void*>(cursor), &page, sizeof(page)) ||
            page.State != MEM_COMMIT || (page.Protect & PAGE_GUARD) || !(page.Protect & accepted_protections))
            return false;
        cursor = reinterpret_cast<uintptr_t>(page.BaseAddress) + page.RegionSize;
    }
    return true;
}

static void hle_rtc_tick_add_weeks(ppu_context* ctx)
{
    constexpr DWORD writable = PAGE_READWRITE | PAGE_WRITECOPY | PAGE_EXECUTE_READWRITE | PAGE_EXECUTE_WRITECOPY;
    constexpr DWORD readable = writable | PAGE_READONLY | PAGE_EXECUTE_READ;
    constexpr s32 invalid_pointer = static_cast<s32>(0x80010602u);
    if (!rtc_tick_accessible(static_cast<u32>(ctx->gpr[3]), writable) ||
        !rtc_tick_accessible(static_cast<u32>(ctx->gpr[4]), readable)) {
        ctx->gpr[3] = static_cast<u64>(static_cast<s64>(invalid_pointer));
        return;
    }

    constexpr u64 microseconds_per_week = 7ull * 24 * 60 * 60 * 1000000;
    const auto weeks = static_cast<s32>(ctx->gpr[5]);
    const u64 delta = static_cast<u64>(weeks) * microseconds_per_week;
    const s32 result = cellRtcTickAddMicroseconds(guest_arg<CellRtcTick>(ctx, 3), guest_arg<const CellRtcTick>(ctx, 4),
                                                static_cast<s64>(delta));
    ctx->gpr[3] = static_cast<u64>(static_cast<s64>(result));
}


extern "C" void ps3_register_peripheral_imports(void)
{
#define REGISTER(name) ps3_hle_register(ps3_compute_nid(#name), #name, reinterpret_cast<void*>(name))
#define REGISTER_CONTEXT(name, ...) ps3_hle_register_ctx(ps3_compute_nid(#name), #name, __VA_ARGS__)
    REGISTER(cellHttpClientSetSslCallback);
    REGISTER(cellHttpClientSetRecvTimeout);
    REGISTER(cellHttpClientSetSendTimeout);
    REGISTER(cellHttpClientSetUserAgent);
    REGISTER(cellHttpClientSetConnTimeout);
    REGISTER(cellHttpInitCookie);
    REGISTER(cellHttpEndCookie);
    REGISTER(cellHttpTransactionAbortConnection);
    REGISTER(cellHttpRequestSetContentLength);
    REGISTER(cellHttpRequestAddHeader);
    REGISTER(sceNpCustomMenuRegisterActions);
    REGISTER(sceNpCustomMenuActionSetActivation);
    REGISTER(sceNpBasicAddPlayersHistory);
    REGISTER(sceNpBasicGetBlockListEntry);
    REGISTER(sceNpProfileCallGui);
    REGISTER(sceNpProfileAbortGui);
    REGISTER(sceNpFriendlist);
    REGISTER(sceNpFriendlistAbortGui);
    REGISTER(sceNpManagerGetEntitlementById);
    REGISTER(sceNpScoreGetBoardInfo);
    REGISTER(cellFontEndLibrary);
    REGISTER(cellFontInitLibraryFreeTypeWithRevision);
    REGISTER(cellGemGetImageState);
    REGISTER(cellGemGetTrackerHue);
    REGISTER(cellGemConvertVideoFinish);
    REGISTER(cellGemConvertVideoStart);
    REGISTER(cellGemPrepareVideoConvert);
    REGISTER(cellGemSetRumble);
    REGISTER(cellGemInvalidateCalibration);
    REGISTER(cellCameraGetBufferInfoEx);
    REGISTER(sys_crash_dump_set_user_log_area);
    REGISTER(sys_crash_dump_get_user_log_area);

    REGISTER_CONTEXT(cellRtcTickAddWeeks, hle_rtc_tick_add_weeks);

    /* Address conversion works with the offline socket backend. */
    REGISTER_CONTEXT(inet_aton, [](ppu_context* ctx) {
        ctx->gpr[3] = sys_net_bnet_inet_aton(guest_arg<const char>(ctx, 3), guest_arg<u32>(ctx, 4));
    });
    REGISTER_CONTEXT(cellFontRenderSurfaceInit, [](ppu_context* ctx) {
        cellFontRenderSurfaceInit(guest_arg<CellFontRenderSurface>(ctx, 3), guest_arg<void>(ctx, 4),
                                  static_cast<s32>(ctx->gpr[5]), static_cast<s32>(ctx->gpr[6]),
                                  static_cast<s32>(ctx->gpr[7]), static_cast<s32>(ctx->gpr[8]));
    });
    REGISTER_CONTEXT(cellGemPrepareCamera, [](ppu_context* ctx) {
        ctx->gpr[3] = cellGemPrepareCamera(static_cast<s32>(ctx->gpr[3]), ctx->fpr[1]);
    });
    REGISTER_CONTEXT(cellGemForceRGB, [](ppu_context* ctx) {
        ctx->gpr[3] = cellGemForceRGB(static_cast<u32>(ctx->gpr[3]),
                                       ctx->fpr[1], ctx->fpr[2], ctx->fpr[3]);
    });

    // The generic HLE adapter only passes integer registers. Float parameters
    // arrive in f1/f2 and still occupy their argument positions in the GPR list.
    REGISTER_CONTEXT(cellFontSetScalePixel, [](ppu_context* ctx) {
        ctx->gpr[3] = cellFontSetScalePixel(guest_arg<CellFont>(ctx, 3), ctx->fpr[1], ctx->fpr[2]);
    });
    REGISTER_CONTEXT(cellFontSetupRenderScalePixel, [](ppu_context* ctx) {
        ctx->gpr[3] = cellFontSetupRenderScalePixel(guest_arg<CellFont>(ctx, 3), ctx->fpr[1], ctx->fpr[2]);
    });
    REGISTER_CONTEXT(cellFontSetEffectWeight, [](ppu_context* ctx) {
        ctx->gpr[3] = cellFontSetEffectWeight(guest_arg<CellFont>(ctx, 3), ctx->fpr[1]);
    });
    REGISTER_CONTEXT(cellFontRenderCharGlyphImage, [](ppu_context* ctx) {
        ctx->gpr[3] = cellFontRenderCharGlyphImage(
            guest_arg<CellFont>(ctx, 3), static_cast<u32>(ctx->gpr[4]),
            guest_arg<CellFontRenderSurface>(ctx, 5), ctx->fpr[1], ctx->fpr[2],
            guest_arg<CellFontGlyphMetrics>(ctx, 8), guest_arg<CellFontGlyphImage>(ctx, 9));
    });
    REGISTER_CONTEXT(cellFontCreateRenderer, [](ppu_context* ctx) {
        ctx->gpr[3] = cellFontCreateRenderer(static_cast<u32>(ctx->gpr[3]),
                                            guest_arg<const void>(ctx, 4),
                                            guest_arg<CellFontRenderer>(ctx, 5));
    });
    REGISTER_CONTEXT(cellFontDestroyRenderer, [](ppu_context* ctx) {
        u32 renderer = static_cast<u32>(ctx->gpr[3]);
        ctx->gpr[3] = renderer ? cellFontDestroyRenderer(vm_read32(renderer))
                               : CELL_FONT_ERROR_INVALID_PARAMETER;
    });
    REGISTER_CONTEXT(cellFontBindRenderer, [](ppu_context* ctx) {
        u32 renderer = static_cast<u32>(ctx->gpr[4]);
        ctx->gpr[3] = renderer ? cellFontBindRenderer(guest_arg<CellFont>(ctx, 3), vm_read32(renderer))
                               : CELL_FONT_ERROR_INVALID_PARAMETER;
    });
#undef REGISTER_CONTEXT
#undef REGISTER
}

/* ---------------------------------------------------------------------------
 * PRX loading
 *
 * main.cpp calls this once, after the lifted function table is registered and
 * vm_base is live, before the game runs. A title that lifts a real system PRX
 * -- libsre, which is cellSpurs and cellSync -- loads its image into guest RAM
 * here and registers its exports. Most ports never need to: the HLE library
 * answers those modules instead.
 * -----------------------------------------------------------------------*/

extern "C" void ps3_load_prx_modules(void)
{
}

/* ---------------------------------------------------------------------------
 * Example: Override a specific NID
 *
 * The module system resolves function imports by NID.  To replace a default
 * HLE stub with custom logic, register your function at init time.
 * -----------------------------------------------------------------------*/

/*
 * Example: override cellGcmSetFlipMode (NID 0xA53D12AE) to force vsync.
 *
 *   static void my_cellGcmSetFlipMode(u32 mode)
 *   {
 *       printf("[hook] cellGcmSetFlipMode: forcing VSYNC (was %u)\n", mode);
 *       // Force vsync regardless of what the game requested
 *       cellGcmSetFlipMode(CELL_GCM_DISPLAY_VSYNC);
 *   }
 *
 * Then in your init code:
 *
 *   ps3::modules::override_nid(0xA53D12AE,
 *       reinterpret_cast<void*>(my_cellGcmSetFlipMode));
 */

/* ---------------------------------------------------------------------------
 * Example: Hook into module loading
 *
 * You can intercept cellSysmoduleLoadModule to perform custom actions
 * when a particular module is loaded.
 * -----------------------------------------------------------------------*/

/*
 *   static s32 my_loadmodule_hook(u16 id)
 *   {
 *       printf("[hook] Module 0x%04X loaded\n", id);
 *
 *       if (id == CELL_SYSMODULE_AUDIO) {
 *           // Perform custom audio backend initialization
 *           init_my_audio_backend();
 *       }
 *
 *       // Call the original implementation
 *       return cellSysmoduleLoadModule(id);
 *   }
 */

/* ---------------------------------------------------------------------------
 * Game-specific patches
 *
 * Sometimes you need to patch recompiled code at specific addresses.
 * Use the patch system to modify behavior without editing generated code.
 * -----------------------------------------------------------------------*/

/*
 *   // Skip an integrity check at guest address 0x00812FA0
 *   ps3::patches::nop_range(0x00812FA0, 0x00812FB0);
 *
 *   // Replace a function call with a direct return
 *   ps3::patches::force_return(0x009A1000, 0);  // return 0
 */
