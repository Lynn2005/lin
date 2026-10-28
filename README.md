# Lynn Recap

Mobile-friendly Burmese AI Movie Recap web app MVP.

## Current MVP features
- Upload a source video (MP4/MOV/MKV/WEBM)
- Upload a manually translated Burmese subtitle `.srt`
- Upload an already-generated narration audio track
- Render an H.264 MP4 using FFmpeg and optionally burn in subtitles
- Job status polling and final MP4 download
- FastAPI health endpoint at `/api/health`

## Render deployment
The included `render.yaml` describes a Python web service. If the existing Render service does not use Blueprint settings, configure it manually:
- **Build command:** `pip install -r requirements.txt && (apt-get update && apt-get install -y ffmpeg fonts-noto-core || true)`
- **Start command:** `uvicorn app:app --host 0.0.0.0 --port $PORT`
- **Health check path:** `/api/health`

## Important limitations
This is an early MVP, not production-ready:
- Video URL import is shown in the UI but is not implemented yet.
- AI TTS/STT providers are not connected; narration audio must be uploaded.
- Job metadata and output files use temporary local storage. Render restarts/redeploys may remove them.
- Cloudflare R2 persistent storage, durable queue/worker, authentication, and robust large-file direct uploads still need to be added.
- Render's free service may sleep or time out on long videos. FFmpeg must be available in the runtime.
- When voice audio is provided, this version replaces the source audio and uses `-shortest`; narration timing/length must be checked before using long videos.

## Local development
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --reload
```
Open http://127.0.0.1:8000
