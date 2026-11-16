# Field hover audit (2026-11-16)

Positive numbers are units above floor Y=0; negative clearance means an existing floor intersection. Each cell is **lowest-point minimum–maximum / highest mesh point** over every decoded logic tick. The frame JSON also retains both points on every tick. Root Y belongs to the entity and is included; X/Z travel is excluded. No idle-floor normalization is used.

All 183 imported partners were measured, a superset of air-specialty species, winged walkers and floating/swimming models. The table below lists air specialties plus every model whose field clearance ever exceeds 25 units. The external provider tree was read only and was cleared by another build after these measurements; the captured frame reports remain in `build/flight-height-results/` because the requested `$OUT` is read-only. A second local snapshot was checked with the new QA, selecting the last pipeline stage rather than the first overlay filename. Its flags agree with the initial capture. KingEtemon 303 was still rebuilding its native overlay, so its original captured measurements are retained in the combined report.

## Aquilamon: cause and repair

At `42b3477d`, idle clearance was already 19.5–437.2 and walk 29.2–449.8 units. Slots 0, 1, 2, 3, 4 and 18 still decode exactly as that commit on current main. Its 50-unit prose was inaccurate: the constants were 20/30. More importantly, reducing body Y climb to 15–22% and adding one constant lift only bounded the minimum. Moving wings, tucked legs and body pitch still changed the mesh floor by over 400 units.

No later chibi reshape caused this: 188 has no chibi profile. Battle-original restores changed battle slots, not these field frames. The later bone size/proportion fit (`clip_rig.fit`, body offset/scale modes and `conform`) likewise did not change these field frames. The repair compresses the measured mesh-floor trajectory at its existing phase, changing only carrier Y; wing, head, tail and leg rotations, travel, loop length and sounds remain within the existing one-unit codec tolerance. Battle and care slots remain exact. Condition idles 1/18 are generated after field authoring: their wing droop is followed by an explicit mesh hover fit, otherwise the new lower flight would put the drooping wings below the floor.

| Slot | Main lowest / top | Repaired final lowest / top |
|---|---|---|
| 0 | 19.5–437.1 / 1256.6 | 29.5–51.2 / 874.1 |
| 1 | 21.0–437.1 / 1110.0 | 30.4–51.2 / 818.1 |
| 2 | 29.2–449.8 / 1266.6 | 80.2–140.8 / 961.6 |
| 3 | 19.5–437.1 / 1256.6 | 29.5–71.2 / 892.1 |
| 4 | 29.9–365.6 / 1198.2 | 79.8–140.2 / 977.2 |
| 5 | -60.9–137.6 / 760.3 | -60.9–137.6 / 760.3 |
| 7 | 21.4–137.6 / 781.3 | 21.4–137.6 / 781.3 |
| 8 | -86.0–93.0 / 733.2 | -86.0–93.0 / 733.2 |
| 9 | -26.4–9.8 / 767.9 | -26.4–9.8 / 767.9 |
| 10 | -79.1–93.0 / 721.6 | -79.1–93.0 / 721.6 |
| 11 | -9.4–9.5 / 753.8 | -9.4–9.5 / 753.8 |
| 12 | -166.8–156.5 / 830.9 | -166.8–156.5 / 830.9 |
| 13 | -79.4–157.0 / 822.9 | -79.4–157.0 / 822.9 |
| 14 | -117.6–75.2 / 717.1 | -117.6–75.2 / 717.1 |
| 15 | -117.6–75.2 / 717.1 | -117.6–75.2 / 717.1 |
| 16 | -117.6–75.2 / 717.1 | -117.6–75.2 / 717.1 |
| 17 | -117.6–75.2 / 717.1 | -117.6–75.2 / 717.1 |
| 18 | 21.0–437.1 / 1110.0 | 30.4–51.2 / 818.1 |
| 19 | -117.6–115.0 / 717.4 | -117.6–115.0 / 717.4 |

