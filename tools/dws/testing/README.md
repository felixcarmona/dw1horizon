# Story testing

These tools own story scenarios, reachable instruction graphs, route/checkpoint
semantics and trace comparisons. Emulator transport is supplied by the developer
harness. Importing these modules does not start an emulator.

| Module | Purpose |
|---|---|
| `sweep.py` | Section corpus, instruction-graph comparison and verification campaign |
| `checkpoints.py`, `route.py`, `branches.py` | Main route checkpoints and additional branch scenarios |
| `trace_audit.py`, `random_audit.py` | Independent checks of trace normalization and random-number consumption |
| `city_equivalence.py`, `city_oracle/` | City rules against the independent original-C oracle |
| `dialogue.py` | Original-format raw dialogue inspection |
| `scenarios/` | Recorded behavioral scenarios and digests |

The sweep, route, branch and audit CLIs provide `--help`; run them from the repository
root. `city_equivalence.py --quick` uses the separately prepared target described in
`docs/mods/city-rules.md`. The raw dialogue inspector takes a DG.SCN path and optional
entry numbers. Scenario identities, trace events and ledger/checkpoint IDs remain stable.
