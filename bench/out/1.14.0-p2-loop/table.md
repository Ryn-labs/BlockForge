# BlockForge 1.14.0-p2-loop benchmark

Lower is better. `mistakes` counts every check; `mistakes_ex_ow` leaves out overwritten blocks (scripts that fill then carve overwrite on purpose, so that column is mostly style).

| id | key | floating | removed | overwritten | buried_path | jump_steps | corner_turns | blocked_doors | wrong_facing | size_off | script_errors | fix_rounds | mistakes | mistakes_ex_ow | time_s | cost |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | cottage | 0 | 0 | 236 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 236 | 0 | 56 | 0.264 |
| 2 | machiya | 0 | 0 | 541 | 4 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 545 | 4 | 155 | 0.572 |
| 3 | stair_road | 0 | 0 | 138 | 29 | 12 | 0 | 0 | 0 | 0 | 0 | 1 | 179 | 41 | 234 | 0.844 |
| 4 | hill_castle | 0 | 0 | 1826 | 91 | 1 | 0 | 0 | 0 | 0 | 0 | 1 | 1918 | 92 | 241 | 0.861 |
| 5 | arch_bridge | 0 | 0 | 543 | 65 | 2 | 0 | 0 | 0 | 0 | 0 | 1 | 610 | 67 | 102 | 0.498 |
| 6 | round_tower | 0 | 5 | 302 | 201 | 2 | 0 | 0 | 0 | 0 | 0 | 1 | 510 | 208 | 107 | 0.448 |
| 7 | village_street | 0 | 0 | 1037 | 17 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1054 | 17 | 98 | 0.426 |
| 8 | grove | 0 | 0 | 1806 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1806 | 0 | 39 | 0.221 |
| 9 | furnished_room | 0 | 1 | 374 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 375 | 1 | 61 | 0.277 |
| 10 | cottage_edit | 0 | 0 | 110 | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 3 | 113 | 3 | 137 | 0.402 |
| total | | 0 | 6 | 6913 | 410 | 17 | 0 | 0 | 0 | 0 | 0 | 12 | 7346 | 433 | 1230 | 4.81 |

## 1.13.0-p1 -> 1.14.0-p2-loop

| check | before | after | change |
|---|---|---|---|
| floating | 0 | 0 |  |
| removed | 4 | 6 | 50% |
| overwritten | 7766 | 6913 | -11% |
| buried_path | 266 | 410 | 54% |
| jump_steps | 10 | 17 | 70% |
| corner_turns | 0 | 0 |  |
| blocked_doors | 0 | 0 |  |
| wrong_facing | 0 | 0 |  |
| size_off | 29 | 0 | -100% |
| script_errors | 0 | 0 |  |
| fix_rounds | 48 | 12 | -75% |
| mistakes | 8075 | 7346 | -9% |
| mistakes_ex_ow | 309 | 433 | 40% |
| time_s | 2905 | 1230 | -58% |
| cost | 7.76 | 4.81 | -38% |
