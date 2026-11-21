# Course and hole data formats (Hot Shots Golf: World Invitational, PS3)

Format notes only: no game data is reproduced here. Findings come from static analysis of the 1.03
`EBOOT.elf` plus inspection of the disc files. Addresses are guest virtual addresses in that ELF.
Confidence tags: H high, M medium, L low.

## 1. Where the files live

All paths are relative to `USRDIR/`. `NN` is the course number (01 to 09), `HH` the hole number (01 to 18).

| Path | Content |
|---|---|
| `xbdata/courseinfo/courseinfo.xb` (and `courseinfo.<locale>.xb`) | FB archive of 6 tab-separated tables: course list, hole list (par, yardage, wind), time/weather, creature sounds, wind-angle weights, wind-speed weights |
| `xbdata/course_localize/courseNN/holeHH.xb` | FB archive for one hole: hole models, UV animation, an XML with cup/tee/tree/prop/structure positions, an effects XML, small 4-bit BMP masks, name lists |
| `xbdata/course_localize/courseNN/holeHH_hmp.xb` | FB archive with two height-map grids for the hole (see section 4) |
| `xbdata/course_localize/courseNN/holeHH_plant_v04.xb` | Vegetation placement for a hole (versioned file, see section 5) |
| `xbdata/course_localize/courseNN/entry.xb` | Course-wide model set (about 600 entries) |
| `.../entry_bg.xb`, `entry_structure.xb`, `entry_tex.xb`, `entry_envinfo.xb`, `courseeffect.xb`, `realcup.xb` | Sky/background models, structure models, textures (DDS), environment XML, effect scripts, real-tournament cup set |
| `data/course_localize/courseNN/...` | Loose files: `cup/cup.rem`, `lowcup_edge/lowcup_edge.rem`, `bg/courseNN_bg_{out,in}.rem`, `obpile/obpile.rem`, `rough/zassouNN.gxt`, `effect/effect_list.csv` |
| `data/course_localize/scorecard_camera/courseNN/camscore_MM_KK.scc` | Scorecard camera paths |
| `data/others/wind/Course_Wind{Angle,Speed}List.txt` | Names of the two wind tables inside courseinfo.xb (read from the archive, not from loose files) |
| `PSN/5555000108000009/course09.edat` + `course09.key` (DLC area) | License for course 09 |

The game opens each path with the formats `xbdata/course_localize/course%02d/hole%02d.xb` and so on
(strings at 0xC83118-0xC83A00 in the 1.03 ELF). Course 09 files are present under
`course_localize/course09`; the license, not the data, gates it (section 6).

## 2. The FB archive container (`.xb`) (H)

Little-endian on disk. The loader (`FB::Reader::Mount`, 0x778374) byte-swaps the header and entry
words on load.

```
0x00  4 bytes   magic "FB" 00 00   (loader masks the low byte, so only 'F','B',0 are checked)
0x04  u32       entry count N
0x08  u32       extra header bytes E (observed 4)
0x0C  E bytes   extra header (observed zero)
0x0C+E  N x 20-byte rows, sorted by name_hash (unsigned):
          u32 name_hash     see "Name hash" below
          u32 runtime_ptr   zero on disk; the loader adds the data base address here
          u32 ordinal       index of this name's payload (0..N-1, a permutation)
          u32 stored_size   bytes on disk of payload number <row index> (0 = empty)
          u32 raw_size      bytes after inflate of payload number <row index>
then the N payloads, back to back in row order, each starting on a 4-byte boundary (pad zeros)
```

Reading rule (`FB_FindEntryByPath`, 0x779228): hash the name, binary-search the rows for that hash
(found row r), then take the payload at row index `ordinal(r)`: its size fields and its data are
those of row `ordinal(r)`, not of row r. In short, the sorted rows are an index (hash -> payload
number) and the size fields describe payloads in payload order. Each payload is a zlib stream
(`78 DA`) that inflates to exactly `raw_size` bytes (true for every non-empty entry checked). An
empty payload (`stored_size` 0) is a zero-length file.

Name hash (H, verified): start with h = 0; for each byte c of the name, ASCII-lowercased,
`h = h * 31 + c` (32 bit). A name containing `.gxt` is hashed up to the `.gxt` and then as `.dds`
(the loader substitutes the DDS texture for a GXT request). Names are full relative paths
that begin with `data/`: for `xbdata/<dir>/<file>.xb` the key is `data/<dir>/<name inside the archive list>`,
for example `data/courseinfo/Course_CourseList.txt` inside `xbdata/courseinfo/courseinfo.xb` and
`data/course_localize/course01/hole/course01_h01.rem` inside `.../course01/hole01.xb`. Checked: all six
`courseinfo.xb` entries and all 438 names listed in the `holeHH.xb` name-list entries of the nine
courses resolve to a row (the `.xb` bytes themselves carry no names).

