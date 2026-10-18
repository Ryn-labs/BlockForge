"""Flint's HD voice: offline neural text-to-speech with Piper (bundled in blockforge/voice/)."""
import hashlib
import os
import subprocess
import tempfile
import threading

from . import store

HERE = os.path.dirname(os.path.abspath(__file__))
VOICE_DIR = os.path.join(HERE, "voice")
PIPER = os.path.join(VOICE_DIR, "piper", "piper.exe")
VOICES = {"joe": ("en_US-joe-medium.onnx", "Joe (US, young male)")}
CACHE = os.path.join(store.DATA, "tts_cache")
_lock = threading.Lock()


def available():
    return os.path.isfile(PIPER) and any(os.path.isfile(os.path.join(VOICE_DIR, f)) for f, _ in VOICES.values())


def voices():
    return {k: label for k, (f, label) in VOICES.items() if os.path.isfile(os.path.join(VOICE_DIR, f))}


def speak(text, voice="joe", speed=1.0):
    """Return WAV bytes for text. Results are cached so repeated lines are instant."""
    text = " ".join(str(text).split())[:600]
    if not text:
        raise ValueError("nothing to say")
    model_file = VOICES.get(voice, VOICES["joe"])[0]
    model = os.path.join(VOICE_DIR, model_file)
    if not (os.path.isfile(PIPER) and os.path.isfile(model)):
        raise FileNotFoundError("HD voice isn't installed")
    speed = min(1.6, max(0.6, float(speed or 1.0)))
    key = hashlib.sha1(f"{voice}|{speed:.2f}|{text}".encode("utf-8")).hexdigest()
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
            _trim_cache()
    with open(path, "rb") as f:
        return f.read()


def _trim_cache(keep=400):
    try:
        files = sorted((os.path.join(CACHE, f) for f in os.listdir(CACHE) if f.endswith(".wav")), key=os.path.getmtime)
        for f in files[:-keep]:
            os.remove(f)
    except OSError:
        pass
