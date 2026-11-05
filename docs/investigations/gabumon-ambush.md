# Gabumon ambush investigation

The reported stop follows screen 45's third Gabumon line,
`s045.sec7.u0` ("W-wait a second!" / "¡E-espera un momento!").
The report describes three Gabumon and Kotemon on the screen in v0.0.4.
No matching player save or state was available for this investigation.
The approximately 60 earlier unsuccessful reproduction attempts were reported
with the task; their individual results are not counted as new measurements.

## Confirmed rendering fault

A diagnostic v0.0.5 four-NPC WarGreymon encounter with QUICK BATTLES on
trapped in the interpreter at `AddPrim` (`0x8009290c`), with an unaligned
ordering-table pointer `0x0010fe9f`. This is a game memory-corruption result,
not merely a host recompiler failure. The model allocator remained intact:
37,184 bytes free, largest block 35,888 bytes.

A write breakpoint on `GS_ORDERING_TABLE` caught the first overwrite at
`BTL_renderBattleStartText + 0x3bc` (`0x800622d4`). The instruction bytes
match the loaded BTL overlay; they are not stale MENU instructions.
The packet cursor at banner entry was `0x801b4f3c`, 66,488 bytes into the
second 81,920-byte framebuffer work area (`0x801a4b84`). Only 15,432 bytes
remained. Gathering 155 banner pieces can emit two 40-byte textured quads
and one 24-byte shadow each: **16,120 bytes**. The observed final cursor
was `0x801b9080`, 1,276 bytes past the packet area. Draw packets overwrote
the offsets and ordering tables immediately after it; `GsSortClear` then
passed the damaged pointer to `AddPrim`.

Main also fails in both RAM modes in a forced-Kotemon, Minotarumon,
QUICK BATTLES on, recruited case. The exact 8 MB pre-battle state traps
in the interpreter at `GsSortSprite` (`0x80094ffc`), with the cursor
82,628 bytes into the 81,920-byte area. A separate write watch catches
`BTL_renderBattleStartText + 0x464` (`0x80062450`) overwriting the ordering
table. Its banner-entry cursor has already used 65,832 bytes: only 16,088
remain, **32 bytes less** than the complete banner needs. Later UI drawing
then encounters the damaged table. Small visibility/pose differences can
therefore make one setup fit and another overrun. The last completed
frames alone did not reveal this failing frame: the completed-frame
monitor saw a peak of 81,584 bytes before the mid-frame exception.

The [C patch](../../mods/patches/Bound-the-battle-start-banner-to-its-GPU-packet-budget.patch)
gives the normal-battle banner a reserved object ID and
defers its callback until all other scene/HUD objects have rendered. It
rechecks that the object still exists before calling it. Tournament and VS
banner IDs keep their existing dispatch. Both gathering and burst phases
then budget against the current framebuffer's existing packet area. It preserves letters before shadows
and trails, and leaves 4 KB for final frame commands. If even the
letters do not fit, animation still advances without linking packets.
The burst uses a stack temporary for projection/culling in that fallback,
so it can still finish. It adds no resident buffers and does not enlarge
the model heap. This bounds this banner's contribution, not every renderer
in the engine.

This reproduces a concrete memory fault after the reported line in the
older four-NPC layout. Without the original save or partner details, it
does not prove that the original v0.0.4 report had this exact cause.

## Scene and battle setup

The authored base script's section 7 says the line and calls `fight()`.
It has no extra movement, turn, model load, or overlay-specific helper between
the dialogue and the battle opcode. The opcode calls resident `startBattle`,
which calls resident `handleBattleStart` and `loadBattleData`, then
`BTL_battleMain` in the battle overlay.

`handleBattleStart` caps opponents at three. In the reported layout, Kotemon
is a fourth NPC, rather than a fourth battle opponent. On current main,
conversation NPCs are excluded from incidental fights. The v0.0.5 loader
does not have that exclusion: in a diagnostic four-NPC run its selected
fighters were `[1, 4, 2, 5]` (partner, third Gabumon, first Gabumon,
Kotemon). Another Gabumon was outside the selection rather than joining.
Kotemon can therefore fight or become a departing bystander, depending
on the version and the selection. With QUICK BATTLES off, the intro waits for the bystanders to leave the
screen. With it on, they depart while the battle runs, with a bounded wait
in `modBattleFleeTick`. This gives a plausible wait to inspect, but source
inspection alone does not establish the reported cause.

