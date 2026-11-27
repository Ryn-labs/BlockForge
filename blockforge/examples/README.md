# BlockForge examples

Example builds kept as code that regenerates them. Run one with:

```python
from blockforge import examples, sandbox
blocks, meta = sandbox.run_safe(examples.code("good_cottage"))
```

Only two kinds of example may be added here:

1. Our own builds, made in this project (owned by the project, same licence as the code).
2. CC0 or CC-BY files, with the source link, the author and the licence written in the table below.

Nothing from the quality reference pictures (owner's picks, unknown licence) is copied here; they were only used to
write down the rules in `docs/QUALITY.md`.

| Example | What it is | Quality | Source | Licence |
| --- | --- | --- | --- | --- |
| `good_cottage` | Two-storey timber-framed cottage (oak fill in a dark oak frame) with a storey band, a lower wing, green trimmed gable roofs, 2 x 2 framed windows with flower boxes, porch with a balcony over it, a side balcony, chimney, fenced front garden, farm plot | 85 | Made in this project from `blockforge/patterns.py` | Owned by the BlockForge project |
| `good_manor` | Two-storey manor (plaster in a spruce frame), storey band, gray cross-gable roof, two wings with chimneys, porch with a balcony over it, a back balcony, garden, three farm plots | 86 | Made in this project from `blockforge/patterns.py` | Owned by the BlockForge project |
| `good_village` | Five buildings (a light-framed hall with a teal roof and a balcony as landmark, four varied houses with red, gray and green roofs), plaza with a well, winding streets, trees, garden, farm | 87 (town) | Made in this project from `blockforge/patterns.py` | Owned by the BlockForge project |
| `light_manor` | The reference look: three storeys of birch in a dark oak frame, storey bands, teal layered cross-gable roof, 2 x 2 framed windows with boxes, porch with a balcony, back balcony, a wing roof as a terrace garden reached by an outside stair with a landing, teal-roofed east wing, chimney, garden, farm plots | 94 | Made in this project from `blockforge/patterns.py` | Owned by the BlockForge project |

The quality numbers come from `blockforge.quality.score`; `tests/test_quality.py` keeps the cottage at 70 or more,
the manor and `light_manor` at 80 or more, and the village at 70 or more as a town.