Because only hashes are stored, an entry that no code string names is identified by sniffing its
first bytes. `tools/fb_archive.py` (list/extract/hash, read-only) implements the rule above.

## 3. courseinfo.xb tables (H)

Six entries. All are UTF-8 (with BOM) tab-separated text with a header row, except the creature
list, which is Shift-JIS CSV. Loader: `CourseExt_LoadCourseInfo` 0x659d84 (course list, hole list),
`WindInfo_Load` 0x19D60C (wind tables), `Course_LoadPropTimeList` 0x64BB58 and
`Course_LoadCreatureSoundList` 0x64BE20.

| Entry name the game asks for | Columns |
|---|---|
| `data/courseinfo/Course_CourseList.txt` | `Label` (`Course_000`..`Course_020`), `Get`, `Secret`, `No`, `Regular`, `Long`, `Rate_R`, `Rate_L`, `Trophy`, `Patch` (the locale variant adds `Get_PS3`, `Secret_PS3`, `Trophy_PS3`, `Patch_PS3`; the game reads the `_PS3` columns) |
| `data/courseinfo/Course_HoleList.txt` | `Label` (`CourseNNN_HHH`, 18 rows per course, rows for course 000 are placeholders), `Par`, `R_Lim`, `L_Lim`, `R_H.C.`, `L_H.C.`, `R_Yard`, `L_Yard`, `R_WindSpeed`, `L_WindSpeed`, `R_WindAngle`, `L_WindAngle`, `L_Rand` |
| `data/courseinfo/time_weather/TimeWeather_TimeWeather.txt` | per-course creature/prop appearance: course, file, sound, start/finish time labels, fine/cloudy/rain flags |
| `CreatureSound_CreatureSoundList.txt` | course number, file name, start/end time (600 = 6:00), weather flags |
| `Course_WindAngleList.txt` | `Label` `WindAngle_000`.., then 12 weights for directions 0, 30, ... 330 degrees |
| `Course_WindSpeedList.txt` | `Label` `WindSpeed_000`.., then 10 weights for 0 m ... 9 m (rows sum to 100) |

Meaning: `R` columns are the regular tee, `L` the long (back) tee. `R_Yard`/`L_Yard` hold the hole length
(the debug overlay prints it with a `Y.` suffix, so yards). `R_WindSpeed` etc. hold a label such as
`WindSpeed_022`; the loader keeps only the last two digits as a row index (M). `L_Rand` (default 15)
is an extra random wind term for the long tee (L).

Course rows: 21 records (course 0 to 20); only courses 1 to 9 have real data and files.
`Get`/`Secret`/`Patch`: unlock conditions; `Patch` is compared with the game's PatchRevision minus 10
(M). `Trophy` marks courses counted by a trophy (M).

## 4. Hole files

### 4.1 `holeHH.xb` (H for container and XML, M for the rest)

Contents (identify by sniffing):

- Name list (text, 2 to 4 lines): e.g. `hole/courseNN_hHH.rem`, `.uva`, `_mg.rem` (model, UV animation, minigame/low-LOD model).
  These are the names the game asks for; each is hashed as `data/course_localize/courseNN/<name>` (section 2).
- Large entries starting `00 00 00 01` followed by `7f 7f ff ff` x3 (FLT_MAX) are big-endian model
  files (`.rem`) in the engine's native format, bounding data first; one is the hole terrain mesh, one
  is the green/surround mesh. Not parsed here.
- Main XML (`<?xml ...?><CourseResource>`, 100 KB+): see below.
- Effect XML (`<CourseResource><Course><effect>`): placed `.ef` effect files (water fall, test effects).
- 16 to 27 small 4-bit BMP files (32x32, 64x64, 128x128 and 256x256 and one 128x64) with 0 to 3 colors. The
  engine has a fixed per-course list of mask names ending in `_attr.bmp` (for example `yogoshi_hNN_attr.bmp`,
  `semirough.bmp`, `fairway.bmp`, `bunker00.bmp`, `green.bmp`, `greenedge00_attr.bmp`, `mask_hNN_attr.bmp`,
  `tc_yogore_c2h02_mask_attr.bmp`); on disc they are keyed as `data/course_localize/courseNN/hole/<name>`
  (course-wide ones such as `semirough.bmp`, `fairway.bmp`, `bunker00.bmp`, `green.bmp`, `greencol.bmp` as
  `data/course_localize/attribute/<name>`, so those hashes are shared by every hole archive). Role (M):
  ground-surface blend/paint masks for the ground renderer (`ground.cpp`, a 0x440-byte object that is handed the
  name list through `0x6A2DC0` / `0x6A64D4`); they are NOT what the game reads for lie or surface lookups, which
  use the attribute plane of the height map (4.2).