In the v0.0.4 source Kotemon is conditional only on not being recruited.
Commit `0fba9bec` subsequently made it conditional on
`ogre_fortress_cleared`, while the native Gabumon spawn before that flag.
Both the v0.0.5 tag and the investigated main baseline contain this
separation. Recruiting Kotemon changes its later availability, but does not
put it back into the shipped ambush. The fourth NPC must therefore be
reintroduced explicitly to investigate the older layout.

## Model heap

The three Gabumon share one loaded model slot; they do not allocate three
copies of the same model. Kotemon adds an 89,144-byte model plus 5,248 bytes
of pose/momentum data, reducing free heap by 94,392 bytes. In the loaded
Agumon scene, v0.0.5 has 131,576 bytes free normally and 37,184 with the
fourth NPC. Main has 128,600 and 34,208 bytes respectively. The 8 MB
configuration has the same model-heap totals and scene costs.

Main's baseline `main_BSS_END` is `0x801ceb00`; heap initialization starts
at `0x801ceb10` and leaves 185,328 bytes. v0.0.5 has `main_BSS_END`
`0x801cdf64`, heap base `0x801cdf70`, and 188,304 bytes. Main's full build
passes `heapcheck` and all 320 archive-based screen setups; the tightest
archive-based margin is 608 bytes on screen 207. The diagnostic four-NPC
warehouse is measured at runtime because its forced overlap is not an
authored current setup.

## Overlay lifetime audit

The rebirth failure fixed in PR #194 involved `getSpeciesVanillaAs` in
MENU_REL being called from DOOA after battle or evolution had overwritten
MENU. On v0.0.5 its address is `0x8005fd9c`. The ambush's battle music and
parameter paths instead call resident `getSpeciesBattleMusic` and
`getSpeciesPara`; neither uses that helper.

An ELF relocation audit of the v0.0.5 object files followed direct call
relocations from `startBattle`, `handleBattleStart`, `loadBattleData`,
`BTL_battleMain`, `NPCEntityTickBattle`, and the battle intro. Cutting the
graph at its first MENU function left two entry paths:

- `BTL_battleMain → handlePause → modLabMenu → modLabMenuLoaded`:
  `modLabMenu` first calls `loadMenuOverlay`. This is the explicit Cheats UI
  gateway, not an unguarded helper call during battle setup.
- `loadBattleData → loadBattleDataTick → modPresent → modReplayMainMenu →
  renderMainMenu`: the redraw is gated by `MOD_TICK_PRIM_MAIN_MENU`.
  The menu closes clear this flag, and the tick setup resets it. The ambush
  does not enable the save-menu renderer.

This is a direct-call/source audit, not a proof about every possible
indirect callback or prior memory corruption. It found no equivalent
unguarded MENU helper call in the ambush path. The battle overlay is loaded
before its functions run; QUICK BATTLES accepts a preload only when its
checksum still matches. The sound-bank/voice/effect staging order is left
unchanged.

The v0.0.5 battle-before-ambush tests passed on both 2 MB and 8 MB with
Omnimon, QUICK BATTLES off, and MENU left closed. The pre-ambush states'
68 bytes at `0x8005fd9c` match BTL_REL exactly and differ from MENU_REL
(SHA-256 `9bd2921ea52af53551888fa243f7e27785ae06e97458630904949886c37fae4c`).
Thus the known rebirth helper really is overwritten in these tests;
opening a menu has not repaired it. The third Gabumon encounter still
enters combat and returns to field control. This supports the call audit's
finding that this particular stale helper is not reached by the ambush.

## Reproduction method

The current probe also records the GPU packet cursor and ordering tables.
Interpreter runs sample every render pass, including undisplayed fast ticks,
for a cursor beyond the
81,920-byte area or damaged ordering-table headers. A successful field
return is reported separately from packet integrity: an instrumented
v0.0.5 replay returned after one overflow in 491 monitored frames (peak
82,644 bytes). Earlier matrix rows do not have this later monitor.


