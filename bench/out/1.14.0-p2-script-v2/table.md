# BlockForge 1.14.0-p2-script-v2 benchmark

Lower is better. `mistakes` counts every check; `mistakes_ex_ow` leaves out overwritten blocks (scripts that fill then carve overwrite on purpose, so that column is mostly style).

| id | key | floating | removed | overwritten | buried_path | jump_steps | corner_turns | blocked_doors | wrong_facing | size_off | script_errors | fix_rounds | mistakes | mistakes_ex_ow | time_s | cost |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | cottage | 0 | 0 | 47 | 0 | 0 | 0 | 0 | 0 | 5 | 0 | 3 | 52 | 5 | 86 | 0.25 |
| 2 | machiya | 0 | 0 | 457 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 7 | 457 | 0 | 446 | 1.187 |
| 3 | stair_road | 0 | 0 | 7 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 5 | 8 | 1 | 271 | 0.694 |
| 4 | hill_castle | 0 | 2 | 3041 | 27 | 2 | 0 | 4 | 0 | 0 | 0 | 5 | 3076 | 35 | 672 | 1.615 |
| 5 | arch_bridge | 0 | 0 | 256 | 4 | 0 | 0 | 0 | 0 | 0 | 0 | 3 | 260 | 4 | 129 | 0.323 |
| 6 | round_tower | 0 | 4 | 4 | 16 | 0 | 0 | 0 | 0 | 1 | 0 | 5 | 25 | 21 | 526 | 1.336 |
| 7 | village_street | 0 | 0 | 653 | 15 | 0 | 0 | 0 | 0 | 1 | 0 | 3 | 669 | 16 | 347 | 0.821 |
| 8 | grove | 0 | 0 | 521 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 521 | 0 | 125 | 0.263 |
| 9 | furnished_room | 0 | 0 | 4 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 3 | 4 | 0 | 86 | 0.272 |
| 10 | cottage_edit | 0 | 0 | 12 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 3 | 12 | 0 | 184 | 0.566 |
| total | | 0 | 6 | 5002 | 62 | 3 | 0 | 4 | 0 | 7 | 0 | 38 | 5084 | 82 | 2872 | 7.33 |

## 1.13.0-p1-v2 -> 1.14.0-p2-script-v2

| check | before | after | change |
|---|---|---|---|
| floating | 0 | 0 |  |
| removed | 4 | 6 | 50% |
| overwritten | 7766 | 5002 | -36% |
| buried_path | 67 | 62 | -7% |
| jump_steps | 2 | 3 | 50% |
| corner_turns | 0 | 0 |  |
| blocked_doors | 0 | 4 |  |
| wrong_facing | 0 | 0 |  |
| size_off | 29 | 7 | -76% |
| script_errors | 0 | 0 |  |
| fix_rounds | 48 | 38 | -21% |
| mistakes | 7868 | 5084 | -35% |
| mistakes_ex_ow | 102 | 82 | -20% |
| time_s | 2905 | 2872 | -1% |
| cost | 7.76 | 7.33 | -6% |
