# BlockForge 1.13.0-p1 benchmark

Lower is better. `mistakes` counts every check; `mistakes_ex_ow` leaves out overwritten blocks (scripts that fill then carve overwrite on purpose, so that column is mostly style).

| id | key | floating | removed | overwritten | buried_path | jump_steps | corner_turns | blocked_doors | wrong_facing | size_off | script_errors | fix_rounds | mistakes | mistakes_ex_ow | time_s | cost |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | cottage | 0 | 0 | 57 | 10 | 0 | 0 | 0 | 0 | 5 | 0 | 5 | 72 | 15 | 130 | 0.456 |
| 2 | machiya | 0 | 0 | 512 | 0 | 0 | 0 | 0 | 0 | 8 | 0 | 5 | 520 | 8 | 344 | 0.891 |
| 3 | stair_road | 0 | 0 | 11 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 5 | 11 | 0 | 270 | 0.691 |
| 4 | hill_castle | 0 | 3 | 4563 | 34 | 0 | 0 | 0 | 0 | 8 | 0 | 5 | 4608 | 45 | 579 | 1.492 |
| 5 | arch_bridge | 0 | 0 | 1265 | 48 | 8 | 0 | 0 | 0 | 1 | 0 | 3 | 1322 | 57 | 251 | 0.607 |
| 6 | round_tower | 0 | 0 | 33 | 157 | 2 | 0 | 0 | 0 | 0 | 0 | 7 | 192 | 159 | 517 | 1.203 |
| 7 | village_street | 0 | 0 | 1136 | 13 | 0 | 0 | 0 | 0 | 0 | 0 | 5 | 1149 | 13 | 337 | 0.906 |
| 8 | grove | 0 | 0 | 85 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 3 | 85 | 0 | 112 | 0.338 |
| 9 | furnished_room | 0 | 1 | 81 | 0 | 0 | 0 | 0 | 0 | 7 | 0 | 5 | 89 | 8 | 109 | 0.37 |
| 10 | cottage_edit | 0 | 0 | 23 | 4 | 0 | 0 | 0 | 0 | 0 | 0 | 5 | 27 | 4 | 256 | 0.802 |
| total | | 0 | 4 | 7766 | 266 | 10 | 0 | 0 | 0 | 29 | 0 | 48 | 8075 | 309 | 2905 | 7.76 |

## 1.12.0 -> 1.13.0-p1

| check | before | after | change |
|---|---|---|---|
| floating | 32 | 0 | -100% |
| removed | 16 | 4 | -75% |
| overwritten | 12599 | 7766 | -38% |
| buried_path | 1645 | 266 | -84% |
| jump_steps | 128 | 10 | -92% |
| corner_turns | 16 | 0 | -100% |
| blocked_doors | 0 | 0 |  |
| wrong_facing | 1 | 0 | -100% |
| size_off | 24 | 29 | 21% |
| script_errors | 0 | 0 |  |
| fix_rounds | 30 | 48 | 60% |
| mistakes | 14461 | 8075 | -44% |
| mistakes_ex_ow | 1862 | 309 | -83% |
| time_s | 1948 | 2905 | 49% |
| cost | 5.05 | 7.76 | 54% |