`tools/dev/playtest/gabumon_ambush.py` boots a private copy of the save
corpus, selects Spanish, keeps the fortress uncleared, and talks to the
third Gabumon. It records model occupancy, the allocator's free list,
largest free block, corruption check, CPU location, battle loading state,
enemy count, and return to field control. The partner is changed through
the normal evolution path. The probe never opens OPTIONS or Cheats
between evolution and the ambush, so those menus cannot repair a stale
MENU helper accidentally.
Trigger 1 is set so eligible nearby enemies join rather than randomly
depart. The probe records the actual fighter IDs/species and checks the
engine's one-to-three-opponent limit.
To select the exact line with tall partners, the final probe temporarily
suppresses competing automatic conversations and places the tamer at
slot 2's coordinates. This bypasses normal walking collision and can change
visibility/packet use; it is not the original player's recorded trajectory.
It restores every NPC's original talk flag before closing the dialogue, so
battle selection uses the disc's original flags.

The diagnostic `forced` layout calls `scriptLoadModel(351)` and
`scriptSetDigimon(351, 3, 0)` at a game-loop boundary. The fourth map entry
must already identify Kotemon. These are the game's normal model/entity
loaders, using the disc's existing NPC position, stats and flee point.
The supplied disc is unchanged. A forced layout with the recruited flag
set deliberately overrides the normal availability rule; it is a stress
case rather than a reachable shipped scene.

Bulk runs began with the emulator's dynamic recompiler; unfinished cases
were subsequently run in the interpreter to catch first-chance exceptions.
The probe defaults to the interpreter; `--cpu dynarec` is optional.
`--keep-going` preserves failed encounters and continues other combinations;
the final exit status still fails if any recorded encounter did not return.
The diagnostic C calls
need interpreter execution breakpoints: the probe saves the complete scene,
restarts the same disc/RAM configuration in interpreter mode, restores that
state, runs the loaders at a game-loop boundary, then saves/restores the
scene into the requested backend. It checks the actual backend and RAM
size after each switch. This preserves the scene's RAM, including overlay
contents; it does not reload MENU into the tested state. `--cpu interpreter`
keeps the whole run in interpreter mode for focused diagnosis.

Battle entry requires an advancing battle frame counter, GAME_STATE 1,
and completed asynchronous loading. Enemy HP is then set to zero to shorten
the fight; the engine still performs victory, teardown and the return to
field control. This checks battle setup and teardown, not a complete
unassisted three-enemy fight. Map entry and approaching the NPC use the
existing warp/position harness, rather than a playthrough from the canyon.

Example, for a matching disc and its staged executable with ELF/map:

```sh
xvfb-run -a python3 tools/dev/playtest/gabumon_ambush.py "$DISC" \
  --exe "$EXE" --out build/ambush-2m --port 39941 \
  --ram-mb 2 --layouts normal,forced
```

Repeat with `--ram-mb 8` and a different output/port. A `boot.state` can
be reused only with its matching `boot.json` (same executable hash and RAM
size). `--prior-battle` runs a separate wild encounter first, without
reloading MENU afterward. Both disc versions use the original 2 MB model
heap even on an 8 MB emulator: the extra RAM caches cold partner clips.
An 8 MB pass therefore does not by itself rule out model-heap exhaustion.

## Attempts and instrumentation corrections

- Initial build preparation found missing private regenerated assembly.
  After copying the local generated seed, extraction rejected the inherited
  `extracted` symlink. A private extraction resolved that requirement.
- The initial emulator launcher exited 143 before reaching a test. Its
  orphan emulator was stopped and the probe was relaunched with a completion
  marker.
- The first probe waited for GAME_STATE 2, which is a loading/intro state.
  Visual inspection showed a functioning fight in GAME_STATE 1. The probe
  was corrected to require an advancing battle frame counter and finished
  loading. The affected 2 MB and 8 MB probes were interrupted and rerun
  from their matching boot checkpoints. They are instrumentation failures,
  not game-hang reproductions.
- After four completed 2 MB cases and five 8 MB cases, the probes were restarted with
  direct HTTP RAM/Lua access to reduce command-launch overhead. An initial
  long Lua URL was rejected with HTTP 400 before another case completed.
  Long commands now use the same file-backed Lua endpoint as the existing
  harness. Completed results are retained by `--resume`; interrupted cases
  are rerun.
