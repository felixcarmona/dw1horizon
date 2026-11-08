# Recruitment announcements

The player videos for v0.0.7 show Sukamon walking out of Trash Mountain without
visible city narration. The original disc only sets trigger 239 (200 + 39) and
adds one prosperity point; Horizon adds the departure. The extended Python pass
supplies a regional jingle and generic narration, but only after removing him.
The original-story pass has neither. Shellmon's earlier correction, 39cd309f,
keeps the announcement before the walk. Sukamon now uses that same order in both
stories, without changing his flag, prosperity or absence on subsequent visits.

The audit covers base `recruit`, `recruitable`, `send_to_city` and embedded DWS,
plus the extended story's resident scenes and compiler-generated announcements.

| Scene | Finding and correction |
|---|---|
| Sukamon, script 159 section 7 | Announce before the two walking legs; region 14, effect 17. |
| Megadramon, script 198 section 53 | A departure walk suppressed the extended compiler announcement even though there was no join narration. Add narration and the Infinity jingle (region 17, effect 0) before departure. |
| Nanimon, scripts 48, 82, 109, 145, 180 | The fifth encounter gives the large key chain and sets trigger 253 without city narration. Add the regional jingle and city line inside `key_chains == 4`, in all five possible final locations. Earlier visits still only award their existing key chain. |
| Myotismon and SkullGreymon, script 64 section 5 | Add city narration for still-unrecruited species at the completed lab story, alongside its existing flags and prosperity. Earlier Myotismon flags also serve the mansion quest; an already-listed species gets no second announcement at the lab. |
| Other original narrated recruits | Existing narrator lines and `send_to_city` already carry their region's jingle. Shellmon already announces before departure. |
| Extended residents and added recruits | `send_to_city` or the compiler's guarded announcement handles them. Reward boxes and ending narration do not count as join narration. |

A walk by itself no longer counts as evidence of an announcement in the Python
lowerer. Explicit city narration, including the shared localized `qol` lines,
still prevents a second generated announcement. This preserves the original
story's quest-specific flags while closing the silent-walk case for extended
story authors.

The changes add script/text bytes, with no resident C or BSS growth. The standard
story buffer, disc build and heap checks remain required; runtime checks use
PCSX-Redux with its original 2 MB RAM.
