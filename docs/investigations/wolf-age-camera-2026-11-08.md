# Wolf: starting age and camera movement (PT-BR, v0.0.7)

## Starting age

The Status screen renders `PARTNER_PARA.age` directly. It does not divide
`remainingLifetime` by 24. The photographed 17 is an age, even though 408 hours
also happens to equal 17 days of remaining lifetime. The other photograph shows
calendar Year 1, Day 3, rather than the first instant after the introduction.
The screenshots alone cannot identify the sequence that produced that age.

Both release tags configure `firstPartner.age = 3` and
`firstPartner.lifetimeHours = 336`. Main's `1749697b` changes only the latter to
408. `partnerBirth.lifetimeHours` is already 408 in v0.0.7. The title/quiz path
creates a provisional save, then initializes the chosen partner and runs the
File City introduction. Its start kit gives 20 Meat and 1,000 bits; it does not
write age. The quiz selects a species and name, not age.

There is a state-restoration omission: `loadSavegame` puts the new payload's
partner care in `SAVED_STATE.partnerPara`, but the New Game branch does not
restore it into `PARTNER_PARA`. Continue restores it in `initializeLoadedMap`.
The USA `initializePartner` resets species-dependent care and lifetime, but
leaves age and several counters alone. Thus a cold process starts with zero
age; returning to the title can retain a previous partner's age. Horizon's
Cheats main-menu action exposes that route without editing the partner. The
underlying initializer omission predates v0.0.7.

`Restore-new-game-partner-care-before-the-opening.patch` copies the new title
payload's care before the quiz. This uses the configured age (3), clears stale
care/counters and leaves species initialization to the existing code. Continue
still restores the saved partner. It adds no resident state or new settings.
It does not rewrite existing saves or claim that Wolf used Cheats.

## Camera changes between v0.0.6 and v0.0.7

The audit covers the complete tag range, patch-series differences, camera
configuration and field-animation inputs, including changes merged through
side branches.

| Change | Effect |
| --- | --- |
| `7a6d8699`, `Stream-camera-bands-without-blocking-field-ticks.patch` | Asynchronous background-band preflight; retain scroll debt at the uploaded window edge and repay it gradually, including after pad release. Input and entities continue while cold tiles load. |
| `7810e037`, `Prefetch-scripted-camera-bands-without-blocking-the-field.patch` | Scripted pans prefetch approaching bands and retry cold steps without advancing their offsets or division remainders. Battle/forced uploads retain their paths. |
| Same commit, `Upload-diagonal-camera-bands-from-their-destination-window.patch` | Resolve both destination axes before a diagonal upload. |
| Same commit, `Choose-uploaded-camera-bands-from-the-actual-window-shift.patch` | Pick upload direction from the actual row/column displacement, including catch-up or reversal. |
| `456e8d28`, `Choose-rendering-rate-from-CPU-speed.patch` | Replace the saved manual frame-rate choice with automatic 20/60 selection, boot probing and hysteresis. At normal CPU the game selects 20; its logic still runs at 20 Hz. This changes the visible camera cadence without changing its per-tick movement. |
| `2a7d5305`, `status-portrait-camera-anchor.patch` | Status-only anchoring for travelling imported portraits; no world-camera path. |
| `55039a8d` and field-animation/model repairs | SaberLeomon's walk/slow walk/run are retimed to 22.5/15/40 units per tick. Armadillomon, Vilemon, MetalGarurumon and other imported-model repairs alter their own gait, braking or presentation. They do not change the tamer's walking speed or Agumon's camera follow. |
| `dd6f777d`, `Finish-scripted-moves-with-a-rounded-zero-step.patch` | Finish scripted tamer walks whose remaining distance rounds to zero; departure/scene completion, not ordinary pad camera speed. |
| `23095ff4` | Developer walk-tour steering accounts for distant-camera waypoints; not shipped game camera code. |

The big-partner camera lift, bounding/capping, follow distance and camera
interpolation patches are byte-for-byte unchanged between the tags. The field
care HUD adds projected UI and render work but does not change world framing.
The Status portrait fit and HUD layout changes should not be described as a
world-camera rewrite. Agumon is below the large-partner lift threshold.

The compiled `MOD_CAM_CFG` arrays also agree in all 24 bytes: lift begins above
450, lift percent 100, lift range 300, portrait fit 130 pixels, minimum scale
2048/4096, trail cap 0, battle lift enabled. Model height/radius changes can
indirectly affect that unchanged algorithm:

| Species | Height v0.0.6 → v0.0.7 | Radius v0.0.6 → v0.0.7 |
| --- | --- | --- |
| Angewomon | 565 → 418 | 223 → 165 |
| Imperialdramon | 600 → 510 | 261 → 222 |
| MegaKabuterimon | 558 → 502 | 276 → 248 |
| Zudomon | 597 → 507 | 293 → 249 |
| MaloMyotismon | 475 → 651 | 216 → 296 |
| Kyubimon | 442 → 345 | 252 → 197 |
| Kurisarimon | 460 → 360 | 191 → 150 |