- An early 2 MB pad wait reported no display refreshes. Replaying its
  pre-battle state advanced the battle counter from 61 to 246 rather than
  reproducing a persistent stop. A later 8 MB diagnostic case advanced
  from battle frame 7 to 411 and also hit the return timeout. Its state
  selected Kotemon as fighter 5, still alive at 965 HP. The early probe
  cleared only the three Gabumon slots, so it failed to shorten that
  encounter. The corrected probe clears the selected fighters' HP, and
  the final matrices start afresh with this instrumentation. These earlier
  timeout results do not establish an ambush freeze.
- The build initially used a shared cache. It was stopped and restarted
  with a private cache in the investigation worktree. The cache copy's
  initial launcher exited 143; a detached checksum-verified synchronization
  completed. All subsequent build/cache output is isolated in the worktree.
- Under heavy host load, the first corrected-matrix launches were still
  in evolution when interrupted to extend the wall-clock watchdogs. These
  launches completed no encounter cases. Pad waits now allow 60 seconds
  for the requested emulated refreshes; map and battle phases allow
  300 seconds. The jobs retain a low scheduling priority without stacking
  an additional priority reduction on the already-low-priority shell.
- A later 8 MB interpreter run reached classic intro state 2 but did not
  reach an advancing battle counter before its 300-second watchdog.
  The saved state has three Gabumon selected and 131,576 bytes free with
  no allocator corruption. A standalone breakpoint probe used an invalid
  Lua register alias and does not contribute a game-failure result.
  The unchanged intro-timeout state, restored into the dynamic recompiler,
  reached active combat in 12.2 seconds including emulator startup and
  returned to field control in 34.5 seconds after the selected enemies'
  HP was cleared. This attempt does not establish a persistent freeze.
  The faster backend reduced host-starvation timeouts, but its later faults
  required interpreter validation of the remaining cases.
- The faster-core Minotarumon / QUICK BATTLES on / recruited / forced
  case hit emulator failures. The 2 MB log says "Unrecoverable error while
  running recompiler" at `0x80060514`, then resets RAM/CPU. The first 8 MB
  process disconnected; a later attempt trapped a reserved instruction
  with EPC `0x001ffd98`, on the stack. Both pre-battle states are preserved.
  The exact 2 MB state and the exact 8 MB state separately enter battle and
  return control in interpreter mode, with sound heaps. Their field-state
  object lists contain no active callbacks into the overlay range.
  Save-state inspection found the CD-ROM component present, rather than
  a truncated snapshot. The probe now invalidates host CPU translations
  after state restores; a 2 MB retry passed, while 8 MB still required its
  explicitly recorded interpreter replay. Those failures were not
  independently traced; the later interpreter watch establishes a concrete
  packet overflow. Translation invalidation is not a game fix. Per-case CPU
  backends are retained with the results.
- An initial WarGreymon attempt opened a different Gabumon's dialogue.
  The probe correctly refused to count it as section 7. Temporary talk
  suppression and closer placement now select section 7; all flags are
  restored before the fight, and the corrected 2 MB normal/forced cases
  pass.
- WarGreymon forced-layout QUICK BATTLES cases also trapped in the
  recompiler during asynchronous battle loading (battle frames 8–9). The
  exact 2 MB pre-battle state passed in the interpreter, but an 8 MB
  interpreter retry trapped in `AddPrim` with overwritten ordering tables.
  A subsequent write watch identified the banner overflow described above.
  Remaining cases
  were resumed in interpreter mode, preserving previously completed cases
  and recording the actual backend per case. These tests do not establish
  that translation invalidation solves these faults.

- Main baseline validation began in the interpreter. Four Agumon cases per
  RAM mode completed before a deliberate interruption switched the remaining
  coverage to the faster backend. Completed rows were retained; interrupted
  rows were rerun. The exact baseline disc/executable copies are preserved
  separately from the patched build.
- The probe gained per-frame GPU monitoring after the initial matrices.
  One monitored replay returned despite a packet-area overflow. Return-only
  rows therefore do not establish packet integrity. An earlier standalone
  call-audit launch needed its repository module path corrected; it affected
  no emulator encounter.

## Baseline matrix

Inputs: v0.0.5 tag `2d6974c74cde30c2adbb29cb1efb72b0ecb37d61`,
USA image SHA-1 `0837751cf5b5d84e7cea0dd344aad4b3311a0119`;
main at `8f3fae8d26c25f7eb27e491d19510959062a7a12`.
Runtime dialogue/UI checks use Spanish.


