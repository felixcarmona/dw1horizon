# gear

The gear reaches the Toys on both branches. Taken to Andromon first, it is only scanned (the archive complete, M3 counted
twice) and stays with the tamer, so the Robot House scene runs as in the game: Hagurumon comes home, the song, Monzaemon
joins. Given to the Toys first, Andromon scans it later by Hagurumon's word. A 0.0.2 save whose gear was installed gets it
back from Andromon; with a full bag Andromon says so and gives it at the next talk. There is no softlock: the talk holds
as long as the tamer lacks the gear and the Toys have not had it.

While the Andromon scan is pending, the Robot House floor greeting is suppressed:
it must let the tamer carry the gear out instead of walking back to Tinmon on each
attempt to leave. Direct talks still give the reminder, and completing the scan
restores the original homecoming trigger. This also repairs saves already on the
keep branch, using the existing flags. The rule is shared by every language.

`test/test_gear_exit.py` compiles all nine language variants, assembles the floor
section and checks its effects against the original across all combinations of
the scan and toy-story flags. It also checks the choices and direct reminder's
control flow across languages; these are offline checks, not emulator playtests.
