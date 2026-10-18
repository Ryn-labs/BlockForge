"""Download Flint's HD voice (Piper TTS + the CC0 "Joe" voice) into blockforge/voice/.
Needed once before building the installer; the files are too big for the git repo."""
import io
import os
import shutil
import urllib.request
import zipfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
VOICE = os.path.join(ROOT, "blockforge", "voice")
PIPER_ZIP = "https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_windows_amd64.zip"
MODEL = "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/joe/medium/en_US-joe-medium.onnx"


def fetch(url):
    print("Downloading", url)
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "BlockForge-build"})) as r:
        return r.read()


def main():
    os.makedirs(VOICE, exist_ok=True)
    if not os.path.isfile(os.path.join(VOICE, "piper", "piper.exe")):
        with zipfile.ZipFile(io.BytesIO(fetch(PIPER_ZIP))) as z:
            z.extractall(VOICE)                     # creates voice/piper/
        shutil.rmtree(os.path.join(VOICE, "piper", "pkgconfig"), ignore_errors=True)
    for suffix in ("", ".json"):
        path = os.path.join(VOICE, "en_US-joe-medium.onnx" + suffix)
        if not os.path.isfile(path):
            with open(path, "wb") as f:
                f.write(fetch(MODEL + suffix))
    print("Voice ready in", VOICE)


if __name__ == "__main__":
    main()
