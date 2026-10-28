from __future__ import annotations

import os
import re
import shutil
import subprocess
import threading
import uuid
from pathlib import Path
from typing import Any

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

APP_NAME = "Lynn Recap"
DATA_DIR = Path(os.getenv("LYNN_DATA_DIR", "/tmp/lynn-recap"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
JOBS: dict[str, dict[str, Any]] = {}
LOCK = threading.Lock()
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_MB", "700")) * 1024 * 1024
ALLOWED_VIDEO = {".mp4", ".mov", ".mkv", ".webm", ".m4v"}
ALLOWED_AUDIO = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"}
ALLOWED_SUBS = {".srt"}

app = FastAPI(title=APP_NAME, version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

PAGE = r"""
<!doctype html>
<html lang="my">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="theme-color" content="#0b1020">
<title>Lynn Recap — AI Movie Recap</title>
<style>
:root{color-scheme:dark;--bg:#080c18;--panel:#11182a;--line:#27324b;--muted:#9aa8c2;--text:#f5f7ff;--accent:#8b7cff;--cyan:#4ed8cf}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(ellipse at 20% 0%,#1b2350 0,transparent 45%),var(--bg);color:var(--text);font:15px/1.5 system-ui,-apple-system,"Noto Sans Myanmar",sans-serif}
.wrap{max-width:1040px;margin:auto;padding:22px 16px 60px}.top{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:30px}.brand{display:flex;align-items:center;gap:11px;font-size:20px;font-weight:800;letter-spacing:-.4px}.logo{display:grid;place-items:center;width:42px;height:42px;border-radius:14px;background:linear-gradient(135deg,var(--accent),#4ec8d2);color:#08101c;font-weight:900}.pill{border:1px solid var(--line);border-radius:999px;padding:7px 11px;color:var(--muted);font-size:12px}
.hero{margin:26px 0 24px}.eyebrow{color:var(--cyan);font-size:12px;letter-spacing:1.6px;font-weight:800}.hero h1{font-size:clamp(30px,6vw,48px);line-height:1.14;letter-spacing:-1.5px;margin:10px 0}.hero p{color:var(--muted);max-width:640px;margin:0}
.grid{display:grid;grid-template-columns:1.15fr .85fr;gap:18px}.panel{background:linear-gradient(180deg,#151d31,#101727);border:1px solid var(--line);border-radius:22px;padding:20px;min-width:0}.panel h2{font-size:17px;margin:0 0 5px}.sub{font-size:13px;color:var(--muted);margin:0 0 18px}
.field{margin:16px 0}.field label{display:block;font-weight:650;font-size:13px;margin-bottom:8px}.hint{font-size:12px;color:var(--muted);margin-top:6px}
input[type=file],input[type=url],input[type=text]{width:100%;border:1px solid #34415f;border-radius:12px;background:#0b1120;color:var(--text);padding:12px;font:inherit}input[type=file]{font-size:12px}input:focus{outline:2px solid #8076ff;outline-offset:1px}
.drop{border:1px dashed #465579;border-radius:15px;padding:14px;background:#0c1221}
.btn{border:0;border-radius:12px;padding:13px 16px;background:linear-gradient(135deg,var(--accent),#6c9dff);color:white;font:inherit;font-weight:800;cursor:pointer;width:100%;margin-top:8px}.btn:disabled{opacity:.55;cursor:wait}.btn.secondary{background:#202b43;border:1px solid #3a4867}.steps{display:flex;gap:8px;margin:0 0 18px}.step{flex:1;border:1px solid var(--line);border-radius:10px;padding:9px 6px;text-align:center;color:var(--muted);font-size:11px}.step b{display:block;color:var(--text);font-size:13px}
.note{border:1px solid #3c3b66;background:#191932;border-radius:13px;padding:12px;color:#d5d3ff;font-size:12px;margin-top:14px}
.status{margin-top:16px;border:1px solid var(--line);border-radius:13px;padding:14px;display:none}.bar{height:7px;background:#27314a;border-radius:99px;overflow:hidden;margin:10px 0}.bar span{display:block;height:100%;width:0;background:linear-gradient(90deg,var(--accent),var(--cyan));transition:width .3s}.status small{color:var(--muted)}
.output a{color:var(--cyan);word-break:break-all}.check{display:flex;align-items:center;gap:9px;color:var(--muted);font-size:13px}.check input{accent-color:var(--accent)}
footer{margin-top:22px;text-align:center;color:#71809d;font-size:11px}
@media(max-width:760px){.grid{grid-template-columns:1fr}.wrap{padding:16px 12px 40px}.panel{padding:16px}.top{margin-bottom:22px}.hero{margin:20px 0}}
</style></head>
<body><div class="wrap">
<header class="top"><div class="brand"><div class="logo">LR</div><span>Lynn Recap</span></div><div class="pill">BETA · Burmese workflow</div></header>
<section class="hero"><div class="eyebrow">AI MOVIE RECAP STUDIO</div><h1>Movie တစ်ကားမှ<br>မြန်မာ Recap Video အထိ။</h1><p>Video တင်ပါ၊ ကိုယ်တိုင်ဘာသာပြန်ထားတဲ့ မြန်မာ SRT နဲ့ narration audio ထည့်ပါ၊ Final MP4 ကို ထုတ်ယူပါ။</p></section>
<div class="steps"><div class="step"><b>01</b>Video</div><div class="step"><b>02</b>မြန်မာ SRT</div><div class="step"><b>03</b>Voice</div><div class="step"><b>04</b>Final MP4</div></div>
<div class="grid">
<section class="panel"><h2>New Recap Job</h2><p class="sub">ဖိုင်များကို ရွေးပြီး Processing စတင်ပါ။</p>
<form id="jobForm">
<div class="field"><label for="video">① Movie Video *</label><div class="drop"><input id="video" name="video" type="file" accept="video/mp4,video/quicktime,video/x-matroska,video/webm" required></div><div class="hint">MP4, MOV, MKV, WEBM · အများဆုံး 700 MB (server config ပေါ်မူတည်)</div></div>
<div class="field"><label for="srt">② မြန်မာစာတန်းထိုး (SRT)</label><input id="srt" name="srt" type="file" accept=".srt"><div class="hint">Manual Burmese translation လုပ်ပြီး .srt ဖိုင်တင်ပါ။</div></div>
<div class="field"><label for="voice">③ မြန်မာ AI Voice Audio</label><input id="voice" name="voice" type="file" accept="audio/*"><div class="hint">လက်ရှိအဆင့်မှာ ထုတ်ပြီးသား voice audio ကိုတင်နိုင်ပါတယ်။ AI TTS provider ကို နောက်အဆင့်မှာ ချိတ်ဆက်မယ်။</div></div>
<div class="field"><label for="videoUrl">Video URL</label><input id="videoUrl" type="url" placeholder="https://…"><div class="hint">URL import ကို နောက်တစ်ဆင့်မှာ backend နဲ့ချိတ်ဆက်မယ်။ လက်ရှိ upload ကို အသုံးပြုပါ။</div></div>
<label class="check"><input type="checkbox" id="burnSubs" checked> Final MP4 ထဲမှာ မြန်မာစာတန်းထိုး ထည့်မယ်</label>
<button class="btn" id="submitBtn" type="submit">Processing စတင်မယ် →</button>
</form><div class="status" id="status"><strong id="statusTitle">Job စတင်နေသည်…</strong><div class="bar"><span id="barFill"></span></div><small id="statusDetail">စောင့်ပါ…</small><div class="output" id="output"></div></div>
</section>
<aside class="panel"><h2>Workflow</h2><p class="sub">Lynn Recap ရဲ့ လက်ရှိ MVP လုပ်ဆောင်ပုံ</p>
<div class="field"><b>1. Upload</b><div class="hint">Movie video ကို server ပေါ်တင်မယ်။</div></div>
<div class="field"><b>2. Manual Subtitle</b><div class="hint">မြန်မာဘာသာပြန်ထားတဲ့ SRT ကို အသုံးပြုမယ်။</div></div>
<div class="field"><b>3. Voice Audio</b><div class="hint">Narration audio ရှိရင် video audio နဲ့ အစားထိုးမယ်။</div></div>
<div class="field"><b>4. FFmpeg Render</b><div class="hint">SRT ကို burn-in လုပ်ပြီး H.264/AAC MP4 ထုတ်မယ်။</div></div>
<div class="note">မှတ်ချက် — Render Free instance ရဲ့ local storage က အမြဲတမ်းမသိမ်းနိုင်ပါ။ Cloudflare R2 persistent storage ကို မချိတ်ရသေးပါ။</div>
</aside></div><footer>LYNN RECAP · BUILDING IN PUBLIC · v0.1 MVP</footer>
</div>
<script>
const form=document.getElementById('jobForm'),btn=document.getElementById('submitBtn'),statusBox=document.getElementById('status');
const title=document.getElementById('statusTitle'),detail=document.getElementById('statusDetail'),fill=document.getElementById('barFill'),output=document.getElementById('output');
function showStatus(t,d,p){statusBox.style.display='block';title.textContent=t;detail.textContent=d;fill.style.width=p+'%'}
async function poll(id){try{const r=await fetch('/api/jobs/'+id);const j=await r.json();showStatus(j.status==='done'?'ပြီးပါပြီ ✓':j.status==='failed'?'မအောင်မြင်ပါ':'Processing '+j.progress+'%',j.message||j.status,j.progress||0);if(j.status==='done'){output.innerHTML='<a href="/api/jobs/'+id+'/download">Final MP4 ကို Download လုပ်ရန် ↗</a>';btn.disabled=false;btn.textContent='နောက် Job စတင်မယ် →';return}if(j.status==='failed'){btn.disabled=false;return}setTimeout(()=>poll(id),1800)}catch(e){showStatus('Connection error','Server ကို ပြန်စစ်ပါ။',0);btn.disabled=false}}
form.addEventListener('submit',async e=>{e.preventDefault();const url=document.getElementById('videoUrl').value.trim();if(url){alert('URL import ကို မချိတ်ရသေးပါ။ Video file ကို upload လုပ်ပါ။');return}
const data=new FormData();data.append('burn_subtitles',document.getElementById('burnSubs').checked?'true':'false');
for(const name of ['video','srt','voice']){const f=document.getElementById(name).files[0];if(f)data.append(name,f)}
btn.disabled=true;btn.textContent='Upload လုပ်နေသည်…';showStatus('Upload လုပ်နေသည်…','Video အရွယ်အစားပေါ်မူတည်ပြီး အချိန်ကြာနိုင်ပါတယ်။',5);
try{const r=await fetch('/api/jobs',{method:'POST',body:data});const j=await r.json();if(!r.ok)throw new Error(j.detail||'Upload failed');showStatus('Job စတင်ပါပြီ','Video ကို process လုပ်နေသည်။',10);poll(j.job_id)}catch(err){showStatus('မအောင်မြင်ပါ',err.message,0);btn.disabled=false;btn.textContent='ပြန်ကြိုးစားမယ်'}}
);
</script></body></html>
"""

def _safe_name(name: str, allowed: set[str]) -> str:
    suffix = Path(name or "").suffix.lower()
    if suffix not in allowed:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {suffix or 'unknown'}")
    return suffix

async def _save_upload(upload: UploadFile, destination: Path, allowed: set[str]) -> None:
    suffix = _safe_name(upload.filename or "", allowed)
    destination = destination.with_suffix(suffix)
    size = 0
    with destination.open("wb") as out:
        while True:
            chunk = await upload.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_UPLOAD_BYTES:
                out.close()
                destination.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail="Upload is too large. Increase MAX_UPLOAD_MB if appropriate.")
            out.write(chunk)
    if size == 0:
        destination.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

def _run_job(job_id: str, video_path: Path, srt_path: Path | None, voice_path: Path | None, burn_subtitles: bool) -> None:
    folder = DATA_DIR / job_id
    output_path = folder / "final.mp4"
    with LOCK:
        JOBS[job_id]["status"] = "processing"
        JOBS[job_id]["progress"] = 15
        JOBS[job_id]["message"] = "FFmpeg ကို စတင်နေသည်…"
    try:
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            raise RuntimeError("FFmpeg မတွေ့ပါ။ Render environment မှာ FFmpeg install လုပ်ဖို့လိုပါတယ်။")
        command = [ffmpeg, "-y", "-i", str(video_path)]
        if voice_path:
            command += ["-i", str(voice_path)]
        if burn_subtitles and srt_path:
            escaped = str(srt_path).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
            command += ["-vf", f"subtitles='{escaped}'"]
        if voice_path:
            command += ["-map", "0:v:0", "-map", "1:a:0", "-c:a", "aac", "-b:a", "192k", "-shortest"]
        else:
            command += ["-map", "0:v:0", "-map", "0:a?", "-c:a", "aac", "-b:a", "192k"]
        command += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-movflags", "+faststart", str(output_path)]
        with LOCK:
            JOBS[job_id]["progress"] = 35
            JOBS[job_id]["message"] = "Video render လုပ်နေသည်…"
        result = subprocess.run(command, capture_output=True, text=True, timeout=60 * 60)
        if result.returncode != 0:
            raise RuntimeError((result.stderr or "FFmpeg failed")[-1800:])
        with LOCK:
            JOBS[job_id].update(status="done", progress=100, message="Final MP4 အဆင်သင့်ဖြစ်ပါပြီ။", output=str(output_path))
    except Exception as exc:
        with LOCK:
            JOBS[job_id].update(status="failed", progress=0, message=str(exc)[:2000])

@app.get("/", response_class=HTMLResponse)
def home() -> str:
    return PAGE

@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "app": APP_NAME, "version": "0.1.0"}

@app.post("/api/jobs")
async def create_job(
    background_tasks: BackgroundTasks,
    video: UploadFile = File(...),
    srt: UploadFile | None = File(default=None),
    voice: UploadFile | None = File(default=None),
    burn_subtitles: str = Form(default="true"),
) -> dict[str, str]:
    job_id = uuid.uuid4().hex[:12]
    folder = DATA_DIR / job_id
    folder.mkdir(parents=True, exist_ok=True)
    try:
        video_path = folder / "source"
        await _save_upload(video, video_path, ALLOWED_VIDEO)
        video_path = next(folder.glob("source.*"))
        srt_path = None
        voice_path = None
        if srt and srt.filename:
            await _save_upload(srt, folder / "subtitles", ALLOWED_SUBS)
            srt_path = next(folder.glob("subtitles.*"))
        if voice and voice.filename:
            await _save_upload(voice, folder / "voice", ALLOWED_AUDIO)
            voice_path = next(folder.glob("voice.*"))
    except Exception:
        shutil.rmtree(folder, ignore_errors=True)
        raise
    with LOCK:
        JOBS[job_id] = {"status": "queued", "progress": 5, "message": "Queue ထဲထည့်ပြီးပါပြီ။", "output": None}
    background_tasks.add_task(_run_job, job_id, video_path, srt_path, voice_path, burn_subtitles.lower() == "true")
    return {"job_id": job_id}

@app.get("/api/jobs/{job_id}")
def get_job(job_id: str) -> dict[str, Any]:
    with LOCK:
        job = JOBS.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job မတွေ့ပါ။ Server restart ဖြစ်လျှင် ယာယီ Job status ပျောက်နိုင်ပါတယ်။")
        return {k: v for k, v in job.items() if k != "output"}

@app.get("/api/jobs/{job_id}/download")
def download_job(job_id: str) -> FileResponse:
    with LOCK:
        job = JOBS.get(job_id)
        output = job.get("output") if job else None
    if not output or not Path(output).is_file():
        raise HTTPException(status_code=404, detail="Final MP4 အဆင်သင့်မဖြစ်သေးပါ။")
    return FileResponse(output, media_type="video/mp4", filename=f"lynn-recap-{job_id}.mp4")
