# BlockForge 1.14.0-p2-loop-v2 benchmark

Lower is better. `mistakes` counts every check; `mistakes_ex_ow` leaves out overwritten blocks (scripts that fill then carve overwrite on purpose, so that column is mostly style).

| id | key | floating | removed | overwritten | buried_path | jump_steps | corner_turns | blocked_doors | wrong_facing | size_off | script_errors | fix_rounds | mistakes | mistakes_ex_ow | time_s | cost |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | cottage | 0 | 0 | 236 | 4 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 240 | 4 | 56 | 0.264 |
| 2 | machiya | 0 | 0 | 541 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 541 | 0 | 155 | 0.572 |
| 3 | stair_road | 0 | 0 | 138 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 138 | 0 | 234 | 0.844 |
| 4 | hill_castle | 0 | 0 | 1826 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1826 | 0 | 241 | 0.861 |
| 5 | arch_bridge | 0 | 0 | 543 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 543 | 0 | 102 | 0.498 |
| 6 | round_tower | 0 | 5 | 302 | 0 | 2 | 0 | 0 | 0 | 0 | 0 | 1 | 309 | 7 | 107 | 0.448 |
| 7 | village_street | 0 | 0 | 1037 | 5 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1042 | 5 | 98 | 0.426 |
| 8 | grove | 0 | 0 | 1806 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1806 | 0 | 39 | 0.221 |
| 9 | furnished_room | 0 | 1 | 374 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 375 | 1 | 61 | 0.277 |
| 10 | cottage_edit | 0 | 0 | 110 | 4 | 0 | 0 | 0 | 0 | 0 | 0 | 3 | 114 | 4 | 137 | 0.402 |
| total | | 0 | 6 | 6913 | 13 | 2 | 0 | 0 | 0 | 0 | 0 | 12 | 6934 | 21 | 1230 | 4.81 |

## 1.13.0-p1-v2 -> 1.14.0-p2-loop-v2

| check | before | after | change |
|---|---|---|---|
| floating | 0 | 0 |  |
| removed | 4 | 6 | 50% |
| overwritten | 7766 | 6913 | -11% |
| buried_path | 67 | 13 | -81% |
| jump_steps | 2 | 2 | 0% |
| corner_turns | 0 | 0 |  |
| blocked_doors | 0 | 0 |  |
| wrong_facing | 0 | 0 |  |
| size_off | 29 | 0 | -100% |
| script_errors | 0 | 0 |  |
| fix_rounds | 48 | 12 | -75% |
| mistakes | 7868 | 6934 | -12% |
| mistakes_ex_ow | 102 | 21 | -79% |
| time_s | 2905 | 1230 | -58% |
| cost | 7.76 | 4.81 | -38% |