Every row below covers four partners (Agumon 3, Minotarumon 330,
WarGreymon 373, Omnimon 461), both QUICK BATTLES settings, both Kotemon
recruitment states, and normal/forced layouts: 32 distinct combinations.
Every loaded setup has exactly three NPC entities normally or four when
forced. Completed rows retain their actual CPU backend.

| Disc | RAM | Returned | Failed |
|---|---:|---:|---:|
| v0.0.5 | 2 MB | 32 | 0 |
| v0.0.5 | 8 MB | 31 | 1 |
| main baseline | 2 MB | 30 | 2 |
| main baseline | 8 MB | 31 | 1 |

The v0.0.5 8 MB failure is WarGreymon / quick on / recruited / forced,
with packet overflow in the interpreter. Both main matrices fail
Minotarumon / quick on / recruited / forced; an exact-state interpreter
replay and write watch confirm the banner overrun on main. The second
main 2 MB failure is WarGreymon / quick on / not recruited / forced:
the native-core process terminates, so that individual failure lacks an
independent write trace. Its pre-state and emulator log are retained.

"Returned" means battle entry followed by field control. It does not
assert packet integrity for rows without the later frame monitor; a
separate v0.0.5 replay demonstrably returned after a nonfatal overflow.

## First guard and validation correction

The first, budget-only guard passed a full eight-language build, image
SHA-1 `360469f4805243c3c4a01b2f224255cb7b4af8a1`.
Baseline image SHA-1: `c2251b05292eaa539846cfa288f17bf52e83b4ef`.
The matched builds use game-version text `v0.0.5-dev.428+8f3fae8d` and
the same build settings. Set that explicit `MOD_VERSION` to reproduce an
investigation image after committing, since the default includes Git HEAD.
`main_BSS_END` stays `0x801ceb00`, heap stays 185,328 bytes, and both
81,920-byte packet areas are unchanged. The BTL image grows from 151,916
to 152,160 bytes (+244). `heapcheck` and all 320 archive-backed setup checks
pass, with the same tightest 608-byte margin. The complete 356-patch series
applies to the pinned decompilation, producing tree
`b2249b3672a4dac7fdd77bef103a2929a4e1ffc3`.

That candidate returned in 14 completed matrix cases per RAM mode before
its matrices were deliberately stopped; the two interrupted setups are
not game failures. All six focused interpreter cases returned with no
completed-frame packet violations. These are candidate measurements, not
validation of the final patch.

The tail measurement exposed an ordering assumption: `addObject` takes the
first free slot, so a newly registered banner can precede later model draws.
An exact candidate-state replay with the corrected monitor confirms the
burst in slot 10 followed by two Digimon renderers, with 18,608 packet bytes
emitted after it (344 sampled passes, peak 77,272, no overflow in that run).
A fixed allowance cannot bound those model packets. The final patch therefore
defers the normal-battle banner, using its own reserved ID, before applying
the packet guard. Its resident dispatch code required a new matched heap
measurement; it adds no persistent buffers/state.

The monitor was also strengthened: a discarded fast-battle render can skip
`GsSortClear`, leaving an old banner-end marker. The final monitor clears that
marker when the packet area resets and samples `applyDrawOffset`, which runs
after rendering on displayed and undisplayed passes. The candidate's raw tail
maxima are not a validated estimate of final frame-command requirements.

## Banner guard validation

The revised 356-patch series applies cleanly, producing tree
`244701f0f350ced3fe70e906d97cdf6cf04e67d4`. The matched eight-language link measures **96 resident bytes**:
`main_BSS_END` changes from `0x801ceb00` to `0x801ceb60`, heap base from
`0x801ceb10` to `0x801ceb70`, and total heap from 185,328 to 185,232 bytes.
The BTL image still grows 244 bytes. No persistent buffer/state is added;
the two 81,920-byte packet areas are unchanged. `heapcheck` passes and all
320 actual-archive setups fit, with a tightest margin of **512 bytes**.
The revised full build passes with image SHA-1
`1fcfd016a6b2633b49cc3fe2cfa72078b7f46ddb`. The banner-only revision returned in all 32 matrix cases per RAM mode.
Three focused 2 MB interpreter cases (Minotarumon, WarGreymon and Omnimon,
QUICK BATTLES on, recruited, diagnostic layout) returned without packet
violations. Across 1,181 render passes the peak was 76,828 bytes; both
banner phases ran, and no packets followed the deferred banner before
`applyDrawOffset`. A synthetic no-room test also advanced both phases and
returned (109 gathering calls, 55 burst calls, 1,477 monitored passes,
zero violations). That test deliberately moves the GPU cursor and is a
unit-style diagnostic, not ordinary gameplay.

