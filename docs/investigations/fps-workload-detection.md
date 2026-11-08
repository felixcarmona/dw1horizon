# Title workload detection

AUTO now counts actual `modPresent` swaps over at least 120 vblanks after one
warm-up tick. At least 40 presented fps selects 60 mode; otherwise it selects
20. The result is cached until reset. The old hblank poll never changes it.

The title renders 64 instances of its resident medal mesh through the normal
matrix, lit geometry, GPU and multipass presenter. No map, model or heap
allocation is added. The title quad covers the geometry, but it remains in the
submitted OT. Diagnostics measured 34,892 packet bytes in a pass, below the
existing 81,920-byte packet buffer. The matrix is restored afterward. This is a
representative field rendering load, without field scripts or battle effects.

## Redux measurements

PCSX-Redux development build 389, source
`b0a245bc23c303b081fa578364e1ead9bd2727e5`, x64 dynarec, software GPU,
OpenBIOS, NTSC. Executable source is main at `ffbe905d` plus the workload patch;
all 428 patches apply together. Diagnostic and release builds use the same
64-instance workload. Captures use matching executables and RAM configurations.

| Core model | RAM | Raw swaps / vblanks | Trial fps | Old hblank count | Old decision | New decision |
|---|---:|---:|---:|---:|---:|---:|
| Standard | 2 MB | 120 / 120 | 60 | 2184 | 20 | 60 |
| Standard | 8 MB | 120 / 120 | 60 | 2183 | 20 | 60 |
| Faster RAM execution | 2 MB | 120 / 120 | 60 | 4099 | 20 | 60 |
| Faster RAM execution | 8 MB | 120 / 120 | 60 | 4084 | 20 | 60 |
| Slower RAM execution | 2 MB | 40 / 120 | 20 | 1132 | 20 | 20 |

Redux has no implemented CPU overclock control in this build. The faster/slower
models modify the x64 JIT's instruction cycle charges, leaving vblank/root
counters, GPU scheduling, GTE latency and BIOS instruction charges unchanged.
The faster model halves eligible RAM block charges; the slower model doubles
charges where the instruction encoding permits it. RAM blocks whose charge
looks like a BIOS charge are conservatively excluded. These are approximate
core-budget simulations, **not genuine 200% or 50% hardware overclocks**. The
old probe's approximately 1.88× and 0.52× ratios corroborate the changed budget.
They do not establish accuracy on Gamma or a physical console.

Each field capture spans 600 GPU vblanks after six settling refreshes. Matching
idle checkpoints use File City (168) and Gear Savanna (69), daytime with the
clock frozen. Scaling captures start a fresh emulator process per checkpoint;
the independent title readings are retained when restoring a field checkpoint.
Mode 0 is a diagnostic override on the same executable. No breakpoints are
installed. Every sample changes the render counter by exactly one or zero;
missed increments invalidate a capture. Logic measured 20.0 Hz in every case.

| Core model | RAM | File City, 60 / 20 mode | Gear Savanna, 60 / 20 mode |
|---|---:|---:|---:|
| Standard | 2 MB | 48.4 / 20.0 | 40.0 / 20.0 |
| Standard | 8 MB | 48.5 / 20.0 | 40.0 / 20.0 |
| Faster RAM execution | 2 MB | 60.0 / 20.0 | 59.7 / 20.0 |
| Faster RAM execution | 8 MB | 60.0 / 20.0 | 59.7 / 20.0 |
| Slower RAM execution | 2 MB | 20.3 / 20.0 | 20.0 / 20.0 |

These rates use nominal 60 Hz guest time. Host flip observations for the
standard 2 MB captures were 47.77 / 19.84 fps in File City and 39.68 / 19.81 in
Gear Savanna. Faster-model host observations were 59.01 / 19.56 and
58.46 / 19.43; the instrumentation itself adds host work. These are emulator
flip events, not compositor/monitor scans. The tool records both clocks.

The 40 fps cutoff preserves the twofold improvement in Gear Savanna and the
larger improvement in File City. Requiring 55–60 would discard that benefit.
The slower model provides a negative control: its workload selects 20 and its
field 60-mode throughput is only about 20. Calibration with 48 mesh instances
was too permissive on that control; 64 discriminated it while retaining the
standard-core benefit. Extracted-C tests also cover every integer rate from
0 to 60, including an inclusive 40 and acceptance of 55.

The adaptive study in draft PR #343 measured approximately 46.6 and 40 fps in
these fields and incorrectly discarded both under a stricter deadline policy.
Its tournament result, 20/18 versus 20/20 (fps/low), remains a limitation of a
field-oriented title trial. This change does not dynamically downgrade battles
or promise improvements in every scene. Existing per-pass deadline checks are
unchanged. If an emulator slows its entire guest clock, guest VSync cannot
measure the resulting host display loss. Device validation remains necessary.

## Memory, options and checks

Release heap is 187,312 bytes, 352 fewer than the matched main baseline.
Diagnostics use 187,152 bytes. MENU remains 55,172 bytes in both builds, equal
to the baseline. The trial allocates nothing and reuses the resident title mesh,
OTs and packet areas. All 320 compiled setup cases fit against actual model
archive bytes, with minimum margins of 2,592 bytes in release and 2,432 in
diagnostics. Original 2 MB boot, Continue and both fields work; the
8 MB boot independently detects expanded RAM and gives the same decision.

Native builds pass for release, `FPS_DIAGNOSTICS=1`, and `FPS=20`; the last
contains neither trial rendering nor diagnostic globals. Sanitized extracted-C
tests cover rates, long ticks, counter wrap and one-shot behavior. All 428
patches apply, six series tests pass, localization audits 116,784 entries with
zero errors, 26 localization regression tests pass, and the save corpus check
passes. No save layout changes are made.

The requested `origin/frame-rate-option` ref was absent during this work. Main
and the local option implementation were inspected. Its AUTO arm currently
recomputes a CPU choice; integration must instead read `MOD_FPS_AUTO_MODE`.
This PR exports that stable cached result and does not duplicate the independent
AUTO/60/20 UI or change its save format.

Use `FPS_DIAGNOSTICS=1 tools/build-full.sh ...` for a test disc, then
`tools/dev/fps/workloadcheck.py --exe EXE --port PORT --out build/result.json`
against the matching running disc. Diagnostics export raw swaps, vblanks,
fps ×100, old probe count, packet bytes and the cached decision. The core-scaling
experiment and complete JSON captures are retained with the local build
artifacts; the supported measurement tool uses only Redux's vblank API and RAM.
