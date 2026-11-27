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
| `good_cottage` | Compact two-storey timber-framed cottage (birch fill in an oak frame, 11 x 9) with its green gable facing the front, a lower wing set back, a storey band, 2 x 2 framed windows with flower boxes, porch with a balcony over it, a back balcony, chimney, fenced front garden, farm plot | 92 | Made in this project from `blockforge/patterns.py` | Owned by the BlockForge project |
| `good_manor` | `manor_layout` facing east on log stilts: plaster in an oak frame, red roofs, a taller central block with a front gable, stepped wings with balconies, porch and grand stair; gardens, path with lantern posts, three farm plots | 90 | Made in this project from `blockforge/patterns.py` | Owned by the BlockForge project |
| `good_village` | Five buildings (a light-framed hall with a teal roof and a balcony as landmark, four varied houses with red, gray and green roofs), plaza with a well, winding streets, trees, garden, farm | 88 (town) | Made in this project from `blockforge/patterns.py` | Owned by the BlockForge project |
| `light_manor` | The reference look and shape (`manor_layout`): a three-storey central block of birch in oak logs with a big teal front gable, an entrance bay with its own gable, two stepped two-storey wings with balconies, porch and grand stair on a stone terrace, storey bands, chimney; path with lantern posts, two flower gardens, trees, farm plots | 96 | Made in this project from `blockforge/patterns.py` | Owned by the BlockForge project |

The quality numbers come from `blockforge.quality.score`; `tests/test_quality.py` keeps the cottage, the manor and
the village (as a town) at 80 or more and `light_manor` at 85 or more.
