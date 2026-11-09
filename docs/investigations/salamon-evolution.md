# Salamon evolving to Gatomon with four care mistakes

Historical v0.0.7 investigation. In v0.0.8, qualifying ordinary targets instead
share an equal random draw; the care-score explanation below still applies. See
the [current selection rule](../reference/partner.md#score-calculaterequirementscore).

The reported v0.0.7 result is allowed by the ordinary evolution rules. No species,
engine or popup change is needed. The documentation needed to explain that
missing the care group is not a veto and that four requirement points do not
outrank three in the Rookie-to-Champion picker.

## Data and popup

Both v0.0.7 and the current source give Salamon (221) these ordered targets:
Nefertimon (198), Pegasusmon (200), Gatomon (234), BlackGatomon (222), Piddomon (85).
`content/species/234-gatomon.json` has `care: 1, flags: 16`: **at most one**
mistake, including one, rather than fewer than one. Its stat group is HP 1000 and
Defense 100, weight is 10 ± 5, and its bonus parent is Salamon.

The tree generator is now `tools/evo_tree.py`; neither inspected revision has an
`evo_lines.py`. Its `care()` function assigns Vaccine Champions `(1, 16)`.
The committed species row is what the build uses. `tools/guide/build.py` renders
this row as `Care mistakes ≤ 1`. The game's `chartCardBuild` calls
`chartRange(..., 0, r.care)` for a maximum; the actual formatter produces `0-1`.
The chart and engine share `evoRequirementsMet` and `evoRequirementPoints`.

`content/tables/evolution-rules.json` assigns one point each for care, weight,
stats and bonus and requires three points. With four mistakes, Gatomon loses the
care point but still qualifies when stats, weight and the Salamon bonus pass.
Failing a second group excludes it in this example.

## Reproduction and priority

The reproducible fixture has no species previously raised, NEW DIGIMON enabled,
models available, 72 hours in the Rookie form, four mistakes, weight 10, HP 2000,
MP 1000, Offense 100, Defense 200, Speed 100 and Brains 100.

| Target, in route order | Requirement points | Stat comparison if eligible |
| --- | --- | --- |
| Nefertimon | 2 | ineligible |
| Pegasusmon | 2 | ineligible |
| Gatomon | 3 | (2000/10 + 200)/2 = 200 |
| BlackGatomon | 4 | (2000/10 + 200 + 100)/3 = 166 |
| Piddomon | 1 | ineligible |

The actual Rookie picker selects Gatomon. The requirement score is an eligibility
threshold; it does not rank these eligible targets. Raising Brains to 200 ties
the comparison and keeps the earlier Gatomon. Raising Brains to 300 makes
BlackGatomon win, provided raised flags do not filter it out.

For precise route-order, raised-history and retained-accumulator behavior see
[the partner reference](../reference/partner.md#score-calculaterequirementscore).
The wiki's evolution requirement and competing-target answers now explain these
rules in English and the eight other supported languages. Existing released
article snapshots remain frozen.

## Verification

`tools/dev/playtest/evolution_selection_host.py` extracts the actual scoring,
Rookie picker and popup range formatter from a supplied patched decompilation,
compiles them on the host with undefined-behavior sanitization, and checks the
fixture against `tools/evo_check.py` and selected-ref species data. It covers
care 0/1/2/3/4, the 3-versus-4-point result, stat ties, a second failed group,
raised-history filtering and the popup range. Both current and v0.0.7 series were
applied independently to the pinned decompilation and both passed:

```sh
python3 tools/dev/playtest/evolution_selection_host.py build/evo-decomp
python3 tools/dev/playtest/evolution_selection_host.py build/evo-v007 --ref v0.0.7
```

The source tree must match the selected data ref. `--ref` selects the species and
formula data, not the C series; the caller prepares the matching tree. The harness
stubs model availability and raised flags and does not load DIGI.DAT, run an
hourly tick, animate an evolution or boot an emulator. No disc extraction or local
emulator was available in this worktree. No player save, complete stat sheet or
attachment message ID was supplied, so the fixture proves the reported outcome
is possible rather than reconstructing the player's exact selection history.

The wiki suite passed 28 tests with two optional PDF checks skipped; all 16 guide
tests passed. The updated articles rendered in all nine locales, and the chart,
popup and localization-parity checks passed. Full selftest: 76 passed, 3 failed,
58 skipped. The three failing suites also failed on an untouched archive of the
starting commit: City NPC-slot fixtures without extracted data, developer symbol
resolution without the decompilation symbols, and portrait drawing without
OpenCV. Disc-dependent checks were skipped.

There are no game C, main-executable, species or runtime-data changes: executable
and heap cost are zero. No new heap measurement is needed for this documentation
and host-test change.