A supplemental 8 MB interpreter run stopped with a distinct effect-loading
fault. It is retained as a failure, rather than folded into successful
banner validation. This prompted the effect guard and combined validation below.

## Effect initialization context

The banner-only build's Minotarumon / quick on / recruited / diagnostic
8 MB interpreter case stops at `BTL_setupLoadedEFEFile + 0x460`
(`0x8006dda4`), loading from the unaligned address `0x01424233`.
The loader is in state `0x16` (effect initialization), `LOAD_EFE_STATE` is
1 and `MOD_BATTLE_LOADING` is 2. The model heap is intact with 34,112 free
bytes; packet use is 66,100 bytes and the monitor reports no overflow.

The loader spreads initialization across callbacks, using shared effect
interpreter globals. Between callbacks, `BTL_tickEFEEngine` and
`BTL_renderEFEEngine` traverse the newly published effect slot and replace
`EFE_SCRIPT_CONTEXT`. The saved failure has it pointing to inactive
subeffect 8 at `0x80012f7c` (its `inst` is null); its uninitialized instance
field is `0x01424233`. After the init script ends, the loader dereferences
that instance while testing its frame. The slot's actual initialized
instance remains at `0x80012b70`, with frame -1.

The second patch skips effect ticking and rendering while
`MOD_BATTLE_LOADING` is nonzero. No technique can start before that flag
clears already. This preserves the loader's interpreter state without new
resident data or changing sound, voice, engine or effect staging order.
The classic blocking loader keeps its existing behavior.

## Ordinary combat supplement

The probe's `--gameplay` mode uses the existing test-save/evolution and
warp helpers, places the tamer 500 units from the third Gabumon once,
then uses only controller input and reads through approach, dialogue and
the full battle. It does not suppress conversations, clear enemy HP, or
reset the battle counter. This mode rejects forced layouts.

On the banner-only build, the 2 MB Agumon / classic / not recruited case
completed the full fight and returned control. The following recruited
case was deliberately interrupted to rebuild with the effect guard; it
is not counted as a pass or a game failure. Final ordinary-gameplay
coverage will use the newly built disc. The four-NPC overlap is no longer
reachable on the investigated current script; existing forced-layout
results remain separate diagnostics, not a claim of a normal-gameplay
reproduction of the original report.

The first ordinary-combat pilot used host polling and a 300-second wall
limit. One Agumon timeout was already in a new section-6 battle, showing
that the section-7 fight had ended; another Minotarumon run was still
advancing combat. Neither is evidence of a persistent freeze. The final
probe pauses the emulator at the first refresh that shows field control,
without writing game RAM, so repeated confirmation cannot run past it into
a new touch conversation. Full combat gets a 900-second host limit.
The pause also releases the active pad override cleanly.

With this observer, unpatched main completes full 2 MB Agumon and
Minotarumon fights, QUICK BATTLES on and Kotemon recruited. Artifacts:
`build/baseline-control-2m/`. Both used the normal three-NPC layout and
unaltered enemy HP/conversation flags after initial test-save setup.
A separate read-only interpreter trace on main, 2 MB, Minotarumon, quick
on, normal layout, records effect initialization context transitions;
its full fight reached the early host limit without packet violations
(`build/baseline-context-2m/`).

A further banner-only 8 MB replay restored the retained diagnostic
four-NPC checkpoint and used only the usual approach helper and pad input
until effects finished loading. It reached active combat with no packet
violation (`build/banner-context-8m/`, 343 monitored render passes). It did
not reproduce the loading exception at that contact timing, and is not
counted as a complete battle or an ordinary reachable scene.

## Combined build

