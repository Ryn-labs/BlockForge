# BlockForge 1.12.0-v2 benchmark

Lower is better. `mistakes` counts every check; `mistakes_ex_ow` leaves out overwritten blocks (scripts that fill then carve overwrite on purpose, so that column is mostly style).

| id | key | floating | removed | overwritten | buried_path | jump_steps | corner_turns | blocked_doors | wrong_facing | size_off | script_errors | fix_rounds | mistakes | mistakes_ex_ow | time_s | cost |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | cottage | 0 | 0 | 225 | 0 | 0 | 0 | 0 | 0 | 4 | 0 | 3 | 229 | 4 | 77 | 0.273 |
| 2 | machiya | 0 | 0 | 693 | 0 | 0 | 0 | 0 | 0 | 3 | 0 | 3 | 696 | 3 | 229 | 0.56 |
| 3 | stair_road | 0 | 0 | 6415 | 0 | 32 | 0 | 0 | 0 | 0 | 0 | 3 | 6447 | 32 | 226 | 0.521 |
| 4 | hill_castle | 32 | 9 | 1677 | 0 | 64 | 0 | 0 | 0 | 3 | 0 | 3 | 1785 | 108 | 537 | 1.263 |
| 5 | arch_bridge | 0 | 0 | 698 | 0 | 0 | 0 | 0 | 0 | 5 | 0 | 1 | 703 | 5 | 78 | 0.164 |
| 6 | round_tower | 0 | 7 | 230 | 0 | 27 | 16 | 0 | 1 | 0 | 0 | 5 | 281 | 51 | 174 | 0.5 |
| 7 | village_street | 0 | 0 | 1488 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 3 | 1489 | 1 | 306 | 0.736 |
| 8 | grove | 0 | 0 | 103 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 3 | 103 | 0 | 119 | 0.352 |
| 9 | furnished_room | 0 | 0 | 754 | 2 | 0 | 0 | 0 | 0 | 8 | 0 | 3 | 764 | 10 | 86 | 0.277 |
| 10 | cottage_edit | 0 | 0 | 316 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 3 | 316 | 0 | 116 | 0.409 |
| total | | 32 | 16 | 12599 | 2 | 123 | 16 | 0 | 1 | 24 | 0 | 30 | 12813 | 214 | 1948 | 5.05 |