- A small binary material-name table (about 180 bytes, names like `c01material:...`).

Main XML structure (`CourseResource`):

```
<CourseResource>
  <HmpVersion id="1210031857"/>          matches the 10-byte trailer in holeHH_hmp.xb
  <Course id="1">
    <cup>  <Unit id=n><pos>x y z</pos><height_ofs>h</height_ofs></Unit> ...   hole positions, 8 per hole
    <tee>  <Unit ...> (always 2: first = regular tee, second = long tee)
    <tree> <Unit id=n><pos/><height_ofs/><rotscaleX/Y/Z/>(3x3 matrix rows)<model_name>x.rem</model_name><group_no/>
    <prop> <structure> <creature> (adds <linkindex>)  <env_se> (model_name = sound zone name, e.g. waterfall, pond)
    <m_point> <t_point> <c_point> <g_point>   guide point lists (camera/route points; g_point = green)
    <tarea>  (pos, height, radius, group_no: trigger areas)
    <obzone> <roughzone> <d_point> <w_point> <effect> <part_wind>   other kinds known to the parser
```

Group names map to a kind number in `CourseRes_KindFromName` (0x65AB14): cup 0, tee 1, tree 2, prop 3,
structure 4, m_point 5, t_point 6, c_point 7, d_point 8, g_point 9, w_point 10, obzone 11, roughzone 12,
tarea 13, creature 14, env_se 15, effect 16, part_wind 17 (H). Coordinates are floats in world units
(the same space as the height map). All 162 hole files of the nine courses have exactly 8 `cup` units and 2 `tee`
units. Only the first 5 cups are ever picked at random for the pin (section 6.4). The `y` of a unit is the terrain
height at (x, z) plus its `height_ofs`: for all 316 tee units `y - height_ofs` equals the height-map value to within
0.1 (tee `height_ofs` is often non-zero, for example -2.46); for cups `height_ofs` is about 0 and `y` is the terrain
height (96% within 0.1, the rest within a few tenths on sloped cells). `tee` unit ids are small integers shared with
`m_point`/`t_point` ids (M). Par and yardage are NOT in the hole file; they come from courseinfo.xb.

Out-of-bounds and hazards: the parser knows `obzone` and `roughzone` kinds and the loader reads
`obpile/obpile.rem` and `rough/zassou*.gxt`. In the sample holes no `obzone`/`roughzone` units were present, so OB and
rough regions are likely encoded in the surface attribute plane of the height map (4.2) and the BMP masks (M/L).

In memory each unit is a 0x84-byte element (`CourseRes_GetElement` 0x65A870: element address =
table begin pointer + index*0x84; table at `*(Course+0)+0x30+16*kind`, begin at +4, end at +8). The XML
parser (`CourseResXml_ParseUnitFields` 0x66D334) builds the element on the 0x70-byte unit class with vtable
0xD2C250 (H): `+0x20..+0x5F` is a 4x4 float matrix (rows 0..2 from `rotscaleX/Y/Z`, row 3 = position), so
**`pos` x, y, z are floats at element +0x50, +0x54, +0x58** (w = 1 at +0x5C); `height_ofs` is the float at
**+0x60**; `tarea` `height` is at +0x68 and `radius` at +0x6C; `group_no` is at +0x70 and a pointer to the loaded
model (set by the later object build) near +0x44/+0x74 of the in-memory element. Evidence: vtable slot 4
(`0xB92738`, copies a matrix to +0x20) is what the parser calls with the matrix it built from the XML; slot 7
(`0xB927C8`) stores `height_ofs` at +0x60.

### 4.2 `holeHH_hmp.xb` (H)

Two entries, found by name: `data/course_localize/courseNN/hole/courseNN_hHH.hmp` (coarse, whole hole) and
`.../courseNN_hHH_g.hmp` (fine, around the green). Both inflate to the same grid layout (little-endian):

