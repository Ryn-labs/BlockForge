"""ElevenLabs text-to-speech for Flint (optional: needs the user's own ElevenLabs API key)."""
import hashlib
import json
import os
import urllib.error
import urllib.request

from . import store, tts

BASE = os.environ.get("BLOCKFORGE_ELEVEN_BASE", "https://api.elevenlabs.io")
MODELS = {
    "eleven_flash_v2_5": "Flash v2.5 (fast, cheapest, recommended)",
    "eleven_turbo_v2_5": "Turbo v2.5 (fast, better quality)",
    "eleven_multilingual_v2": "Multilingual v2 (most natural)",
    "eleven_v3": "v3 (most expressive)",
}
MAX_CHARS = 350                                         # keep each line cheap


class ElevenError(Exception):
    pass


def _cfg():
    c = store.load_settings().get("eleven") or {}
    if not c.get("api_key"):
        raise ElevenError("Add your ElevenLabs API key in Settings → Guide.")
    return c


def _friendly(code, body):
    try:
        d = json.loads(body).get("detail", {})
        status = d.get("status") if isinstance(d, dict) else None
        msg = d.get("message") if isinstance(d, dict) else str(d)
    except ValueError:
        status, msg = None, body[:200]
    if status == "quota_exceeded" or code == 402:
        return "You've used all your ElevenLabs credits for now, so Flint is using his offline voice."
    if code in (401, 403) or status in ("invalid_api_key", "missing_permissions"):
        extra = " (the key needs the 'Text to Speech' and 'Voices: read' permissions)" if status == "missing_permissions" else ""
        return f"ElevenLabs rejected the API key{extra}: {msg or code}"
    if code == 429:
        return "ElevenLabs is busy (too many requests at once). Try again in a moment."
    if code == 404:
        return "ElevenLabs doesn't know that voice. Pick another in Settings → Guide."
    return f"ElevenLabs error {code}: {(msg or body)[:200]}"


def _call(path, key, body=None, accept="application/json", timeout=60):
    headers = {"xi-api-key": key, "Accept": accept, "User-Agent": "BlockForge"}
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method="POST" if data else "GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        raise ElevenError(_friendly(e.code, e.read().decode("utf-8", "replace")))
    except urllib.error.URLError as e:
        raise ElevenError(f"Couldn't reach ElevenLabs: {e.reason}")


def list_voices():
    key = _cfg()["api_key"]
    try:
        raw = _call("/v2/voices?page_size=100", key)
    except ElevenError:
        raw = _call("/v1/voices", key)
    out = []
    for v in json.loads(raw).get("voices", []):
        lab = v.get("labels") or {}
        extra = ", ".join(x for x in (lab.get("gender"), lab.get("accent"), lab.get("descriptive") or lab.get("use_case")) if x)
        out.append({"id": v.get("voice_id"), "name": v.get("name", "?"), "category": v.get("category") or "other",
                    "info": extra})
    out.sort(key=lambda v: (v["category"] != "cloned" and v["category"] != "generated", v["category"], v["name"]))
    return out


def usage():
    """Credits used / limit, or None if the key can't read the subscription."""
    try:
        d = json.loads(_call("/v1/user/subscription", _cfg()["api_key"], timeout=20))
    except ElevenError:
        return None
    return {"used": d.get("character_count"), "limit": d.get("character_limit"), "tier": d.get("tier"),
            "reset": d.get("next_character_count_reset_unix")}


def speak(text, voice_id=None, model=None, speed=1.0):
    """MP3 bytes for one line. Cached on disk so a repeated line never costs credits twice."""
    c = _cfg()
    voice_id = voice_id or c.get("voice_id")
    if not voice_id:
        raise ElevenError("Pick an ElevenLabs voice in Settings → Guide (click Load voices).")
    model = model if model in MODELS else (c.get("model") if c.get("model") in MODELS else "eleven_flash_v2_5")
    text = " ".join(str(text).split())
    if len(text) > MAX_CHARS:
        cut = text[:MAX_CHARS]
        text = cut[:max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))].strip() or cut
    if not text:
        raise ElevenError("nothing to say")
    speed = min(1.2, max(0.7, float(speed or 1.0)))
    key = hashlib.sha1(f"eleven|{voice_id}|{model}|{speed:.2f}|{text}".encode("utf-8")).hexdigest()
    os.makedirs(tts.CACHE, exist_ok=True)
    path = os.path.join(tts.CACHE, key + ".mp3")
    if not os.path.isfile(path):
        body = {"text": text, "model_id": model,
                "voice_settings": {"stability": 0.5, "similarity_boost": 0.75, "style": 0.0, "use_speaker_boost": True,
                                   "speed": speed}}
        audio = _call(f"/v1/text-to-speech/{voice_id}?output_format=mp3_44100_64", c["api_key"], body,
                      accept="audio/mpeg", timeout=90)
        if len(audio) < 200:
            raise ElevenError("ElevenLabs sent back an empty sound.")
        with open(path, "wb") as f:
            f.write(audio)
        tts.trim_cache()
    with open(path, "rb") as f:
        return f.read()
