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

The redundant Continue pan is already fixed on main by `6dc46c25`; see
[player-report investigation](player-reports-2026-11-08.md). This investigation
does not duplicate that fix or the separately developed frame-rate option.

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
All 81 sampled tamer-position/camera-offset tuples agree exactly between tags.
The visible regression here is presentation cadence; no additional camera
movement fix is justified by that walk. Other screens, partners and cold-tile
boundaries may have different costs and are outside this one-walk comparison.

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