```
+0x00 f32 origin_x
+0x04 f32 origin_z
+0x08 u32 width  (cell count along x)
+0x0C u32 height (cell count along z)
+0x10 f32[width*height]   terrain height (world Y) per cell
      u8 [width*height]   surface attribute id per cell
      10 ASCII bytes      HmpVersion string (e.g. "1210031857", equals the XML HmpVersion id)
```

Total size is `16 + 5*width*height + 10`. Cell spacing is not stored in the file; the engine constructs the
grid objects with constants (`Hmp_InitDefaults` 0x6A20EC, `Ground_SetDefaultCellSizesAndBuild` 0x6A5EA4):
**1.3 world units for the coarse grid and 0.13 for the fine grid** (inverses 0.7692 and 7.692).

World mapping (H, verified against disc data): a point (x, z) falls in cell
`ix = trunc((x - origin_x) / spacing)`, `iz = trunc((z - origin_z) / spacing)`, and the arrays are stored
**x-major**: element index = `ix * height + iz` (`height` = cell count along z). `origin_x`/`origin_z` is the world
position of cell (0,0). The attribute lookup `Hmp_GetAttributeAt` (0x6A3E58) uses the fine grid when the point
is inside it, else the coarse one, and rounds to the nearest cell. Check: using bilinear interpolation of the
height plane (spacing 1.3 coarse / 0.13 fine, the fine grid first), 316 of 316 tee positions satisfy
`tee.y - height_ofs = terrain` and 1208 of 1264 cup positions are within 0.1 of terrain over all 162 holes;
differences on the last few are slope effects. Attribute value 6 covers about 84% of the sample green grid
(green). Attribute ids seen: 0, 1, 2, 3, 5, 6, 7, 8, 11, 12, 22, 27, 46 (names not resolved).

## 5. Versioned files (H)

The hole loaders try patch-variant file names before the base name (`Course_OpenHoleFile` 0x645088,
`Course_OpenHoleHmpFile` 0x644F58, `Course_OpenHolePlantFile` 0x6451B8). With `count` from
`Game_GetHoleFileVersionCount` (5 by default), they try `..._v05`, `_v04`, `_v03`, then the plain
name, and stop at the first that exists. This is why `hole01_plant_v04.xb` exists on disc.

## 6. In-memory structures (1.03 ELF)

### 6.1 CourseInfo records (H for the loader order, M for per-field use)

`*(0x185C4B4)` points to 21 records of 0x42C bytes (index = course number 0..20). Fields (offset
from record start):

| Off | Field | Source column |
|---|---|---|
| +0x08 | course number | `No` |
| +0x0C | hole count (constant 18) | |
| +0x10 | regular value | `Regular` |
| +0x14 | long value | `Long` |
| +0x18 / +0x1C | float rate | `Rate_R` / `Rate_L` |
| +0x20 | name string `courseNN` | built with sprintf |
| +0x60 | Get_PS3 (s32) | |
| +0x64 | Secret_PS3 | |
| +0x68 | Trophy_PS3 | |
| +0x6C | Patch_PS3 | |
| +0x70 | DLC-locked flag (u8; 1 for course 9) | from `Dlc_IsBaseCourse` |
| +0x74 + 0x30*h | 0x30-byte hole record for hole h (1..18; slot 0 and 19 spare) | HoleList |

Hole record (pointer returned by `CourseExt_GetHoleInfo` 0x65978C, 12 words):

| Off | Field |
|---|---|
| +0x00 | par (0 in the table becomes 4 by default) |
| +0x04 / +0x08 | `R_Lim` / `L_Lim` |
| +0x0C / +0x10 | `R_H.C.` / `L_H.C.` |
| +0x14 / +0x18 | `R_Yard` / `L_Yard` (yardage) |
| +0x1C / +0x20 | wind speed row index, regular / long tee |
| +0x24 / +0x28 | wind angle row index, regular / long tee |
| +0x2C | `L_Rand` |

Par at +0 is confirmed by 44 of 60 callers of the current-hole getter. The wind offsets are confirmed
by `WindInfo_SelectHoleWinds` (0x19CE4C). The loader (`CourseExt_LoadCourseInfo` 0x659D84, hole loop at
0x65A32C) reads CSV columns 1..3 into +0/+4/+8, columns 4 and 5 into +0xC/+0x10, columns 6 and 7
(`R_Yard`, `L_Yard`) as plain integers into +0x14/+0x18, columns 8..11 as wind labels into +0x1C/+0x20 and
+0x24/+0x28, column 12 into +0x2C (H for the store offsets). No HUD consumer of +0x14/+0x18 was found by static
reading (the yardage the player sees may be computed from positions). In the disc data `R_Yard` equals `L_Yard`
for the holes checked, and the straight distance tee to cup is a little less than the table yardage (for
example 322 yd measured against 327 in the table for course 1 hole 1), so the table value looks like the
designed hole length (guide-line length) rather than a tee-specific number.

