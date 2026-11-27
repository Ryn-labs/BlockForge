# BlockForge 1.12.0-v2 benchmark

Lower is better. `mistakes` counts every check; `mistakes_ex_ow` leaves out overwritten blocks (scripts that fill then carve overwrite on purpose, so that column is mostly style).

| id | key | floating | removed | overwritten | buried_path | jump_steps | corner_turns | blocked_doors | wrong_facing | size_off | script_errors | fix_rounds | mistakes | mistakes_ex_ow | time_s | cost |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | cottage | 0 | 0 | 225 | 4 | 0 | 0 | 0 | 0 | 4 | 0 | 3 | 233 | 8 | 77 | 0.273 |
| 2 | machiya | 0 | 0 | 693 | 0 | 0 | 0 | 0 | 0 | 3 | 0 | 3 | 696 | 3 | 229 | 0.56 |
| 3 | stair_road | 0 | 0 | 6415 | 0 | 32 | 0 | 0 | 0 | 0 | 0 | 3 | 6447 | 32 | 226 | 0.521 |
| 4 | hill_castle | 32 | 9 | 1677 | 1 | 64 | 0 | 0 | 0 | 3 | 0 | 3 | 1786 | 109 | 537 | 1.263 |
| 5 | arch_bridge | 0 | 0 | 698 | 6 | 0 | 0 | 0 | 0 | 5 | 0 | 1 | 709 | 11 | 78 | 0.164 |
| 6 | round_tower | 0 | 7 | 230 | 5 | 27 | 16 | 0 | 1 | 0 | 0 | 5 | 286 | 56 | 174 | 0.5 |
| 7 | village_street | 0 | 0 | 1488 | 10 | 0 | 0 | 0 | 0 | 1 | 0 | 3 | 1499 | 11 | 306 | 0.736 |
| 8 | grove | 0 | 0 | 103 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 3 | 104 | 1 | 119 | 0.352 |
| 9 | furnished_room | 0 | 0 | 754 | 2 | 0 | 0 | 0 | 0 | 8 | 0 | 3 | 764 | 10 | 86 | 0.277 |
| 10 | cottage_edit | 0 | 0 | 316 | 5 | 0 | 0 | 0 | 0 | 0 | 0 | 3 | 321 | 5 | 116 | 0.409 |
| total | | 32 | 16 | 12599 | 34 | 123 | 16 | 0 | 1 | 24 | 0 | 30 | 12845 | 246 | 1948 | 5.05 |
