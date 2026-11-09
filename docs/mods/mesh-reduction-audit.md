# Imported mesh reduction audit

`tools/models/audit_reduction.py` is an offline authoring tool. It requires NumPy,
the player's extracted DW1 files, and the three private source-game extractions
accepted by `tools/models/edit.py`. It neither downloads assets nor stores them
in tracked files. Outputs, including source-derived images, belong under `build/`.
Keep the evidence directory separate from the name of a developer disc build:
the build driver replaces its output directory.

```sh
python3 tools/models/audit_reduction.py \
  --games build/imported-model-edit/source-games \
  --out build/mesh-evidence/final --jobs 3
python3 -m unittest tools.test_reduction_audit tools.test_wargrowlmon
```

`--ids 326` narrows a run. `--resume` reuses results only when content hashes of
the tools, authored content, extraction and source games match. Importer caches
remain subject to the editor's source pins. Every final provider output is
checked against the species pins, including field overlays, replacement rigs,
native builders and battle passes. The source recipe is selected through the
actual delta source path, including size recipes; species display names are not
reliable recipe identifiers.

The tool reads the complete pre-reduction mesh through the bundled disc readers,
with face deletion and mesh reduction disabled. Temporary reader instrumentation
retains the original texture pages, palettes and UV corners before packing,
palette merging or vertical texture resizing. The reference image therefore
includes texture information that the importer may have lost. Native replacement
species 224 uses the actual native MetalGreymon source, rather than its retired
imported mesh.

## Correspondence and coverage

Authored proportions and different idle poses must not count as missing surfaces.
The tool fits source vertex pools to the final local geometry, then poses the
reference with the final skeleton. It accepts indexed pools only with equal
sizes, full affine rank and a maximum residual of three game units. For rebound
parts or compacted pools, unique oriented UV triangles establish corner
correspondences instead. Repeated UVs are resolved within the corresponding
object before attempting a cross-object match. A deterministic affine consensus
requires at least 60% of independent corner pairs; altered corners from edge
collapses are then measured against that transform. The support fraction and
residual are recorded, and fits without a majority are refused.
Palettes are not part of that match: an incorrect
palette must remain detectable. A planar fit is accepted only when all source
vertices lie in the observed plane. Ambiguous matches are refused.

Where reduction compacted vertex pools, the pinned importer can bridge the
comparison: its pool establishes the authored final proportion transform.
The recorded import scale and subsequent size passes reconstruct full source
coordinates in those units. At least 98% of importer vertices must be retained
source endpoints within 2.5 units before that bridge is accepted. Cross-object
UV matching is disabled when source and final rigs agree, so identical mirrored
parts cannot substitute for each other.

Each result includes matched and unmatched source parts, the fraction of source
surface area checked, unassigned final triangles and `complete`/`partial` status.
An error or unmatched region is **unverified**, never a clean bill of health.
Contact sheets show matched source regions beside the complete shipped model
in six views with a shared camera. Unassigned final faces are always visible,
so a correspondence failure cannot masquerade as a missing shipped part. Their
header states the source area coverage. They are review aids; the software
renderer does not reproduce the PS1 ordering table or affine rasterization.

## Measurements

The JSON retains per-part/bone measurements and anatomy labels where available:

- Source and final triangle counts, surface area, area decrease, degenerate
  triangles, boundary and nonmanifold edges.
- Oriented source triangles with no counterpart, including small detail that
  a surface-distance threshold or silhouette can miss. This is a geometry change
  measure; a legitimate edge collapse also changes triangles.
- Area-weighted source surface samples farther than the tolerance from any
  surviving triangle in the same part. Four interior samples per triangle make
  this an estimate, not an exhaustive Hausdorff distance. The tolerance is the
  larger of 2.5 game units and 0.3% of the reference diagonal.
- Newly exposed boundary segments compared with the original boundary paths,
  allowing the same tolerance for quantization. Existing openings and UV seams
  are not automatically new holes. Five samples check each boundary segment.
- Enclosed volume and volume decrease only when both surfaces are closed,
  manifold and consistently oriented. For an open part, volume is `null`; its
  signed surface integral is provided separately and is not enclosed volume.
- UV and CLUT samples outside the texture, missing UVs, source-opaque samples
  becoming transparent or opaque black, and large RGB changes. Reference
  palettes and texels come from the source page. The absolute texture audit
  additionally inspects every final textured primitive, including unpaired parts.
- Geometric silhouette XOR/union and drawn-mask differences in six directions,
  including elevated three-quarter views. The same camera frames both meshes.

The score prioritizes uncovered area, the worst substantial part, triangles
without counterparts, opaque texture damage, large colour changes and the worst
drawn-mask change.
It is a review order, not a probability or a count of proven bugs. Authored
remodeling, intentional source effects, fine texture resampling and incomplete
correspondence require inspection. `ranked.json` holds all measurements;
`ranked.md` is the full table. Each species has a phone-width contact image.
Exit zero means all requested rows were processed without errors; inspect
coverage and findings before deciding whether a model is correct.

## Preventing further face deletion

New `import_batch.load_source` authoring uses the seam-aware edge reducer when
the mesh exceeds 713 primitives. It no longer deletes small faces to hit the
count. The old deletion algorithm is retained only behind
`legacy_face_drop=True` in frozen recipe replay: changing historical importer
bytes would invalidate every dependent plain delta. Existing repairs use
`edit.py put` and final provider pins, without rewriting unrelated imports.

There was also an independent edge-reducer defect: its four-triangle minimum
applied to an entire bone, so it could erase a disconnected small component
while a larger component on that bone remained. The vertex-neighbor link test
also allowed a tetrahedron to become coincident opposite faces. Synthetic
fixtures reproduce both cases. New authoring records `preserve_components: true`:
each original component retains at least four triangles (or its original count
when smaller), and a collapse cannot create duplicate faces. If these
constraints prevent reaching the budget, authoring must be revised rather than
deleting the part. Historical serialized specs without the flag retain their
original replay. This does not silently regenerate every shipped species.

The 713-primitive, 172-vertices-per-object and original resident/cold-buffer
targets still apply to the WarGrowlmon repair. The audit and authoring changes
add no runtime allocation or executable data. Other severe findings need their
own source comparison and storage checks before a repair is accepted.
