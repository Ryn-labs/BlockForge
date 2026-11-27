# The builder improves its own work

Rule: check -> fix -> check, until there are 0 check problems and the quality score is at least `quality.QUALITY_MIN`
(60). Nothing is handed to the user with problems that nobody tried to fix. The shared code is `blockforge/selfimprove.py`
(`assess`, `improve_message`, `hand_back`, `not_done_text`); the two limits are `CHAT_ROUNDS = 3` and `LOOP_ROUNDS = 2`.

## The three paths

| Path | What happens |
|---|---|
| Chat panel (`chat.py`) | After every AI turn that changed blocks the server runs `checks.run` and `quality.score` on the session. If anything is off it starts an improvement turn by itself, up to 3 rounds per user request. Each round puts the status line "Improving: <weakest item>, round k of 3" in the panel and is saved as a version. The AI gets a focused message: the findings grouped by kind with coordinates, the 3 weakest quality parts with their fixes, "fix these, change nothing else, then check". The last message to the user says what got fixed, with before/after numbers. If the rounds run out it says what is still open and shows a "Keep improving" button (`POST /api/chat/<id>/improve`, 3 more rounds). Pause stops the rounds too. |
| Step-by-step engine (`loop.py`) | The prompt (SKILL.md "The loop") says check -> fix -> check. After the AI ends, the session is looked at again; with problems or quality under the minimum it runs up to 2 more `claude -p` turns (same system prompt, the findings as the message) before the build is saved. A build saved earlier in the run is replaced by the improved one. |
| MCP one-shot tools (`mcp_server.py`) | `create_build` and `update_build` check the result. A build with problems or low quality answers "NOT DONE YET - improve before you show the user:" + the findings with coordinates + the weakest quality parts + "call update_build with the fixes". Only a clean build starts with "Done.". The session tool `check` uses the same words. `get_build_guide` carries the rule. |

Quality only counts in the chat once the plan is finished (a half-built house has no roof yet); check problems always count.
"Keep improving" counts quality at once.

## Real run

Temp data dir, port 8799, the real AI (`claude -p` through the chat panel API), prompt "a small stone house". The AI made
no plan, so quality counted straight after its first turn. Numbers are `checks.run` and `quality.score` on each version's
snapshot.

| Step | Version | Blocks | Check problems | Quality |
|---|---|---|---|---|
| Before (the AI's own turn) | v2 | 575 | 0 | 35 |
| Round 1 ("Improving: detail, round 1 of 3") | v3 | 804 | 0 | 71 |
| Round 2 | not needed | | | |
| Round 3 | not needed | | | |

Message the user got: "Quality 35 -> 71 (roof, detail, massing). It is clean now: no check problems, quality 71."
Round 1 took about 50 seconds. This run had no check problems to fix, so only the quality part was exercised for real;
the check-problem path (and the 3-round cap) is covered by the unit tests in `tests/test_self_improve.py`.