Angewomon and Kurisarimon cross below the lift threshold. Status-position data
also changes broadly with the portrait-layout repair; those coordinates are
used by the Status view, not by field follow. The native tamer and Agumon model
dimensions/locomotion remain the appropriate control for Wolf's screenshot.

The redundant Continue pan was removed on main by `6dc46c25`; see
[player-report investigation](player-reports-2026-11-08.md). The main control
exposes a further framing regression: `initializeLoadedMap` calls
`initializeDrawingOffsets` twice, and that function **adds** the projected
delta rather than assigning an absolute view. The old queued pan masked the
double adjustment. Without it, the Green Gym control keeps Y origin 384 rather
than 242, leaving the tamer clipped at the bottom. The displacement during the
walk still agrees; the starting view is wrong.

`Position-the-Continue-view-once-after-collision-relocation.patch` restores
`gameLoop`'s view/projection and places Continue at the former pan's absolute,
clamped endpoint. The calculation is shared with `tickCameraMovement`, retaining
the large-partner shift and script-pan geometry. The preliminary NPC visibility
path remains intact; the final absolute placement runs after collision/story
relocation and before the existing synchronous tile upload. It queues no pan
object, so movement can follow immediately. No frame-rate option is added here.

## Runtime method

All checks use PCSX-Redux, 2 MB, normal emulated CPU, with its interpreter for
reliable execution breakpoints. This is not an Android DuckStation acceptance
claim. The host can run slower than real time; measurements use emulated CPU
cycles and native presentation events, never wall-clock video sampling.

The camera control loads the same private card fixture into Green Gym, Agumon,
PT-BR, position (0,0,0). It waits 80 logic ticks after Continue initialization,
holds Left for 40 ticks and Right for 40. The v0.0.6 save explicitly requests
60 fps; v0.0.7 reads the same bytes but selects its rate automatically. The card
is a fixture, not a claimed new game. No camera data is injected.

Over 80 ticks (4.000 emulated seconds), v0.0.6 presents 160 frames (~40 fps),
alternating one and two vblanks. Its requested 60 cannot fit every intermediate
pass in this control. v0.0.7 presents 80 frames (~20 fps), three vblanks apart.
All 81 sampled tamer-position/camera-offset tuples agree exactly between tags
and vanilla. The v0.0.7 difference in this control is presentation cadence.
Main before the follow-up has the same positions and camera displacement but
the constant 142-pixel origin error described above. Other screens, partners
and cold-tile boundaries may have different costs and are outside this
one-walk frame-rate comparison.

Runtime screenshots, clips, per-tick/per-present CSVs, build identities and
acceptance details accompany the task's external `REPORT.md`.

The portable age replay is `tools/dev/playtest/new_game_partner.py`. Use
`--expect-age 0` for the old cold-boot control, `--expect-age 17` with a matching
field state and `--restart-age 17` for the old restart, and `--expect-age 3` for
the corrected build. Its result requires the actual introduction to visit the
house and return to free control; a stale `CURRENT_SCREEN` during the quiz is
not sufficient. Fixtures and screenshots are written only to explicit output
directories. The prior age and the return-title request are disclosed fixture
writes; the quiz and introduction run without care writes.

## Acceptance

The EN/PT-BR image uses original 2 MB RAM. Main's cold New Game control starts
at 0; the corrected full introduction starts at the configured 3, with life 408,
1,000 bits and unchanged initial stats. A same-session restart fixture with a prior
age of 17 also finishes the new introduction at 3. A saved age of 17 remains 17
on Continue.

The corrected 80-tick route restores all 81 position/origin tuples to exact
agreement with v0.0.6, v0.0.7 and vanilla. Immediate Left for 60 ticks passes
native visibility and origin checks with Agumon and Greymon; the final origin
(320,250) matches vanilla at the same final position (-2250,0,79). Follow is
active from tick 1 with no fixed pan target. WereGarurumon (height 525, above
the lift threshold) also passes native visibility, retaining its intentional
height adjustment. Checking only partial actor
visibility would have missed the prior main regression.

The actual old/new C endpoint calculation also agrees in 100,000 host cases
with stubbed projection: signed coordinates, tamer/script targets, lift and
clamping. Runtime introduction pans exercise the shared calculation with real
GTE projection. The native BSS end changes from `0x801cbda0` to `0x801cbed0`:
304 bytes of resident code, no new resident state, heap 196,944 → 196,640 bytes.
The complete EN/PT-BR build and story heap gate pass. This is a selected-language
test image, not a nine-language release-image checksum claim.
