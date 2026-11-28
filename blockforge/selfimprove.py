"""Self-improvement: after the AI changes a build, look at the check problems and the quality score and, if anything is off,
turn them into a focused "fix these" message. Shared by the chat panel, the step-by-step engine and the MCP tools.

assess(blocks) -> {"found", "problems", "by_check", "q", "qtotal", "low_quality", "ok"}
The loop is always: check -> fix -> check, until 0 problems and quality >= QUALITY_MIN (or the rounds are used up)."""
from . import checks, quality

CHAT_ROUNDS = 3                 # improvement rounds per user request in the chat panel
LOOP_ROUNDS = 2                 # extra turns of the step-by-step engine before it saves
SHOW = 6                        # findings listed per check kind in a message


def assess(blocks, ground=None, terrain_blocks=None, size=None, with_quality=True, prompt=None, found=None, q=None):
    """Checks plus quality of `blocks`. with_quality=False leaves quality out of the verdict (a build that is not finished).
    prompt = what was asked or the build's title (a small cottage may have one storey, a dark/gothic build may be dark).
    found / q = checks.run / quality.score of these blocks when the caller has them already (a session caches them)."""
    blocks = blocks or {}
    if found is None:
        found = checks.run(blocks, ground=ground) if blocks else []
    if not (blocks and with_quality):
        q = None
    elif q is None:
        q = quality.score(quality.built_only(blocks, terrain_blocks), size, prompt)
    qtotal = q["total"] if q and q.get("building") else None
    low = qtotal is not None and qtotal < quality.QUALITY_MIN
    return {"found": found, "problems": checks.total(found), "by_check": checks.counts(found), "q": q, "qtotal": qtotal,
            "low_quality": low, "ok": not found and not low}


def _by_check_text(a):
    return ", ".join(f"{checks.CHECK_LABELS.get(k, k)} {v}" for k, v in a["by_check"].items())


def findings_lines(a, show=SHOW):
    """The check findings grouped by kind, with coordinates."""
    out = []
    groups = {}
    for f in a["found"]:
        groups.setdefault(f["check"], []).append(f)
    for k, fs in groups.items():
        out.append(f"{checks.CHECK_LABELS.get(k, k)} ({a['by_check'][k]}):")
        out += ["- " + f["text"] for f in fs[:show]]
        if a["by_check"][k] > min(len(fs), show):
            out.append(f"- ...and {a['by_check'][k] - min(len(fs), show)} more of the same kind (call check to list them).")
    return out


def quality_lines(a, n=3):
    out = []
    if a["q"] and a["q"].get("building"):
        for k, v, fix in quality.weakest(a["q"], n):
            out.append(f"- {quality.LABELS[k]} {v}/100: " + (" ".join(fix[:2]) if fix else "improve it."))
    return out


def weakest_item(a):
    """The plain name of the thing to fix first (for the status line)."""
    if a["by_check"]:
        k = max(a["by_check"], key=lambda x: a["by_check"][x])
        return checks.CHECK_LABELS.get(k, k)
    if a["low_quality"]:
        return quality.LABELS[quality.weakest(a["q"], 1)[0][0]].lower()
    return "the build"


def status_line(a, k, n):
    return f"Improving: {weakest_item(a)}, round {k} of {n}"


def improve_message(a, k=None, n=None):
    """The focused message for one improvement turn."""
    head = "Automatic improvement" + (f" round {k} of {n}" if k else "") + ". Your last step left things to fix."
    out = [head]
    if a["found"]:
        out += ["", f"Check problems ({a['problems']}):"] + findings_lines(a)
    if a["low_quality"]:
        out += ["", f"Quality {a['qtotal']}/100, the minimum is {quality.QUALITY_MIN}. The weakest parts and their fixes:"]
        out += quality_lines(a)
    out += ["", "Fix these, change nothing else (no new parts, keep the size and the style), then call check again. "
                "Use pattern() for proven parts. Stop only when check says no problems."]
    return "\n".join(out)


def _quality_words(first, last):
    """The quality parts that improved most, as plain words."""
    if not (first["q"] and last["q"] and first["q"].get("building") and last["q"].get("building")):
        return ""
    gains = sorted(((last["q"]["parts"].get(k, 0) - v, k) for k, v in first["q"]["parts"].items()), reverse=True)
    names = [quality.LABELS[k].lower() for g, k in gains[:3] if g > 0]
    return f" ({', '.join(names)})" if names else ""


def hand_back(first, last, rounds, max_rounds):
    """(text, done). The sentence for the user after the improvement rounds: what got fixed, what is still open."""
    bits = []
    fixed = first["problems"] - last["problems"]
    if first["problems"]:
        if fixed > 0:
            gone = {k: v - last["by_check"].get(k, 0) for k, v in first["by_check"].items() if v > last["by_check"].get(k, 0)}
            words = ", ".join(f"{checks.CHECK_LABELS.get(k, k)} {v}" for k, v in gone.items())
            bits.append(f"Fixed {fixed} check problem{'s' if fixed != 1 else ''}" + (f" ({words})" if words else ""))
        else:
            bits.append("The check problems could not be fixed")
    if first["qtotal"] is not None and last["qtotal"] is not None and (first["low_quality"] or last["qtotal"] != first["qtotal"]):
        bits.append(f"quality {first['qtotal']} -> {last['qtotal']}" + _quality_words(first, last))
    text = ("; ".join(bits) if bits else "Improved it") + "."
    text = text[0].upper() + text[1:]
    if last["ok"]:
        return text + " It is clean now: no check problems" + (f", quality {last['qtotal']}." if last["qtotal"] is not None else "."), True
    left = []
    if last["problems"]:
        left.append(f"{last['problems']} check problems still open ({_by_check_text(last)})")
    if last["low_quality"]:
        left.append(f"quality {last['qtotal']} is still under {quality.QUALITY_MIN} (weakest: "
                    + ", ".join(quality.LABELS[k].lower() for k, _v, _f in quality.weakest(last["q"], 3)) + ")")
    return (text + f" I used all {max_rounds} rounds and this is still open: " + "; ".join(left)
            + ". Press \"Keep improving\" and I will go on."), False


def not_done_text(a, what="build", fix_call="update_build"):
    """For the one-shot MCP tools and check(): the NOT DONE YET block, or None when the build is clean."""
    if a["ok"]:
        return None
    out = ["NOT DONE YET - improve before you show the user:"]
    if a["found"]:
        out += [f"{a['problems']} check problems ({_by_check_text(a)}):"]
        out += findings_lines(a)
    if a["low_quality"]:
        out += [f"Quality {a['qtotal']}/100, the minimum is {quality.QUALITY_MIN}. Weakest parts:"] + quality_lines(a)
    out.append(f"Call {fix_call} with the fixes (only the changes), then check again. Repeat until the {what} is clean; "
               "never hand over a build that still has problems.")
    return "\n".join(out)
