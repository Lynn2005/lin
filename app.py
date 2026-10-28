from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import threading
import uuid
from pathlib import Path
from typing import Any

import edge_tts
from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from groq import Groq

APP_NAME = "Lynn Recap"
DATA_DIR = Path(os.getenv("LYNN_DATA_DIR", "/tmp/lynn-recap"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
JOBS: dict[str, dict[str, Any]] = {}
LOCK = threading.Lock()
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_MB", "700")) * 1024 * 1024
ALLOWED_VIDEO = {".mp4", ".mov", ".mkv", ".webm", ".m4v"}
ALLOWED_AUDIO = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"}
STT_MODEL = os.getenv("GROQ_STT_MODEL", "whisper-large-v3")
TRANSLATE_MODEL = os.getenv("GROQ_TRANSLATE_MODEL", "llama-3.3-70b-versatile")
MYANMAR_VOICE = os.getenv("MYANMAR_TTS_VOICE", "my-MM-NilarNeural")

app = FastAPI(title=APP_NAME, version="0.2.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST"], allow_headers=["*"])

PAGE = r"""
<!doctype html><html lang="my"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="theme-color" content="#0b1020">
<title>Lynn Recap — AI Movie Recap</title><style>
:root{color-scheme:dark;--bg:#080c18;--panel:#11182a;--line:#27324b;--muted:#9aa8c2;--text:#f5f7ff;--accent:#8b7cff;--cyan:#4ed8cf}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(ellipse at 20% 0%,#1b2350 0,transparent 45%),var(--bg);color:var(--text);font:15px/1.6 system-ui,-apple-system,"Noto Sans Myanmar",sans-serif}.wrap{max-width:1040px;margin:auto;padding:22px 16px 60px}.top{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:30px}.brand{display:flex;align-items:center;gap:11px;font-size:20px;font-weight:800}.logo{display:grid;place-items:center;width:42px;height:42px;border-radius:14px;background:linear-gradient(135deg,var(--accent),#4ec8d2);color:#08101c;font-weight:900}.pill{border:1px solid var(--line);border-radius:999px;padding:7px 11px;color:var(--muted);font-size:12px}.hero{margin:26px 0 24px}.eyebrow{color:var(--cyan);font-size:12px;letter-spacing:1.6px;font-weight:800}.hero h1{font-size:clamp(30px,6vw,48px);line-height:1.2;letter-spacing:-1px;margin:10px 0}.hero p,.sub{color:var(--muted)}.grid{display:grid;grid-template-columns:1.15fr .85fr;gap:18px}.panel{background:linear-gradient(180deg,#151d31,#101727);border:1px solid var(--line);border-radius:22px;padding:20px;min-width:0}.panel h2{font-size:17px;margin:0 0 5px}.sub{font-size:13px;margin:0 0 18px}.field{margin:16px 0}.field label{display:block;font-weight:650;font-size:13px;margin-bottom:8px}.hint{font-size:12px;color:var(--muted);margin-top:6px}input[type=file]{width:100%;border:1px solid #34415f;border-radius:12px;background:#0b1120;color:var(--text);padding:12px;font:inherit}.drop{border:1px dashed #465579;border-radius:15px;padding:14px;background:#0c1221}.btn{border:0;border-radius:12px;padding:13px 16px;background:linear-gradient(135deg,var(--accent),#6c9dff);color:white;font:inherit;font-weight:800;cursor:pointer;width:100%;margin-top:8px}.btn:disabled{opacity:.55;cursor:wait}.steps{display:flex;gap:8px;margin:0 0 18px}.step{flex:1;border:1px solid var(--line);border-radius:10px;padding:9px 6px;text-align:center;color:var(--muted);font-size:11px}.step b{display:block;color:var(--text);font-size:13px}.note{border:1px solid #3c3b66;background:#191932;border-radius:13px;padding:12px;color:#d5d3ff;font-size:12px;margin-top:14px}.status{margin-top:16px;border:1px solid var(--line);border-radius:13px;padding:14px;display:none}.bar{height:7px;background:#27314a;border-radius:99px;overflow:hidden;margin:10px 0}.bar span{display:block;height:100%;width:0;background:linear-gradient(90deg,var(--accent),var(--cyan));transition:width .3s}.status small{color:var(--muted)}.output a{display:inline-block;color:var(--cyan);margin:7px 12px 0 0;word-break:break-all}.check{display:flex;align-items:center;gap:9px;color:var(--muted);font-size:13px}.check input{accent-color:var(--accent)}footer{margin-top:22px;text-align:center;color:#71809d;font-size:11px}
@media(max-width:760px){.grid{grid-template-columns:1fr}.wrap{padding:16px 12px 40px}.panel{padding:16px}.top{margin-bottom:22px}.hero{margin:20px 0}}
</style></head><body><div class="wrap"><header class="top"><div class="brand"><div class="logo">LR</div><span>Lynn Recap</span></div><div class="pill">AUTO AI · BETA</div></header>
<section class="hero"><div class="eyebrow">AI MOVIE RECAP STUDIO</div><h1>Video တင်လိုက်ရုံနဲ့<br>Transcript · SRT · မြန်မာ AI Voice</h1><p>Video အသံကို အလိုအလျောက်စာသားပြောင်း၊ Original SRT ထုတ်၊ မြန်မာဘာသာပြန် SRT နှင့် မြန်မာ AI Voice ဖန်တီးပြီး Final MP4 ထုတ်ပေးမယ်။</p></section>
<div class="steps"><div class="step"><b>01</b>Auto Transcript</div><div class="step"><b>02</b>Original SRT</div><div class="step"><b>03</b>မြန်မာ SRT</div><div class="step"><b>04</b>AI Voice + MP4</div></div>
<div class="grid"><section class="panel"><h2>New Recap Job</h2><p class="sub">Movie video တစ်ခုတင်ပြီး အလိုအလျောက်လုပ်ဆောင်ပါ။</p>
<form id="jobForm"><div class="field"><label for="video">① Movie Video *</label><div class="drop"><input id="video" name="video" type="file" accept="video/*" required></div><div class="hint">MP4, MOV, MKV, WEBM · အများဆုံး 700 MB (server setting ပေါ်မူတည်)</div></div>
<label class="check"><input type="checkbox" id="burnSubs" checked> Final MP4 ထဲမှာ မြန်မာစာတန်းထိုး ထည့်မယ်</label>
<button class="btn" id="submitBtn" type="submit">Auto Process စတင်မယ် →</button></form>
<div class="status" id="status"><strong id="statusTitle">Job စတင်နေသည်…</strong><div class="bar"><span id="barFill"></span></div><small id="statusDetail">စောင့်ပါ…</small><div class="output" id="output"></div></div></section>
<aside class="panel"><h2>Auto Workflow</h2><p class="sub">ဖိုင်တင်ပြီးနောက် အဆင့်အားလုံးကို အလိုအလျောက်လုပ်မယ်။</p>
<div class="field"><b>1. Audio Extract + Transcript</b><div class="hint">Groq Whisper နဲ့ movie အသံကို စာသားပြောင်းမယ်။</div></div>
<div class="field"><b>2. Original SRT</b><div class="hint">မူရင်းဘာသာစကား SRT ကို timestamp နဲ့ထုတ်မယ်။</div></div>
<div class="field"><b>3. Burmese Translation + SRT</b><div class="hint">Groq language model နဲ့ မြန်မာဘာသာပြန်ပြီး SRT ဖိုင်ထုတ်မယ်။</div></div>
<div class="field"><b>4. Myanmar AI Voice</b><div class="hint">Myanmar neural voice နဲ့ narration ဖန်တီးမယ်။</div></div>
<div class="field"><b>5. Final MP4</b><div class="hint">Voice နဲ့ မြန်မာစာတန်းထိုးကို video နဲ့ပေါင်းမယ်။</div></div>
<div class="note">Server Environment မှာ GROQ_API_KEY ထည့်ထားဖို့လိုပါတယ်။ လက်ရှိ voice သည် Myanmar neural TTS ဖြစ်ပြီး အသံပုံစံရွေးရန် MYANMAR_TTS_VOICE ကို ပြောင်းနိုင်ပါတယ်။ Render restart ဖြစ်လျှင် local files ပျောက်နိုင်သောကြောင့် persistent storage ကို နောက်ထပ်ချိတ်ဆက်ရန်လိုပါသေးတယ်။</div></aside></div><footer>LYNN RECAP · AUTO TRANSCRIPT + SRT + MYANMAR VOICE · v0.2</footer></div>
<script>
const form=document.getElementById('jobForm'),btn=document.getElementById('submitBtn'),box=document.getElementById('status'),title=document.getElementById('statusTitle'),detail=document.getElementById('statusDetail'),fill=document.getElementById('barFill'),output=document.getElementById('output');
function show(t,d,p){box.style.display='block';title.textContent=t;detail.textContent=d;fill.style.width=p+'%'}
async function poll(id){try{const r=await fetch('/api/jobs/'+id),j=await r.json();show(j.status==='done'?'ပြီးပါပြီ ✓':j.status==='failed'?'မအောင်မြင်ပါ':'လုပ်ဆောင်နေသည် · '+j.progress+'%',j.message||j.status,j.progress||0);if(j.status==='done'){output.innerHTML='<a href="/api/jobs/'+id+'/download">Final MP4 Download</a><a href="/api/jobs/'+id+'/original-srt">Original SRT Download</a><a href="/api/jobs/'+id+'/burmese-srt">မြန်မာ SRT Download</a><a href="/api/jobs/'+id+'/voice">AI Voice Download</a>';btn.disabled=false;btn.textContent='နောက် Job စတင်မယ် →';return}if(j.status==='failed'){btn.disabled=false;btn.textContent='ပြန်ကြိုးစားမယ်';return}setTimeout(()=>poll(id),1800)}catch(e){show('Connection error','Server ကို ပြန်စစ်ပါ။',0);btn.disabled=false}}
form.addEventListener('submit',async e=>{e.preventDefault();const f=document.getElementById('video').files[0];if(!f)return;const data=new FormData();data.append('video',f);data.append('burn_subtitles',document.getElementById('burnSubs').checked?'true':'false');btn.disabled=true;btn.textContent='Upload လုပ်နေသည်…';output.innerHTML='';show('Upload လုပ်နေသည်…','Video အရွယ်အစားပေါ်မူတည်ပြီး အချိန်ကြာနိုင်ပါတယ်။',3);try{const r=await fetch('/api/jobs',{method:'POST',body:data}),j=await r.json();if(!r.ok)throw new Error(j.detail||'Upload failed');poll(j.job_id)}catch(err){show('မအောင်မြင်ပါ',err.message,0);btn.disabled=false;btn.textContent='ပြန်ကြိုးစားမယ်'}});
</script></body></html>
"""

def _safe_suffix(name: str, allowed: set[str]) -> str:
    suffix = Path(name or "").suffix.lower()
    if suffix not in allowed:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {suffix or 'unknown'}")
    return suffix

async def _save_upload(upload: UploadFile, destination: Path) -> Path:
    suffix = _safe_suffix(upload.filename or "", ALLOWED_VIDEO)
    path = destination.with_suffix(suffix)
    size = 0
    with path.open("wb") as out:
        while chunk := await upload.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_UPLOAD_BYTES:
                out.close()
                path.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail="Video is too large. Increase MAX_UPLOAD_MB if appropriate.")
            out.write(chunk)
    if size == 0:
        path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="Uploaded video is empty.")
    return path

