# Story-state compiler target

DWS separates the `original` allocation profile from `extended-save`, which uses
persistent flags and 32-bit saved/scene variables. The latter compiles with
`--exe story-state`. The everything recipe uses the existing mod executable and
original allocation pools; this compiler target does not change that recipe.

The separate optional C extension is parked: its first patch does not apply to the
current production series, including on the untouched cleanup baseline. Compiler
examples exercise its instruction generation; they do not certify a newly built
optional executable. Rebase and measure that extension before using it as a
runtime target. The production everything build uses its own proven target.

## Allocation and saved identities

`tools/dws/alloc.py` is the allocation authority. The extended profile provides
16,384 persistent flags, 1,024 saved variables and 256 scene variables. Variables
are 32-bit values. Saved flags address the interpreter's story-bit range; scene
variables use the scene-variable operand range. Original triggers and pstats retain
their identities. The compiler's lock files are append-only.

The allocator retains the existing serialized profile identifiers when reading
saved locks. `tools/dws/targets.py` maps the descriptive compiler profile names to
the allocator's pool registry. No saved flag, counter or registry ID is renumbered.
The tagged memory-card formats and record identities are documented in
[save-format.md](../reference/save-format.md).

## Compiler and bytecode

The interpreter target must implement the story-variable instructions and their
comparison forms. `tools/dws/bytecode/` owns their encoding and operand formats;
`tools/dws/gen.py` checks that a source's operations are supported by its selected
executable. A program using only original pools/instructions retains those
instructions when compiled for the story-state target.

```sh
python3 tools/dws.py check tools/dws/examples/expanded-state.dws \
  --profile extended-save --exe story-state --build -o build/state-example.SCN
```

`check` without `--build` can analyze the larger allocation profile independently
of an executable. Compiling its wider state operations requires the matching
story-state target. Supply `--exe-dir` for an independently prepared target; the
default directory is `build/decomp-story-state/build/us/psx/gcc`.

## Resources and original hardware

Pool size, script buffers and NPC slot capacity are distinct limits. More slots do
not provide model heap or SPU space. A playable build must use the actual target's
facts, archive and linker map for its checks:

```sh
python3 tools/dws.py check-heap build/game/with-new-screens/MAPHEAD.SCN \
  --map build/decomp-game/build/us/psx/gcc/SLUS_010.32.elf.map \
  --archive build/game/DIGI.DAT --facts build/game/derived/exe-facts.json
```

Keep the original 2 MB PlayStation budget. Measured margins belong to their exact
executable and archive; historical port estimates do not describe a new build.
The compiler's regression examples verify code generation. Actual-target resource
checks and hardware play checks establish whether a target/content combination fits.

## City rules and proofs

The table-driven city rules and presence declarations are described in
[city-rules.md](city-rules.md). `tools/dws/testing/city_equivalence.py` compares
those rules with independently extracted original C functions, using the host
fixtures in `tools/dws/testing/city_oracle/`. The emulator adapter is separate from
that static oracle. See [story-testing.md](../developing.md) for the corpus,
checkpoint, graph and trace proof tools.