At rendered thirds (alpha 1365/2730), idle spans 28.6–53.8, condition idles 28.4–58.6, walk 79.3–141.0, condition walk 29.2–71.8, run 77.6–145.6. All stay above the floor. Final model resident storage is 71,502 / 100,352 bytes; cold sector reads fit 8,192 bytes. No engine heap allocation or buffer was enlarged.

## Engine height

No specialty-dependent fixed flight offset is added. Aquilamon has air/battle specialties, radius 216 and height 445; these describe gameplay bounds/elements, not a flying Y offset. `tools/species.py` encodes specialties and the defined/partner/condition-effect/default-effect/shots flags; none is a flight-height flag. `decomp/src/main/partner.c:partnerTickWalking` chooses slots 0–4 by follow distance and condition. `map.c:entityMoveForward` explicitly assigns `posData->location.vy = 0`; `anim.c` updates entity Y from root momentum (`anim->locY`, `location.vy = anim->locY >> 15`). The mesh flight is in the bone animation. The decomp was inspected in the sibling main repository because this worktree has no decomp checkout.

## Native calibration

| Native | Idle | Walk | Condition walk | Run |
|---|---|---|---|---|
| 7 AIRD | 32.6–49.6 / 452.9 | 79.0–137.1 / 453.4 | 21.9–93.6 / 411.5 | 75.4–134.6 / 453.4 |
| 21 BIRD | -73.5–128.1 / 704.5 | -58.3–138.6 / 656.5 | -133.5–88.8 / 561.6 | -82.0–250.2 / 680.2 |
| 24 HOEE | 37.3–57.0 / 409.8 | 62.0–118.2 / 470.1 | 13.4–105.3 / 463.7 | 107.8–134.2 / 485.3 |
| 25 VEGI | -1.5–1.4 / 348.7 | -38.5–53.0 / 389.1 | -10.1–-1.4 / 342.4 | -22.9–39.9 / 400.0 |
| 28 VEDA | 88.6–108.9 / 410.2 | 88.2–129.3 / 423.1 | 65.3–104.4 / 410.6 | 88.2–129.3 / 443.0 |
| 29 POYO | 124.5–165.5 / 272.4 | 122.2–155.8 / 288.7 | 71.8–106.3 / 226.5 | 80.0–152.0 / 270.9 |
| 37 BAKE | 116.1–190.7 / 394.6 | 129.6–156.0 / 393.7 | 63.4–118.4 / 343.6 | 114.4–171.6 / 435.7 |

7=Airdramon, 21=Birdramon, 24=Whamon, 25=Vegiemon, 28=Vademon, 29=Poyomon, 37=Bakemon. Silphymon 226 and Garudamon 460 are imports, currently grounded walkers (see below). Parrotmon is absent from this repository’s species catalogue and provider outputs, so there is no model to measure.

`tools/models/audit_field.py --from BUILD --hover --native-from EXTRACTED --out REPORT.json` measures every field/care slot and returns failure on high field hover or missing/unreadable models. Absolute peak-clearance limits are 200 for 0/1/18, 160 for 2/3 and 260 for 4; all seven native references pass. Care gestures, sleep and toilet arcs are reported in full but have no locomotion ceiling. Checking only the minimum clearance would miss Aquilamon. Final emitted catalogue skeletons are used after native bindings and late care overlays.

## Other high-hover candidates (listed, not changed)

- Magnadramon 215: idle 207.4–295.9 / top 646.8; walk 286.4–317.5 / 617.8; condition walk 249.6–296.8 / 569.3; run 272.1–303.1 / 622.1; slots 1/18 also exceed 200. Her authored flight keeps a high base hover.
- Scorpiomon 275: idle 143.8–218.8 / 570.1; walk 142.5–202.9 / 558.9; condition walk 106.0–168.7 / 611.3; run 132.3–197.7 / 641.2. This is an authored floating swimmer, above the native locomotion ceilings in 0/2/3.
- NeoCrimson 402: grounded idle −0.3–3.4 / 494.8, but slots 1/18 float 188.4–221.1 / 713.6. This is a condition-clip discrepancy, not normal flight.