def _run(command: list[str], timeout: int = 3600) -> None:
    result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError((result.stderr or "Command failed")[-2500:])

def _srt_time(seconds: float) -> str:
    ms = max(0, int(seconds * 1000))
    h, rem = divmod(ms, 3600000)
    m, rem = divmod(rem, 60000)
    s, ms = divmod(rem, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"

def _write_srt(segments: list[dict[str, Any]], path: Path, text_key: str = "text") -> None:
    rows = []
    for i, seg in enumerate(segments, 1):
        text = str(seg.get(text_key, "")).strip()
        if not text:
            continue
        start = max(0.0, float(seg.get("start", 0)))
        end = max(start + 0.25, float(seg.get("end", start + 1)))
        rows.append(f"{len(rows)+1}\n{_srt_time(start)} --> {_srt_time(end)}\n{text}\n")
    path.write_text("\n".join(rows), encoding="utf-8-sig")

def _set_job(job_id: str, progress: int, message: str, status: str = "processing") -> None:
    with LOCK:
        JOBS[job_id].update(progress=progress, message=message, status=status)

async def _make_voice(text: str, output: Path) -> None:
    communicate = edge_tts.Communicate(text, MYANMAR_VOICE, rate="+8%")
    await communicate.save(str(output))

def _run_job(job_id: str, video_path: Path, burn_subtitles: bool) -> None:
    folder = DATA_DIR / job_id
    try:
        if not os.getenv("GROQ_API_KEY"):
            raise RuntimeError("Render Environment မှာ GROQ_API_KEY မထည့်ရသေးပါ။ Groq API key ထည့်ပြီး redeploy လုပ်ပါ။")
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            raise RuntimeError("FFmpeg မတွေ့ပါ။ Dockerfile မှာ FFmpeg install လုပ်ထားဖို့လိုပါတယ်။")
        client = Groq(api_key=os.environ["GROQ_API_KEY"])
        audio_path = folder / "source-audio.mp3"
        _set_job(job_id, 10, "Video ကနေ audio extract လုပ်နေသည်…")
        _run([ffmpeg, "-y", "-i", str(video_path), "-vn", "-ac", "1", "-ar", "16000", "-b:a", "48k", str(audio_path)])
        if audio_path.stat().st_size > 24 * 1024 * 1024:
            raise RuntimeError("Extracted audio သည် transcription API limit ထက်ကြီးနေပါတယ်။ ပိုတိုသော video ဖြင့် စမ်းပါ။")
        _set_job(job_id, 22, "Groq Whisper နဲ့ transcript ထုတ်နေသည်…")
        with audio_path.open("rb") as af:
            transcript = client.audio.transcriptions.create(file=(audio_path.name, af.read()), model=STT_MODEL, response_format="verbose_json", timestamp_granularities=["segment"])
        raw_segments = getattr(transcript, "segments", None) or []
        segments = []
        for item in raw_segments:
            get = item.get if isinstance(item, dict) else lambda k, d=None: getattr(item, k, d)
            txt = str(get("text", "")).strip()
            if txt:
                segments.append({"start": float(get("start", 0)), "end": float(get("end", 0)), "text": txt})
        if not segments:
            full_text = str(getattr(transcript, "text", "")).strip()
            if not full_text:
                raise RuntimeError("Transcript မရပါ။ အသံပါသော video နဲ့ ပြန်စမ်းပါ။")
            segments = [{"start": 0.0, "end": 5.0, "text": full_text}]
        original_srt = folder / "original.srt"
        _write_srt(segments, original_srt)
        _set_job(job_id, 38, "Original SRT ထုတ်ပြီးပါပြီ။ မြန်မာဘာသာပြန်နေသည်…")
        translations = []
        texts = [s["text"] for s in segments]
        for start in range(0, len(texts), 25):
            batch = texts[start:start+25]
            prompt = "Translate each subtitle into natural conversational Burmese (Myanmar language). Keep meaning, names, and order. Return ONLY a JSON array of strings with exactly the same number of items.\nSUBTITLES:\n" + json.dumps(batch, ensure_ascii=False)
            response = client.chat.completions.create(model=TRANSLATE_MODEL, temperature=0.2, messages=[{"role":"system","content":"You are a professional English-to-Burmese subtitle translator. Output valid JSON only."},{"role":"user","content":prompt}])
            content = response.choices[0].message.content or ""
            try:
                parsed = json.loads(content[content.find("["):content.rfind("]")+1])
                if not isinstance(parsed, list) or len(parsed) != len(batch):
                    raise ValueError("Translation count mismatch")
                translations.extend([str(x).strip() for x in parsed])
            except Exception as exc:
                raise RuntimeError("မြန်မာဘာသာပြန်ရလဒ်ကို ဖတ်မရပါ။ GROQ_TRANSLATE_MODEL setting ကို စစ်ပါ။") from exc
        burmese_segments = []
        for i, seg in enumerate(segments):
            burmese_segments.append({"start": seg["start"], "end": seg["end"], "text": translations[i] or seg["text"]})
        burmese_srt = folder / "burmese.srt"
        _write_srt(burmese_segments, burmese_srt)
        (folder / "transcript.txt").write_text("\n".join(texts), encoding="utf-8")
        (folder / "burmese.txt").write_text("\n".join(translations), encoding="utf-8")
        _set_job(job_id, 55, "မြန်မာ AI Voice ဖန်တီးနေသည်…")
        clips_dir = folder / "voice-clips"
        clips_dir.mkdir(exist_ok=True)
        clip_paths = []
        voice_timeline = []
        cursor = 0.0
        for i, line in enumerate(translations):
            if not line.strip():
                continue
            clip = clips_dir / f"clip-{i:05d}.mp3"
            asyncio.run(_make_voice(line, clip))
            probe = subprocess.run([shutil.which("ffprobe") or "ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(clip)], capture_output=True, text=True)
            duration = float(probe.stdout.strip() or "1")
            voice_timeline.append({"start": cursor, "end": cursor + duration, "text": line})
            cursor += duration + 0.12
            clip_paths.append(clip)
            if i % 10 == 0:
                _set_job(job_id, min(78, 55 + int(20 * (i+1) / max(1, len(translations)))), f"AI Voice ဖန်တီးနေသည်… {i+1}/{len(translations)}")
        if not clip_paths:
            raise RuntimeError("AI Voice ဖန်တီးရန် မြန်မာစာသားမရှိပါ။")
        concat_file = folder / "voice-concat.txt"
        concat_file.write_text("".join(f"file '{p.as_posix()}'\n" for p in clip_paths), encoding="utf-8")
        voice_path = folder / "burmese-voice.mp3"
        _run([ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file), "-c:a", "libmp3lame", "-q:a", "4", str(voice_path)])
        voice_srt = folder / "burmese-voice-timed.srt"
        _write_srt(voice_timeline, voice_srt)
        _set_job(job_id, 82, "မြန်မာ AI Voice နဲ့ စာတန်း timing ကို video နဲ့ပေါင်းနေသည်…")
        output_path = folder / "final.mp4"
        command = [ffmpeg, "-y", "-i", str(video_path), "-i", str(voice_path), "-map", "0:v:0", "-map", "1:a:0"]
        if burn_subtitles:
            escaped = str(voice_srt).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
            command += ["-vf", f"subtitles='{escaped}'"]
        command += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", str(output_path)]
        _run(command, timeout=7200)
        with LOCK:
            JOBS[job_id].update(status="done", progress=100, message="Transcript, SRT, Myanmar AI Voice နဲ့ Final MP4 အဆင်သင့်ဖြစ်ပါပြီ။", output=str(output_path), original_srt=str(original_srt), burmese_srt=str(burmese_srt), voice=str(voice_path))
    except Exception as exc:
        with LOCK:
            JOBS[job_id].update(status="failed", progress=0, message=str(exc)[:2200])

@app.get("/", response_class=HTMLResponse)
def home() -> str:
    return PAGE

@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "app": APP_NAME, "version": "0.2.0"}

@app.post("/api/jobs")
async def create_job(background_tasks: BackgroundTasks, video: UploadFile = File(...), burn_subtitles: str = Form(default="true")) -> dict[str, str]:
    job_id = uuid.uuid4().hex[:12]
    folder = DATA_DIR / job_id
    folder.mkdir(parents=True, exist_ok=True)
    try:
        video_path = await _save_upload(video, folder / "source")
    except Exception:
        shutil.rmtree(folder, ignore_errors=True)
        raise
    with LOCK:
        JOBS[job_id] = {"status": "queued", "progress": 5, "message": "Queue ထဲထည့်ပြီးပါပြီ။", "output": None}
    background_tasks.add_task(_run_job, job_id, video_path, burn_subtitles.lower() == "true")
    return {"job_id": job_id}

@app.get("/api/jobs/{job_id}")
def get_job(job_id: str) -> dict[str, Any]:
    with LOCK:
        job = JOBS.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job မတွေ့ပါ။ Server restart ဖြစ်လျှင် ယာယီ Job status ပျောက်နိုင်ပါတယ်။")
        return {k: v for k, v in job.items() if k not in {"output", "original_srt", "burmese_srt", "voice"}}

def _download(job_id: str, key: str, filename: str, media_type: str):
    with LOCK:
        job = JOBS.get(job_id)
        path = job.get(key) if job else None
    if not path or not Path(path).is_file():
        raise HTTPException(status_code=404, detail="ဖိုင်အဆင်သင့်မဖြစ်သေးပါ။")
    return FileResponse(path, media_type=media_type, filename=filename)

@app.get("/api/jobs/{job_id}/download")
def download_job(job_id: str):
    return _download(job_id, "output", f"lynn-recap-{job_id}.mp4", "video/mp4")

@app.get("/api/jobs/{job_id}/original-srt")
def download_original_srt(job_id: str):
    return _download(job_id, "original_srt", f"lynn-original-{job_id}.srt", "application/x-subrip")

@app.get("/api/jobs/{job_id}/burmese-srt")
def download_burmese_srt(job_id: str):
    return _download(job_id, "burmese_srt", f"lynn-myanmar-{job_id}.srt", "application/x-subrip")

@app.get("/api/jobs/{job_id}/voice")
def download_voice(job_id: str):
    return _download(job_id, "voice", f"lynn-myanmar-voice-{job_id}.mp3", "audio/mpeg")
