# Third-party voice components

BlockForge's HD voice for Flint runs fully offline using these components:

| Component | Licence | Source |
|---|---|---|
| Piper TTS 2023.11.14-2 (`piper.exe`, `piper_phonemize.dll`) | MIT | https://github.com/rhasspy/piper |
| eSpeak NG (`espeak-ng.dll`, `espeak-ng-data/`) | GPL-3.0-or-later | https://github.com/espeak-ng/espeak-ng |
| ONNX Runtime (`onnxruntime*.dll`) | MIT | https://github.com/microsoft/onnxruntime |
| Voice model `en_US-joe-medium` | Model: MIT (piper-voices); dataset: CC0 | https://huggingface.co/rhasspy/piper-voices/tree/v1.0.0/en/en_US/joe/medium |

eSpeak NG is distributed unmodified. Its complete source code is available at the link above.

## Optional voices (downloaded on demand, not bundled)

Flint's settings can download more voices from https://huggingface.co/rhasspy/piper-voices when the user clicks
Download. They are only offered if their licence allows free use:

| Voice | Licence |
|---|---|
| Bryce, Norman, John, Kristin, Linda (LJSpeech) | Public domain |
| Kathleen | CC0 |
| Sam | Apache 2.0 |
| Alba (Scottish female) | CC BY 4.0, credit: Alba voice dataset, University of Edinburgh CSTR |

## ElevenLabs (optional)

If the user adds their own ElevenLabs API key, Flint's lines are sent to ElevenLabs (https://elevenlabs.io) for speech.
Nothing is sent unless a key is set, and the key is stored only on the user's PC.
