# Lynn Recap

Mobile-friendly Burmese AI Movie Recap web app. Upload a video and the app attempts to run the complete automatic pipeline.

## Automatic workflow
1. Extract audio from the uploaded video with FFmpeg.
2. Generate a timestamped original-language transcript with Groq Whisper.
3. Export the original-language SRT.
4. Translate subtitle lines into conversational Burmese with a Groq chat model.
5. Generate Burmese narration clips using Microsoft Edge neural voice (default: `my-MM-NilarNeural`).
6. Assemble the narration, generate voice-timed Burmese SRT, and render an H.264 MP4 with optional burned-in subtitles.
7. Download the final MP4, original SRT, Burmese SRT, and Burmese voice MP3.

## Required Render environment variable
Set this in **Render Dashboard → your service → Environment**:
- `GROQ_API_KEY` — required API key from Groq. Do not commit the key into GitHub.

Optional settings:
- `GROQ_STT_MODEL` (default `whisper-large-v3`)
- `GROQ_TRANSLATE_MODEL` (default `llama-3.3-70b-versatile`)
- `MYANMAR_TTS_VOICE` (default `my-MM-NilarNeural`; try `my-MM-ThihaNeural` if available for your runtime)
- `MAX_UPLOAD_MB` (default `700`)
- `LYNN_DATA_DIR` (default `/tmp/lynn-recap`)

The Dockerfile installs FFmpeg and Noto fonts. After adding `GROQ_API_KEY`, save the Environment settings and redeploy the service.

## Render deployment
This repository includes a Dockerfile. The current Docker-based Render service should build from the repository root and use the Dockerfile. Health check path: `/api/health`.

## Important limitations
- Groq API usage and limits apply; very long audio may exceed transcription limits. This version stops with an explanatory error if the extracted MP3 exceeds 24 MB.
- Voice-timed subtitles follow generated narration timing. Narration may not match the original film pacing exactly, and `-shortest` can cut output to the shorter of video and narration.
- Job status and files use temporary local storage. Render restarts/redeploys may remove them; Cloudflare R2 and a durable background worker are not connected yet.
- This is an MVP; test short videos first before relying on long jobs.

## Local development
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export GROQ_API_KEY="your_key_here"
uvicorn app:app --reload
```
Open http://127.0.0.1:8000
