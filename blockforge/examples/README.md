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
| `good_cottage` | Timber-framed cottage with a lower wing, trimmed gable roofs, framed windows with flower boxes, porch, chimney, fenced front garden, farm plot | 97 | Made in this project from `blockforge/patterns.py` | Owned by the BlockForge project |
| `good_manor` | Two-storey manor, cross-gable roof, two wings with chimneys, porch with a balcony over it, garden, three farm plots | 98 | Made in this project from `blockforge/patterns.py` | Owned by the BlockForge project |
| `good_village` | Five buildings (a hall as landmark, four varied houses), plaza with a well, winding streets, trees, garden, farm | 98 (town) | Made in this project from `blockforge/patterns.py` | Owned by the BlockForge project |

The quality numbers come from `blockforge.quality.score`; `tests/test_quality.py` keeps the cottage at 70 or more and
the manor at 80 or more, and the village at 70 or more as a town.
