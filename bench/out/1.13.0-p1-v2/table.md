# BlockForge 1.13.0-p1-v2 benchmark

Lower is better. `mistakes` counts every check; `mistakes_ex_ow` leaves out overwritten blocks (scripts that fill then carve overwrite on purpose, so that column is mostly style).

| id | key | floating | removed | overwritten | buried_path | jump_steps | corner_turns | blocked_doors | wrong_facing | size_off | script_errors | fix_rounds | mistakes | mistakes_ex_ow | time_s | cost |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | cottage | 0 | 0 | 57 | 0 | 0 | 0 | 0 | 0 | 5 | 0 | 5 | 62 | 5 | 130 | 0.456 |
| 2 | machiya | 0 | 0 | 512 | 0 | 0 | 0 | 0 | 0 | 8 | 0 | 5 | 520 | 8 | 344 | 0.891 |
| 3 | stair_road | 0 | 0 | 11 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 5 | 11 | 0 | 270 | 0.691 |
| 4 | hill_castle | 0 | 3 | 4563 | 0 | 0 | 0 | 0 | 0 | 8 | 0 | 5 | 4574 | 11 | 579 | 1.492 |
| 5 | arch_bridge | 0 | 0 | 1265 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 3 | 1266 | 1 | 251 | 0.607 |
| 6 | round_tower | 0 | 0 | 33 | 0 | 2 | 0 | 0 | 0 | 0 | 0 | 7 | 35 | 2 | 517 | 1.203 |
| 7 | village_street | 0 | 0 | 1136 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 5 | 1136 | 0 | 337 | 0.906 |
| 8 | grove | 0 | 0 | 85 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 3 | 85 | 0 | 112 | 0.338 |
| 9 | furnished_room | 0 | 1 | 81 | 0 | 0 | 0 | 0 | 0 | 7 | 0 | 5 | 89 | 8 | 109 | 0.37 |
| 10 | cottage_edit | 0 | 0 | 23 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 5 | 23 | 0 | 256 | 0.802 |
| total | | 0 | 4 | 7766 | 0 | 2 | 0 | 0 | 0 | 29 | 0 | 48 | 7801 | 35 | 2905 | 7.76 |

## 1.12.0-v2 -> 1.13.0-p1-v2

| check | before | after | change |
|---|---|---|---|
| floating | 32 | 0 | -100% |
| removed | 16 | 4 | -75% |
| overwritten | 12599 | 7766 | -38% |
| buried_path | 2 | 0 | -100% |
| jump_steps | 123 | 2 | -98% |
| corner_turns | 16 | 0 | -100% |
| blocked_doors | 0 | 0 |  |
| wrong_facing | 1 | 0 | -100% |
| size_off | 24 | 29 | 21% |
| script_errors | 0 | 0 |  |
| fix_rounds | 30 | 48 | 60% |
| mistakes | 12813 | 7801 | -39% |
| mistakes_ex_ow | 214 | 35 | -84% |
| time_s | 1948 | 2905 | 49% |
| cost | 5.05 | 7.76 | 54% |