## Imported air species and models with airborne field frames

| Species | Idle | Walk | Condition walk | Run |
|---|---|---|---|---|
| 184 Hawkmon | -0.7–1.1 / 316.0 | -0.2–1.0 / 342.6 | -0.3–0.1 / 314.4 | -0.3–30.6 / 386.8 |
| 187 Stingmon | -5.8–5.0 / 467.0 | -0.1–7.5 / 517.9 | 0.6–6.6 / 523.3 | 0.9–32.1 / 522.0 |
| 188 Aquilamon | 19.5–437.1 / 1256.6 | 29.2–449.8 / 1266.6 | 19.5–437.1 / 1256.6 | 29.9–365.6 / 1198.2 |
| 190 Angewomon | -5.5–0.7 / 443.8 | 0.8–16.0 / 440.8 | -0.7–3.3 / 522.9 | 1.7–12.4 / 459.5 |
| 195 Flamedramon | -7.1–0.3 / 467.5 | 2.5–3.4 / 505.3 | 2.2–3.4 / 467.2 | 4.1–36.5 / 494.8 |
| 196 Halsemon | 0.3–1.7 / 382.3 | 2.7–3.2 / 374.7 | 2.4–3.7 / 359.2 | 2.5–3.5 / 374.1 |
| 198 Nefertimon | -2.9–-0.4 / 469.8 | 0.9–2.0 / 487.9 | 0.1–2.0 / 487.9 | 1.0–11.8 / 489.7 |
| 199 Paildramon | -1.9–1.2 / 534.9 | 0.5–11.2 / 530.9 | 0.2–13.1 / 520.1 | 0.8–40.7 / 497.5 |
| 200 Pegasusmon | 0.2–1.8 / 432.3 | 2.6–3.2 / 437.6 | 2.5–3.5 / 425.9 | 2.5–14.7 / 460.1 |
| 201 Lighdramon | -5.2–-3.1 / 439.3 | 2.4–3.2 / 440.8 | 2.2–3.9 / 426.1 | 2.5–4.1 / 427.6 |
| 202 Submarimon | 95.2–115.1 / 479.1 | 95.2–114.7 / 479.1 | 97.5–115.1 / 478.6 | 97.5–115.1 / 478.6 |
| 205 MegaKabuterimon | -1.1–3.1 / 522.0 | 1.8–3.9 / 644.7 | 2.1–3.1 / 468.1 | 1.7–3.1 / 503.1 |
| 206 MagnaAngemon | -1.9–1.5 / 611.4 | -80.5–-16.6 / 616.1 | -34.8–-2.9 / 576.0 | -69.1–-17.6 / 594.4 |
| 207 Seraphimon | 0.3–0.3 / 657.4 | -0.7–24.3 / 687.0 | -0.6–1.8 / 655.4 | -0.5–25.9 / 674.3 |
| 209 Lillymon | 42.5–61.9 / 567.5 | 46.3–79.2 / 552.8 | 42.5–58.7 / 556.2 | 59.7–87.0 / 534.9 |
| 210 GranKuwagamon | 1.1–3.8 / 669.6 | -0.4–0.1 / 695.8 | -1.9–0.9 / 688.6 | -0.3–0.0 / 707.5 |
| 211 MetalSeadramon | -0.8–113.3 / 604.1 | 4.1–119.1 / 591.2 | 24.6–116.9 / 591.5 | 18.1–100.8 / 628.4 |
| 212 VenomMyotismon | 0.9–2.5 / 674.8 | 0.8–3.0 / 648.4 | 0.6–3.0 / 668.0 | 1.9–82.4 / 816.2 |
| 213 AeroVeedramon | 1.0–3.2 / 688.8 | 1.4–2.3 / 683.0 | 0.8–3.2 / 682.1 | 1.8–14.2 / 707.0 |
| 214 Shakkoumon | 14.2–16.3 / 564.1 | 14.6–15.5 / 568.4 | 14.6–16.5 / 565.5 | 14.6–15.4 / 568.1 |
| 215 Magnadramon | 207.4–295.9 / 646.8 | 286.4–317.5 / 617.8 | 249.6–296.8 / 569.3 | 272.1–303.1 / 622.1 |
| 216 Devidramon | -3.6–8.8 / 416.5 | 0.3–4.1 / 390.1 | -1.5–4.5 / 390.1 | 3.0–15.8 / 419.1 |
| 221 Salamon | 1.2–3.5 / 188.9 | 1.5–2.4 / 179.5 | 1.4–3.4 / 177.4 | 1.4–5.4 / 179.8 |
| 222 BlackGatomon | -2.6–-1.6 / 366.4 | 2.3–2.9 / 217.7 | 1.2–4.2 / 219.9 | -0.9–0.7 / 230.9 |
| 223 LadyDevimon | 99.5–106.2 / 543.7 | 103.9–109.3 / 542.0 | 77.0–80.2 / 517.1 | 120.5–127.6 / 534.0 |
| 225 Shurimon | 2.0–5.5 / 370.1 | 0.5–4.6 / 365.4 | 1.1–4.4 / 351.5 | 2.2–10.2 / 335.9 |
| 226 Silphymon | -0.2–1.6 / 469.9 | -0.6–1.6 / 471.5 | 0.5–1.4 / 476.6 | 0.9–28.8 / 461.5 |
| 228 Baronmon | -0.9–0.8 / 379.3 | -1.7–0.4 / 380.3 | -0.5–1.0 / 387.2 | -0.5–7.0 / 388.8 |
| 229 Phantomon | 41.3–87.5 / 652.6 | 20.9–131.5 / 657.6 | 27.1–57.4 / 647.2 | 27.9–115.2 / 623.8 |
| 230 Rosemon | 0.4–3.0 / 520.9 | 0.8–3.9 / 524.2 | 1.4–4.0 / 513.9 | 2.1–12.7 / 530.6 |
| 231 ShellNumemon | -2.0–0.0 / 328.9 | -2.2–0.2 / 341.3 | -2.1–0.5 / 348.2 | -1.8–-0.5 / 349.3 |
| 232 BomberNanimon | -1.4–0.6 / 290.2 | -10.0–10.0 / 297.4 | -23.1–-4.3 / 294.6 | -20.7–27.4 / 321.4 |
| 233 RedOtamamon | 83.5–96.7 / 291.5 | 81.4–94.7 / 278.7 | 81.7–90.3 / 259.4 | 81.6–104.0 / 288.1 |
| 234 Gatomon | -2.2–-1.3 / 379.0 | 1.7–2.5 / 223.7 | 1.0–3.9 / 226.0 | -1.0–0.7 / 237.5 |
| 235 Candlemon | -0.4–-0.0 / 369.6 | -0.3–52.1 / 414.8 | -0.5–19.6 / 389.1 | -0.5–33.5 / 392.5 |
| 236 DemiDevimon | 35.1–114.6 / 356.1 | 27.1–135.4 / 359.7 | 35.8–91.5 / 320.9 | 45.3–135.6 / 350.1 |
| 238 Dolphmon | -0.4–0.0 / 342.1 | -0.4–0.1 / 342.2 | -0.5–0.2 / 342.1 | -0.1–-0.0 / 342.2 |
| 241 Wizardmon | -1.4–0.6 / 435.7 | -29.6–12.5 / 449.4 | -2.0–4.4 / 439.5 | -23.0–5.1 / 420.8 |
| 242 Sorcermon | -1.4–0.6 / 435.7 | -29.6–12.5 / 449.4 | -2.0–4.4 / 439.5 | -23.0–5.1 / 420.8 |
| 243 Starmon | 0.6–3.9 / 414.5 | 0.9–32.5 / 441.9 | 0.6–18.0 / 429.2 | 2.1–45.3 / 437.1 |
| 244 SuperStarmon | 2.1–6.8 / 725.5 | -0.3–58.1 / 773.2 | 0.3–31.5 / 751.4 | 2.4–80.6 / 765.0 |
| 245 Piedmon | 15.7–56.7 / 563.2 | 22.4–60.9 / 552.3 | 22.3–56.6 / 534.6 | 27.3–68.6 / 513.1 |
| 247 Kokuwamon | 4.0–5.0 / 298.4 | 3.7–6.2 / 294.3 | 3.1–5.8 / 295.1 | 3.6–6.8 / 288.2 |
| 248 MarineAngemon | 69.7–103.9 / 424.3 | 70.9–118.3 / 430.3 | 54.6–101.5 / 370.9 | 63.4–76.2 / 382.1 |
| 249 Quetzalmon | 22.2–51.2 / 524.3 | 35.5–71.0 / 554.5 | 7.6–21.3 / 449.8 | 25.7–58.2 / 510.6 |
| 250 Shadramon | 0.3–2.6 / 457.6 | 3.9–4.1 / 473.4 | 3.9–4.0 / 484.3 | 2.2–7.0 / 514.7 |
| 251 Solarmon | 18.2–25.1 / 221.2 | 12.9–25.0 / 223.8 | 9.6–17.8 / 223.1 | 21.0–30.9 / 222.7 |
| 252 Thundermon | -1.0–0.7 / 253.7 | -0.4–0.6 / 264.7 | -0.9–0.7 / 261.0 | -0.1–17.6 / 265.1 |
| 254 Tylomon | 108.8–150.6 / 293.1 | 107.9–158.3 / 310.9 | 61.7–85.8 / 265.9 | 117.7–131.1 / 283.6 |
| 255 Valkyrimon | -3.5–-0.1 / 460.9 | -0.1–6.2 / 480.2 | 0.1–3.0 / 499.9 | 3.7–8.6 / 425.2 |
| 256 VioletElecmon | -0.3–2.1 / 311.6 | -41.4–-10.5 / 310.9 | -41.3–-14.8 / 180.6 | -12.9–122.9 / 371.8 |
| 257 Triceramon | -1.4–3.1 / 553.8 | -0.6–3.1 / 547.0 | -0.6–3.3 / 499.5 | -3.7–25.6 / 511.7 |
| 258 SaberLeomon | -6.9–-3.0 / 470.4 | -9.6–0.4 / 472.4 | -9.0–-5.2 / 428.1 | -5.8–13.6 / 539.0 |
| 259 Okuwamon | -10.8–0.8 / 565.0 | -0.3–0.2 / 560.9 | -0.8–0.5 / 544.4 | -0.4–16.3 / 574.6 |
| 262 Flymon | 26.6–47.0 / 531.9 | 24.4–53.3 / 550.1 | 7.0–29.3 / 532.9 | 36.2–76.1 / 540.1 |
| 269 Garbagemon | -0.6–0.5 / 365.9 | -0.9–39.6 / 424.9 | -0.5–0.6 / 381.3 | -0.5–65.1 / 451.1 |
| 270 PrinceMamemon | -0.6–0.4 / 490.0 | -23.6–33.0 / 520.0 | -31.9–21.8 / 508.8 | -25.6–66.0 / 555.0 |
| 271 Plesiomon | 46.6–102.0 / 601.3 | 60.0–140.2 / 598.3 | 23.9–65.7 / 469.0 | 84.3–208.3 / 481.8 |
| 274 Blossomon | -0.5–1.7 / 313.5 | 0.1–14.5 / 317.6 | 0.1–8.8 / 304.4 | 0.5–27.8 / 325.1 |
| 275 Scorpiomon | 143.8–218.8 / 570.1 | 142.5–202.9 / 558.9 | 106.0–168.7 / 611.3 | 132.3–197.7 / 641.2 |
| 277 SkullMeramon | -1.6–0.7 / 567.0 | -1.5–1.2 / 563.9 | -0.3–31.6 / 560.8 | 25.9–86.7 / 531.9 |
| 280 Pumpkinmon | 1.8–11.9 / 559.1 | -0.4–0.5 / 571.8 | -0.4–0.5 / 580.8 | -0.4–64.3 / 620.1 |
| 281 Cyclonemon | 1.8–4.9 / 555.0 | 1.9–4.7 / 567.7 | -0.1–4.8 / 539.7 | -2.4–5.1 / 545.7 |
| 282 Kiwimon | -1.1–1.1 / 344.8 | -0.4–0.5 / 348.3 | -0.3–0.5 / 335.7 | -0.4–13.4 / 350.8 |
| 283 Syakomon | 73.1–78.3 / 246.4 | 73.5–108.4 / 294.1 | 73.7–87.7 / 255.1 | 73.7–125.9 / 331.2 |
| 287 Tapirmon | -1.3–-0.3 / 204.0 | -7.5–0.5 / 203.0 | -7.3–0.2 / 188.2 | -2.0–6.2 / 229.3 |
| 288 Boltmon | -0.5–0.4 / 546.2 | -1.3–0.4 / 541.4 | -0.3–0.5 / 488.7 | -0.4–36.4 / 472.0 |
| 289 ChaosLord | -2.4–0.4 / 671.5 | -48.9–-5.7 / 659.9 | -42.8–-6.6 / 659.1 | -0.0–43.0 / 649.1 |
| 290 Clockmon | 0.2–2.5 / 597.8 | 0.8–2.4 / 604.9 | 1.4–2.8 / 605.9 | 1.5–15.8 / 602.2 |
| 291 Dragomon | -1.4–1.5 / 610.2 | -0.9–1.1 / 664.3 | -0.9–0.8 / 635.1 | -0.7–13.2 / 623.2 |
| 293 Gryphonmon | 1.4–3.6 / 823.5 | 1.4–3.4 / 796.2 | 1.7–3.5 / 565.9 | 2.4–15.7 / 823.6 |
| 294 Datamon | 0.6–3.3 / 241.2 | 1.4–4.3 / 226.7 | 0.6–5.3 / 225.8 | 2.3–16.2 / 234.9 |
| 295 Vilemon | -10.4–-8.1 / 469.7 | -26.9–-10.8 / 481.0 | -28.4–-13.1 / 456.4 | -28.4–2.9 / 488.3 |
| 296 Grizzlymon | -0.5–2.5 / 419.5 | -0.1–2.1 / 415.6 | -0.1–2.7 / 425.0 | 0.9–27.0 / 439.7 |
| 300 SlashAngemon | -1.9–0.4 / 561.1 | 0.7–3.5 / 548.0 | -1.2–0.4 / 543.0 | -0.6–0.9 / 548.3 |
| 303 KingEtemon | -1.2–1.3 / 408.0 | -13.3–9.3 / 445.8 | -20.1–17.0 / 453.1 | -43.4–12.7 / 410.3 |
| 304 Divermon | 1.4–4.0 / 460.2 | -1.3–3.4 / 490.5 | 2.4–3.5 / 476.4 | 2.5–28.3 / 492.6 |
| 305 Ebidramon | 16.6–47.6 / 526.6 | 22.2–89.8 / 558.4 | 8.3–58.1 / 511.1 | 34.0–87.4 / 588.0 |
| 306 GrapLeomon | -9.4–-8.9 / 425.9 | -22.3–-8.0 / 424.8 | -11.8–-5.6 / 412.5 | -20.9–7.6 / 384.8 |
| 308 Dinohyumon | 0.6–3.1 / 445.3 | -1.5–2.4 / 433.1 | -2.0–2.9 / 396.6 | 1.4–22.3 / 430.9 |
| 309 Antylamon | -1.4–0.8 / 647.6 | -1.8–1.2 / 655.9 | -0.7–0.4 / 654.6 | -1.6–0.4 / 634.9 |
| 310 Assaultmon | -0.9–0.6 / 547.0 | -1.0–14.0 / 602.0 | -0.4–18.0 / 603.0 | -0.8–28.6 / 598.9 |
| 312 Creepymon | -0.1–2.5 / 561.7 | 0.7–4.6 / 550.9 | 0.9–4.0 / 557.6 | 2.7–24.0 / 529.3 |
| 314 SkullSatamon | -1.0–0.7 / 496.1 | -0.5–11.4 / 495.4 | -6.8–4.7 / 479.0 | -0.4–50.8 / 530.1 |
| 315 Taomon | -1.8–0.7 / 481.5 | -1.0–0.5 / 474.6 | -0.4–0.5 / 425.1 | -7.0–0.5 / 423.8 |
| 316 Sakuyamon | -1.3–1.1 / 564.9 | -28.9–1.3 / 504.9 | -0.7–8.0 / 474.2 | -1.9–11.2 / 496.5 |
| 317 Fujinmon | -1.3–1.4 / 586.2 | 0.6–3.2 / 561.3 | 0.6–3.3 / 582.2 | 1.4–21.9 / 566.6 |
| 318 Gallantmon | -0.5–1.7 / 578.0 | -0.6–3.4 / 574.0 | -0.5–4.3 / 617.4 | 0.3–17.2 / 593.8 |
| 319 Pharaohmon | -1.6–-0.0 / 610.0 | -1.4–1.0 / 601.9 | -2.9–2.9 / 550.9 | 1.1–25.3 / 583.5 |
| 320 Growlmon | 0.2–2.8 / 361.1 | -2.5–2.5 / 361.1 | -2.7–3.4 / 332.0 | 1.1–27.8 / 354.5 |
| 321 Knightmon | -1.3–0.4 / 502.4 | -0.5–2.0 / 490.0 | -0.4–3.5 / 460.9 | -0.9–29.8 / 462.3 |
| 322 Kyukimon | -1.0–1.0 / 470.1 | -0.1–2.5 / 450.9 | 0.3–2.5 / 427.8 | -0.1–22.2 / 433.8 |
| 323 Lynxmon | -5.2–-1.9 / 612.3 | 1.1–2.4 / 571.0 | 1.0–3.0 / 568.8 | 1.2–41.4 / 613.4 |
| 324 Maildramon | -4.7–-2.3 / 655.6 | 1.1–3.1 / 635.8 | 0.6–2.7 / 616.0 | 1.4–19.2 / 649.6 |
| 325 Musyamon | -1.8–0.6 / 551.1 | -2.1–0.7 / 558.3 | -0.8–33.5 / 575.8 | -0.5–71.6 / 612.4 |
| 326 WarGrowlmon | 1.7–6.3 / 574.5 | 2.2–12.4 / 594.9 | 3.8–14.5 / 611.7 | -2.4–38.9 / 636.4 |
| 327 Gargoylemon | 0.3–3.5 / 525.5 | 0.6–3.2 / 551.4 | 0.8–3.2 / 490.9 | 1.5–15.3 / 581.2 |
| 328 Snimon | -0.2–0.1 / 663.3 | -0.2–0.1 / 550.8 | 0.1–31.1 / 602.6 | 0.0–65.6 / 632.8 |
| 329 Ghoulmon | 7.9–10.3 / 573.8 | -0.6–0.3 / 637.1 | -1.6–0.7 / 687.0 | -0.5–16.1 / 668.9 |
| 330 Minotarumon | -4.3–-0.2 / 467.0 | -1.9–25.5 / 472.3 | -1.9–3.8 / 424.1 | -1.1–55.1 / 491.2 |
| 332 Roachmon | -3.7–0.8 / 465.7 | -0.8–1.8 / 438.3 | 41.3–69.0 / 494.4 | 1.5–47.2 / 538.6 |
| 333 Raijinmon | -7.3–2.8 / 576.3 | 1.2–3.0 / 598.1 | 0.4–3.3 / 594.4 | 0.9–15.7 / 577.6 |
| 334 Mummymon | -0.4–1.4 / 544.7 | -1.6–1.4 / 542.1 | -1.4–2.3 / 522.4 | -1.8–17.1 / 523.4 |
| 336 Raidenmon | 1.1–4.2 / 486.5 | 1.3–2.2 / 483.6 | 1.3–2.3 / 417.9 | 1.1–3.2 / 485.6 |
| 352 Monmon | 1.8–4.3 / 297.9 | -1.5–4.4 / 309.1 | 0.1–3.9 / 279.4 | -0.7–20.6 / 304.3 |
| 373 WarGreymon | 0.1–2.7 / 445.7 | -0.6–5.7 / 444.1 | -2.5–3.0 / 420.6 | 1.5–26.3 / 442.8 |
| 400 Apocalymon | 42.1–114.1 / 696.1 | 41.5–125.4 / 703.6 | 39.9–62.6 / 732.8 | 41.8–149.4 / 734.7 |
| 401 Pukumon | 0.9–3.0 / 291.9 | 1.9–16.2 / 301.0 | 1.0–5.4 / 284.8 | 5.0–28.6 / 327.9 |
| 402 NeoCrimson | -0.3–3.4 / 494.8 | -0.8–5.0 / 501.0 | -1.9–6.0 / 494.0 | 0.0–24.6 / 491.5 |
| 404 BlackWarGreymon | 0.1–2.7 / 525.4 | -1.3–6.1 / 524.0 | 0.0–3.2 / 490.1 | 1.4–22.0 / 528.0 |
| 406 MaloMyotismon | 0.5–2.5 / 649.9 | -2.3–1.6 / 689.3 | -1.6–0.9 / 723.3 | 0.7–69.2 / 738.3 |
| 408 Suijinmon | -5.1–-0.0 / 482.2 | -2.6–9.8 / 485.1 | -2.6–10.1 / 485.1 | -2.7–22.6 / 514.6 |
| 430 Zanbamon | 5.0–6.8 / 503.5 | 5.3–6.3 / 500.1 | 4.2–6.8 / 507.8 | 5.0–19.8 / 525.2 |
| 431 Kurisarimon | 14.9–30.1 / 385.9 | 21.4–67.9 / 429.3 | 5.6–16.9 / 379.6 | 24.7–108.3 / 472.1 |
| 460 Garudamon | 2.9–4.7 / 531.3 | 3.1–5.1 / 540.2 | 3.4–5.6 / 517.2 | 3.6–22.2 / 543.4 |
| 470 Pabumon | 4.0–10.4 / 139.2 | 4.2–26.4 / 181.1 | 4.0–10.9 / 151.3 | 4.1–29.0 / 171.9 |
| 472 YukimiBotamon | 1.0–2.0 / 122.6 | 1.0–12.9 / 138.7 | 1.0–6.6 / 126.2 | 1.1–19.8 / 146.1 |
| 476 Nyaromon | 3.0–4.0 / 171.3 | 3.0–8.2 / 177.5 | 3.0–6.4 / 168.1 | 3.0–12.6 / 178.7 |
| 477 Yokomon | 1.0–14.0 / 247.2 | -15.3–64.5 / 295.8 | -8.0–20.4 / 256.6 | -16.9–95.5 / 326.8 |

Validation: 32 related unit/integration tests ran (two existing optional model-fixture tests skipped), including final-provider clearance, native reference thresholds, unchanged battle/care frames, preserved joint channels and rendered thirds. `edit.py check 188 --species-pins` and final field QA passed. Git staging/commit is blocked by read-only worktree metadata; a binary patch accompanies the eight-line result.