Both fixes apply with the 357-patch series, tree
`5d255f4ed5fb0a9fde2042ca52ecb84ad72a9c66`. The combined full eight-language
build passes, image SHA-1 `5015a5edf17d3b89b98a76098144a5125094ae27`.
The effect guard adds **64 B to BTL** and **0 resident bytes** relative to
the banner revision. Both fixes together cost **96 resident bytes**:
`main_BSS_END` is `0x801ceb60`, heap 185,232 B, and the two packet areas
remain 81,920 B each. The combined BTL image is 152,224 B (+308 B against
main baseline). `heapcheck` and all 320 actual-archive setup checks pass;
the tightest margin remains 512 B. Build log:
`build/build-context-fixed.log`. The initial attempt ended with SIGTERM
during derivation; the detached retry completed successfully.

Runtime validation uses fresh boots from the combined disc, with its
matching staged executable/ELF/map in `build/context-fixed-exe/`. Earlier
save states contain old executable/overlay code and are not used to
validate this new image. Ordinary test groups cover the same four
partners, both quick-battle settings and both recruitment states.

## Combined runtime results

All **16/16** normal-layout, full-combat combinations return to field
control on 2 MB: Agumon, Minotarumon, WarGreymon and Omnimon, both QUICK
BATTLES settings and both Kotemon recruitment states. These runs use
`--gameplay`; no enemy HP or NPC talk flags are changed after positioning.
They use the current normal three-NPC scene, not the older four-NPC
layout. Output groups: `build/context-gameplay-2m/`,
`build/context-gameplay-minotarumon-2m/`,
`build/context-gameplay-wargreymon-2m/`,
`build/context-gameplay-omnimon-2m/`.

The focused 2 MB interpreter runs (quick on, recruited, normal layout)
complete with Minotarumon, WarGreymon and Omnimon. The successful runs
sample **7,845** render passes, peak **75,112 B** of
81,920 B, no packet violations, and both banner phases observed. The
additional 8 MB Minotarumon interpreter run also completes. Across these
four successful instrumented runs there are **11,556** sampled passes,
peak **75,332 B**, zero violations. The deferred banner has no
later object packet tail before `applyDrawOffset` in these runs. All
recorded model-heap checks remain intact.

A read-only context write watch sees **126 tick calls and 126 render
calls while loading**, and **zero context writes from those functions**
in that interval. Evidence: `build/effect-guard-watch.json`.

### Retained long-run timeout

The first focused Omnimon interpreter attempt does **not** count as a
pass. It reaches active combat and is last observed advancing at battle
frame **9,504**, with two enemies defeated and one still at full HP.
Later emulator API requests time out, including failure-state capture.
The probe relaunches under `--keep-going`, overwriting that emulator's
original stdout log. The saved pre-encounter state, battle/banner images
and failed result row remain in `build/context-watch-2m/`; there is no
exact failure state or complete packet monitor for that failed attempt.
Its cause is unclassified. It is not a reproduction of a stop immediately
after the reported dialogue.

An isolated Omnimon repeat, with no additional context-write watch,
completes the full fight and returns: `build/context-omnimon-retry-2m/`.
It samples 1,334 passes, peak 63,928 B, zero violations. No manual finisher
or RAM intervention is used in that repeat. The attempted manual-pad
inspection of the earlier failed process never reached its button call
because its initial RAM request failed.

The probe now copies emulator stdout into the failing case directory
before any automatic relaunch, preserving that evidence on future API or
native-core failures. This diagnostic-only follow-up is syntax checked;
the successful gameplay/monitor paths are unchanged.

### Repeating ordinary coverage

```sh
xvfb-run -a python3 tools/dev/playtest/gabumon_ambush.py "$DISC" \
  --exe "$EXE" --out build/ambush-gameplay --port 39941 \
  --ram-mb 2 --layouts normal --gameplay --cpu dynarec
```

An exact reporter memory-card save immediately before the line would be
most useful, with game version/disc base, partner and equipped techniques,
QUICK BATTLES setting, Kotemon recruitment/fortress progress, emulator
version and RAM setting. An uncut entry video and a save state of the
actual stop would help distinguish a loading stall, a running battle,
and a renderer fault. The current normal scene cannot reproduce the
older four-NPC availability by changing recruitment alone. Physical
PlayStation, exact v0.0.4, tournament and VS behavior remain untested.