Current course and hole come from `Game` (`*(0x185E878)`): `*(Game+0x5C)+0xE8` course number
(`Game_GetCourseNo` 0x67C008), `+0xEC` hole number (0x67C028), `+0xF8` zero-based hole counter in the
round (0x67C038). `*(0x185EEE0)` (round setup) holds `+0x394` game mode, `+0x398` hole count,
`+0x310` hole-order helper. The next hole is preloaded on a worker thread
(`ThreadLoad_NextHole`, 0x645430 / entry 0x645310).

### 6.2 Course resource table (M)

`*(0x185C4B8)` is the Course object; `*(Course+0)` is the resource table: one vector triple per kind at
`+0x30 + 16*kind` (begin at +4, end at +8), 0x84-byte elements; per-hole vectors at `+0x160 + 16*h`.
Cup, tee and other positions from the hole XML are loaded into these vectors by
`Course_LoadCourseResources` (0x650900) and `CourseResXml_Load` (0x66C818).

Course object fields (course.cpp, 0x490 bytes; H unless noted): `+0x180` current tee, `+0x190` current pin,
`+0x1A0` tee list, `+0x1C0` cup list (up to 10), `+0x260` tee index, `+0x264` pin index, `+0x268` per-hole pin
array (18 entries, M), `+0x2B0` tee count, `+0x2B4` cup count, `+0x2B8` guide length, `+0x420` random number
generator object.

### 6.4 Tee and pin selection (M)

- Tee: `Course_SetTee` (0x645790) takes an index (0 = regular tee, 1 = long tee), copies the matching tee unit
  into +0x180 and stores the index at +0x260 and in the round setup byte `+0x31C`. The index comes from bit 7
  of the hole-order entry (`HoleOrder` object at round setup +0x310, entry +0x28+i = course number | tee flag
  in bit 7). When the index is 1 the tee x is negated (the reason is not understood, L).
- Pin: `Course_RandomizePin` (0x64E100) draws from the course RNG over cups 0 to min(count, 5) - 1, skipping the
  current pin, and calls `Course_SetPin` (0x64D9B8), which sets +0x190 and +0x264 and mirrors the index into
  round setup byte `+0x34C`. `Course_LoadCourseResources` pre-rolls a `rand % 5` per hole into the array at
  +0x268. Cups 5 to 7 are never chosen by this path.
- Not found: any difficulty or tournament condition on pin choice.

### 6.3 Save data (M)

`SaveData+0x11B40`: 21 course records of 0x41 bytes (`SaveCourse_GetRecord` 0x30CBC). Byte 0 is the
course state; values 3 and 4 count as cleared/owned. Per-hole best scores are elsewhere
(`SaveData+0x12180 + course*0x1BA0 + ...`, 0x644E9C).

## 7. Course enumeration and the DLC gate (M)

- The list of courses is the 21 CourseInfo records. Courses 1 to 9 have disc data. Course select
  (`CourseSelect_Init` 0x39DE98, UI files `xbdata/menu/phase/course_sel/course_sel.xb`,
  `data/menu/phase/course_sel/layout_course_*.lay`) fills slots named `icon%d`, `short_icon`, `new%d`,
  `waku%d`, and asks `CourseSelect_IsCourseSelectable` (0x39C4A4) per course.
- The DLC flag comes from `Dlc_QueryCourse` (0x6E1878): only index 9 depends on a license
  (`course09.key` under content id 5555000108000009, table 0xDB55E8 entry 0). Result is cached
  in the DLC state object at `*(0x185FB80)` (byte `+1`), filled once by `Dlc_InitCategories`
  (0x6E1C78), which calls `Drm_IsContentAvailable` (0x7E6BD4) for all 91 table entries. Forcing
  0x7E6BD4 to return true therefore unlocks course 9 (and every other DLC item).
- Start-up count: after loading, `CourseExt_LoadCourseInfo` also tallies courses with a trophy flag
  and courses whose `Patch_PS3` is at or below the patch revision minus 10.
