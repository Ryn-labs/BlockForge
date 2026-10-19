"""Flint's HD voice: offline neural text-to-speech with Piper (engine bundled in blockforge/voice/)."""
import hashlib
import os
import subprocess
import tempfile
import threading

from . import store, voices

HERE = os.path.dirname(os.path.abspath(__file__))
VOICE_DIR = os.path.join(HERE, "voice")
PIPER = os.path.join(VOICE_DIR, "piper", "piper.exe")
CACHE = os.path.join(store.DATA, "tts_cache")
_lock = threading.Lock()


def available():
    return os.path.isfile(PIPER) and bool(voices.installed())


def speak(text, voice="joe", speed=1.0):
    """Return WAV bytes for text. Results are cached so repeated lines are instant."""
    text = " ".join(str(text).split())[:600]
    if not text:
        raise ValueError("nothing to say")
    model = voices.path(voice) or voices.path("joe") or next(iter(filter(None, (voices.path(v) for v in voices.CATALOG))), None)
    if not (os.path.isfile(PIPER) and model):
        raise FileNotFoundError("HD voice isn't installed")
    speed = min(1.6, max(0.5, float(speed or 1.0)))
    key = hashlib.sha1(f"{os.path.basename(model)}|{speed:.2f}|{text}".encode("utf-8")).hexdigest()
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, key + ".wav")
    if not os.path.isfile(path):
        with _lock:                                   # one synthesis at a time keeps CPU use low
            fd, tmp = tempfile.mkstemp(suffix=".wav", dir=CACHE)
            os.close(fd)
            r = subprocess.run([PIPER, "--model", model, "--output_file", tmp, "--length_scale", f"{1 / speed:.3f}",
                                "--sentence_silence", "0.15"],
                               input=text.encode("utf-8"), capture_output=True, timeout=60, cwd=os.path.dirname(PIPER),
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if r.returncode != 0 or os.path.getsize(tmp) < 100:
                os.remove(tmp)
                raise RuntimeError("voice failed: " + r.stderr.decode("utf-8", "replace")[-300:])
            os.replace(tmp, path)
            trim_cache()
    with open(path, "rb") as f:
        return f.read()


def trim_cache(keep=400):
    try:
        files = sorted((os.path.join(CACHE, f) for f in os.listdir(CACHE) if f.endswith((".wav", ".mp3"))),
                       key=os.path.getmtime)
        for f in files[:-keep]:
            os.remove(f)
    except OSError:
        pass
