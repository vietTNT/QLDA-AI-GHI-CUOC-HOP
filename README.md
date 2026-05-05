# AI Meeting Minutes Backend

Local FastAPI backend for CPU-based meeting-minutes processing.

## Run

From Git Bash:

```bash
cd /d/Code/code_QLDA
source .venv/Scripts/activate
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Open:

```text
http://127.0.0.1:8000
http://127.0.0.1:8000/docs
```

The root page is the meeting recorder UI. It records microphone audio in the browser, sends the audio to FastAPI, and renders transcript, speaker segments, translation, and summary.

## Endpoints

- `GET /health` checks API and local model folders.
- `GET /models/status` lists local model availability.
- `POST /api/transcribe` uploads audio and returns STT segments.
- `POST /api/diarize` uploads audio and returns speaker segments.
- `POST /api/process` runs the meeting pipeline.
- `POST /api/translate` translates text with local Helsinki-NLP models.
- `POST /api/summarize` summarizes text with local BART.

## UI Flow

- Open `http://127.0.0.1:8000`.
- Press `Record` and allow microphone access.
- Press `Stop`.
- Press `Process`.
- Review transcript, speakers, translation, and summary.
- After diarization finishes, type real names in the speaker label fields to rename `SPEAKER_00`, `SPEAKER_01`, etc. The visible summary, transcript, action items, and copied output use those labels.

## Notes

- Inference is configured for CPU.
- STT uses `models/stt/PhoWhisper-medium-ct2-int8`.
- Diarization uses local pyannote and preloads audio waveform to avoid direct `torchcodec` decoding on Windows.
- FFmpeg is resolved from `FFMPEG_BINARY`, PATH, local WinGet installs, or the bundled `imageio-ffmpeg` package.
- LLM refinement uses local Ollama. Defaults:
  - `OLLAMA_BASE_URL=http://127.0.0.1:11434`
  - `OLLAMA_MODEL=qwen3.5:9b`
- When LLM is enabled, the app first asks Ollama to correct likely Vietnamese ASR errors in the transcript before translation, summary, and meeting-minutes generation. The original ASR transcript is still returned in the API response as `original_transcript` when corrections change the text.
- Add project terms, names, and common phrases in the UI `Project context` field to help the local LLM correct ASR mistakes without inventing new meeting facts.
  - `OLLAMA_TIMEOUT_SECONDS=120`

## LLM Test

```bash
python scripts/test_ollama_llm.py
```

Debug endpoints:

```text
GET  /health/llm
POST /debug/llm-test
```
