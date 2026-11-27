# BlockForge 1.12.0 benchmark

Lower is better. `mistakes` counts every check; `mistakes_ex_ow` leaves out overwritten blocks (scripts that fill then carve overwrite on purpose, so that column is mostly style).

| id | key | floating | removed | overwritten | buried_path | jump_steps | corner_turns | blocked_doors | wrong_facing | size_off | script_errors | fix_rounds | mistakes | mistakes_ex_ow | time_s | cost |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | cottage | 0 | 0 | 225 | 4 | 0 | 0 | 0 | 0 | 4 | 0 | 3 | 233 | 8 | 77 | 0.273 |
| 2 | machiya | 0 | 0 | 693 | 1 | 0 | 0 | 0 | 0 | 3 | 0 | 3 | 697 | 4 | 229 | 0.56 |
| 3 | stair_road | 0 | 0 | 6415 | 91 | 32 | 0 | 0 | 0 | 0 | 0 | 3 | 6538 | 123 | 226 | 0.521 |
| 4 | hill_castle | 32 | 9 | 1677 | 1124 | 64 | 0 | 0 | 0 | 3 | 0 | 3 | 2909 | 1232 | 537 | 1.263 |
| 5 | arch_bridge | 0 | 0 | 698 | 109 | 5 | 0 | 0 | 0 | 5 | 0 | 1 | 817 | 119 | 78 | 0.164 |
| 6 | round_tower | 0 | 7 | 230 | 284 | 27 | 16 | 0 | 1 | 0 | 0 | 5 | 565 | 335 | 174 | 0.5 |
| 7 | village_street | 0 | 0 | 1488 | 5 | 0 | 0 | 0 | 0 | 1 | 0 | 3 | 1494 | 6 | 306 | 0.736 |
| 8 | grove | 0 | 0 | 103 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 3 | 103 | 0 | 119 | 0.352 |
| 9 | furnished_room | 0 | 0 | 754 | 20 | 0 | 0 | 0 | 0 | 8 | 0 | 3 | 782 | 28 | 86 | 0.277 |
| 10 | cottage_edit | 0 | 0 | 316 | 7 | 0 | 0 | 0 | 0 | 0 | 0 | 3 | 323 | 7 | 116 | 0.409 |
| total | | 32 | 16 | 12599 | 1645 | 128 | 16 | 0 | 1 | 24 | 0 | 30 | 14461 | 1862 | 1948 | 5.05 |
