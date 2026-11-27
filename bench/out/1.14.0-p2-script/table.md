# BlockForge 1.14.0-p2-script benchmark

Lower is better. `mistakes` counts every check; `mistakes_ex_ow` leaves out overwritten blocks (scripts that fill then carve overwrite on purpose, so that column is mostly style).

| id | key | floating | removed | overwritten | buried_path | jump_steps | corner_turns | blocked_doors | wrong_facing | size_off | script_errors | fix_rounds | mistakes | mistakes_ex_ow | time_s | cost |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | cottage | 0 | 0 | 47 | 21 | 0 | 0 | 0 | 0 | 5 | 0 | 3 | 73 | 26 | 86 | 0.25 |
| 2 | machiya | 0 | 0 | 457 | 9 | 0 | 0 | 0 | 0 | 0 | 0 | 7 | 466 | 9 | 446 | 1.187 |
| 3 | stair_road | 0 | 0 | 7 | 8 | 6 | 0 | 0 | 0 | 0 | 0 | 5 | 21 | 14 | 271 | 0.694 |
| 4 | hill_castle | 0 | 2 | 3041 | 538 | 2 | 0 | 4 | 0 | 0 | 0 | 5 | 3587 | 546 | 672 | 1.615 |
| 5 | arch_bridge | 0 | 0 | 256 | 132 | 7 | 0 | 0 | 0 | 0 | 0 | 3 | 395 | 139 | 129 | 0.323 |
| 6 | round_tower | 0 | 4 | 4 | 323 | 22 | 0 | 0 | 0 | 1 | 0 | 5 | 354 | 350 | 526 | 1.336 |
| 7 | village_street | 0 | 0 | 653 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 3 | 654 | 1 | 347 | 0.821 |
| 8 | grove | 0 | 0 | 521 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 521 | 0 | 125 | 0.263 |
| 9 | furnished_room | 0 | 0 | 4 | 14 | 0 | 0 | 0 | 0 | 0 | 0 | 3 | 18 | 14 | 86 | 0.272 |
| 10 | cottage_edit | 0 | 0 | 12 | 26 | 0 | 0 | 0 | 0 | 0 | 0 | 3 | 38 | 26 | 184 | 0.566 |
| total | | 0 | 6 | 5002 | 1071 | 37 | 0 | 4 | 0 | 7 | 0 | 38 | 6127 | 1125 | 2872 | 7.33 |

## 1.13.0-p1 -> 1.14.0-p2-script

| check | before | after | change |
|---|---|---|---|
| floating | 0 | 0 |  |
| removed | 4 | 6 | 50% |
| overwritten | 7766 | 5002 | -36% |
| buried_path | 266 | 1071 | 303% |
| jump_steps | 10 | 37 | 270% |
| corner_turns | 0 | 0 |  |
| blocked_doors | 0 | 4 |  |
| wrong_facing | 0 | 0 |  |
| size_off | 29 | 7 | -76% |
| script_errors | 0 | 0 |  |
| fix_rounds | 48 | 38 | -21% |
| mistakes | 8075 | 6127 | -24% |
| mistakes_ex_ow | 309 | 1125 | 264% |
| time_s | 2905 | 2872 | -1% |
| cost | 7.76 | 7.33 | -6% |
