# BlockForge 1.15.0-bc benchmark

Lower is better. `mistakes` counts every check; `mistakes_ex_ow` leaves out overwritten blocks (scripts that fill then carve overwrite on purpose, so that column is mostly style).

| id | key | floating | removed | overwritten | buried_path | jump_steps | corner_turns | blocked_doors | wrong_facing | size_off | script_errors | fix_rounds | mistakes | mistakes_ex_ow | time_s | cost |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | cottage | 0 | 0 | 196 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 196 | 0 | 48 | 0.316 |
| 2 | machiya | 0 | 0 | 921 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 921 | 0 | 148 | 0.672 |
| 4 | hill_castle | 0 | 0 | 921 | 0 | 0 | 0 | 0 | 0 | 40 | 0 | 1 | 961 | 40 | 243 | 0.957 |
| 6 | round_tower | 0 | 0 | 196 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 196 | 0 | 102 | 0.547 |
| 9 | furnished_room | 0 | 0 | 334 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 334 | 0 | 49 | 0.249 |
| total | | 0 | 0 | 2568 | 0 | 0 | 0 | 0 | 0 | 40 | 0 | 5 | 2608 | 40 | 590 | 2.74 |

## 1.14.0-p2-loop-v2 -> 1.15.0-bc

| check | before | after | change |
|---|---|---|---|
| floating | 0 | 0 |  |
| removed | 6 | 0 | -100% |
| overwritten | 6913 | 2568 | -63% |
| buried_path | 13 | 0 | -100% |
| jump_steps | 2 | 0 | -100% |
| corner_turns | 0 | 0 |  |
| blocked_doors | 0 | 0 |  |
| wrong_facing | 0 | 0 |  |
| size_off | 0 | 40 |  |
| script_errors | 0 | 0 |  |
| fix_rounds | 12 | 5 | -58% |
| mistakes | 6934 | 2608 | -62% |
| mistakes_ex_ow | 21 | 40 | 90% |
| time_s | 1230 | 590 | -52% |
| cost | 4.81 | 2.74 | -43% |
