# vault

"Open it and stay" (R3) melts the wall. Angemon keeps the door on 311, with the hints, then comes back to the city by
itself: Jijimon tells it on the next homecoming after the memory news, and the recruit flag, three prosperity points and
the summit's fallback rescue return with it. "Come to the city" keeps the wall frozen until the tamer goes down again:
the descent is not forced again (`vault_kept`).

The band across the statue room (97, step 1) is the only way on to the rest of the Sanctuary (BlueMeramon, the gym), so
the descent is offered only until it is answered (`vault_kept`; after "Stay", until the thaw is told on 311,
`thaw_told`) and never stands in the way afterwards. `tools/test_vault_passage.py` guards it.

The keeper on 311 reuses the city hint script (211:8), whose lines address
script speaker 6. Its sole NPC keeps physical slot 0 but declares `section=6`;
this controls both its map script id and its own talk section. Leaving the
script id at 5 crashes the speaker-name lookup on the first shared hint.
See the [investigation](../../../../../docs/investigations/ice-keeper-dialogue.md)
and `tools/dev/playtest/ice_keeper.py` for the 2 MB pad-driven reproduction.
