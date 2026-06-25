# -*- coding: utf-8 -*-
"""
AI Video Editor - FastAPI Backend
自动剪视频 + 去杂音 + 加字幕 + 简单动效
"""
import os
import json
import uuid
import shutil
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict

from fastapi import FastAPI, File, UploadFile, Form, BackgroundTasks, WebSocket
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

# 导入处理模块
from modules.transcriber import Transcriber
from modules.analyzer import ClipAnalyzer
from modules.renderer import VideoRenderer
from modules.audio_processor import AudioProcessor
from modules.visual_analyzer import VisualAnalyzer
from modules.intent_parser import IntentParser
from modules.config import MAX_UPLOAD_MB, FFMPEG_PATH, print_config_status

# ========== 配置 ==========
BASE_DIR = Path(__file__).parent.resolve()
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "outputs"
TEMP_DIR = BASE_DIR / "temp"

for d in [UPLOAD_DIR, OUTPUT_DIR, TEMP_DIR]:
    d.mkdir(exist_ok=True)

app = FastAPI(title="AI Video Editor", version="1.0.0")

# 静态文件 & 模板
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")

# 任务状态存储
JOB_STATUS = {}  # job_id -> {status, progress, message, output_path}

# 启动时检查 FFmpeg 和打印配置状态
def _startup_checks():
    import subprocess
    print("\n" + "="*50)
    print("[ClipAI] 启动检查...")
    print("="*50)
    
    # 打印配置状态
    print_config_status()
    
    # 检查 FFmpeg
    try:
        subprocess.run([FFMPEG_PATH, "-version"], capture_output=True, check=True)
        print(f"[ClipAI] ✅ FFmpeg ready: {FFMPEG_PATH}")
    except Exception as e:
        print(f"[ClipAI] ⚠️ FFmpeg check failed: {e}")
        print(f"[ClipAI] 请安装 FFmpeg 并设置环境变量 FFMPEG_PATH")
    
    print("="*50 + "\n")

_startup_checks()

# ========== 路由 ==========

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """主页面"""
    return templates.TemplateResponse(request, "index.html")


@app.post("/api/upload")
async def upload_video(file: UploadFile = File(...)):
    """上传视频文件"""
    job_id = str(uuid.uuid4())[:8]
    ext = Path(file.filename).suffix.lower()
    if ext not in ['.mp4', '.mov', '.avi', '.mkv', '.webm']:
        return JSONResponse(status_code=400, content={"error": "仅支持 mp4/mov/avi/mkv/webm 格式"})
    
    upload_path = UPLOAD_DIR / f"{job_id}{ext}"
    with open(upload_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    
    # 检查文件大小
    file_size_mb = upload_path.stat().st_size / (1024 * 1024)
    if file_size_mb > MAX_UPLOAD_MB:
        upload_path.unlink(missing_ok=True)
        return JSONResponse(status_code=413, content={"error": f"文件过大，最大支持 {MAX_UPLOAD_MB}MB"})
    
    JOB_STATUS[job_id] = {
        "id": job_id,
        "status": "uploaded",
        "progress": 10,
        "message": "视频上传成功",
        "input_path": str(upload_path),
        "output_path": None,
        "created_at": datetime.now().isoformat()
    }
    
    return {"job_id": job_id, "status": "uploaded", "filename": file.filename}


@app.post("/api/process")
async def process_video(
    job_id: str = Form(...),
    api_key: str = Form(""),               # 用户自带 API Key
    video_mode: str = Form("speech"),     # speech / visual
    instruction: str = Form(""),            # 用户自然语言指令
    mode: str = Form("auto"),              # auto / silence / subtitle / custom
    remove_silence: bool = Form(True),
    add_subtitle: bool = Form(True),
    denoise_audio: bool = Form(False),
    add_zoom: bool = Form(False),           # 简单放大动效
    add_bgm: bool = Form(False),            # 添加背景音乐
    target_duration: Optional[float] = Form(None),  # 目标时长(秒)
    style: str = Form("vlog")               # vlog / podcast / short
):
    """启动视频处理任务"""
    if job_id not in JOB_STATUS:
        return JSONResponse(status_code=404, content={"error": "任务不存在"})
    
    JOB_STATUS[job_id]["status"] = "processing"
    JOB_STATUS[job_id]["progress"] = 15
    JOB_STATUS[job_id]["message"] = "开始处理..."
    JOB_STATUS[job_id]["params"] = {
        "api_key": api_key,
        "video_mode": video_mode,
        "instruction": instruction,
        "mode": mode,
        "remove_silence": remove_silence,
        "add_subtitle": add_subtitle,
        "denoise_audio": denoise_audio,
        "add_zoom": add_zoom,
        "add_bgm": add_bgm,
        "target_duration": target_duration,
        "style": style
    }
    
    # 后台异步处理
    asyncio.create_task(_process_video_task(job_id))
    
    return {"job_id": job_id, "status": "processing"}


@app.get("/api/status/{job_id}")
async def get_status(job_id: str):
    """查询任务状态"""
    if job_id not in JOB_STATUS:
        return JSONResponse(status_code=404, content={"error": "任务不存在"})
    return JOB_STATUS[job_id]


@app.get("/api/download/{job_id}")
async def download_video(job_id: str):
    """下载处理后的视频"""
    if job_id not in JOB_STATUS:
        return JSONResponse(status_code=404, content={"error": "任务不存在"})
    
    output_path = JOB_STATUS[job_id].get("output_path")
    if not output_path or not Path(output_path).exists():
        return JSONResponse(status_code=404, content={"error": "输出文件不存在"})
    
    return FileResponse(
        path=output_path,
        media_type="video/mp4",
        filename=f"AI_Clip_{job_id}.mp4"
    )


@app.get("/api/history")
async def get_history():
    """获取所有任务历史"""
    return list(JOB_STATUS.values())


@app.delete("/api/jobs/{job_id}")
async def delete_job(job_id: str):
    """删除任务"""
    if job_id not in JOB_STATUS:
        return JSONResponse(status_code=404, content={"error": "任务不存在"})
    
    job = JOB_STATUS[job_id]
    # 清理文件
    for p in [job.get("input_path"), job.get("output_path")]:
        if p and Path(p).exists():
            try:
                Path(p).unlink()
            except:
                pass
    
    del JOB_STATUS[job_id]
    return {"status": "deleted"}


# ========== WebSocket 实时进度推送 ==========

@app.websocket("/ws/{job_id}")
async def websocket_endpoint(websocket: WebSocket, job_id: str):
    await websocket.accept()
    try:
        while True:
            if job_id in JOB_STATUS:
                await websocket.send_json(JOB_STATUS[job_id])
                if JOB_STATUS[job_id]["status"] in ["completed", "failed"]:
                    break
            await asyncio.sleep(1)
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        await websocket.close()


# ========== 核心处理逻辑 ==========

async def _update_progress(job_id: str, progress: int, message: str):
    """更新任务进度"""
    if job_id in JOB_STATUS:
        JOB_STATUS[job_id]["progress"] = progress
        JOB_STATUS[job_id]["message"] = message


async def _process_video_task(job_id: str):
    """后台处理视频的主流程 — 支持语音模式和画面模式"""
    job = JOB_STATUS[job_id]
    input_path = job["input_path"]
    params = job.get("params", {})
    video_mode = params.get("video_mode", "speech")
    instruction = params.get("instruction", "")
    
    try:
        if video_mode == "visual":
            # ========== 画面模式 ==========
            await _process_visual_mode(job_id, input_path, params, instruction)
        else:
            # ========== 语音模式（原有逻辑）==========
            await _process_speech_mode(job_id, input_path, params)
        
    except Exception as e:
        import traceback
        print(f"处理失败: {e}")
        traceback.print_exc()
        JOB_STATUS[job_id]["status"] = "failed"
        JOB_STATUS[job_id]["message"] = f"处理失败: {str(e)}"
        JOB_STATUS[job_id]["progress"] = 0


async def _process_speech_mode(job_id: str, input_path: str, params: Dict):
    """语音模式处理流程（口播、播客、Vlog）"""
    # 步骤 1: 音频处理
    await _update_progress(job_id, 20, "步骤 1/5: 音频处理中...")
    audio_processor = AudioProcessor()
    
    if params.get("denoise_audio"):
        processed_audio = await asyncio.to_thread(
            audio_processor.denoise, input_path, TEMP_DIR / f"{job_id}_audio_clean.wav"
        )
    else:
        processed_audio = await asyncio.to_thread(
            audio_processor.extract_audio, input_path, TEMP_DIR / f"{job_id}_audio.wav"
        )
    
    # 步骤 2: 语音识别
    await _update_progress(job_id, 35, "步骤 2/5: 语音识别中...")
    transcriber = Transcriber()
    transcript = await asyncio.to_thread(transcriber.transcribe, input_path)
    
    srt_path = TEMP_DIR / f"{job_id}.srt"
    transcriber.save_srt(transcript, str(srt_path))
    
    # 步骤 3: 智能分析
    await _update_progress(job_id, 50, "步骤 3/5: 智能分析剪辑点...")
    api_key = params.get("api_key")
    analyzer = ClipAnalyzer(use_llm=True, api_key=api_key)
    
    if params.get("remove_silence"):
        segments = await asyncio.to_thread(
            analyzer.remove_silence, transcript,
            silence_threshold=1.0, min_segment=2.0,
            style=params.get("style", "vlog")
        )
    else:
        segments = await asyncio.to_thread(
            analyzer.auto_highlight, transcript,
            style=params.get("style", "vlog"),
            target_duration=params.get("target_duration")
        )
    
    # 步骤 4: 渲染
    await _update_progress(job_id, 70, "步骤 4/5: 视频渲染中...")
    await _render_video(job_id, input_path, segments, params, str(srt_path))


async def _process_visual_mode(job_id: str, input_path: str, params: Dict, instruction: str):
    """画面模式处理流程（风景、航拍、无语音）"""
    # 步骤 1: 画面分析
    await _update_progress(job_id, 20, "步骤 1/4: 画面分析中...")
    visual_analyzer = VisualAnalyzer()
    
    analysis = await asyncio.to_thread(visual_analyzer.analyze_video, input_path)
    
    # 转换为类 transcript 格式
    visual_segments = visual_analyzer.to_transcript_format(analysis)
    
    # 保存分析结果
    analysis_path = TEMP_DIR / f"{job_id}_visual_analysis.json"
    with open(analysis_path, "w", encoding="utf-8") as f:
        json.dump(analysis, f, ensure_ascii=False, indent=2)
    
    # 步骤 2: 解析用户指令
    await _update_progress(job_id, 40, "步骤 2/4: 解析剪辑指令...")
    api_key = params.get("api_key")
    intent_parser = IntentParser(use_llm=True, api_key=api_key)
    
    if instruction.strip():
        parsed_params = intent_parser.parse(instruction, analysis)
        print(f"[VisualMode] 用户指令解析: {parsed_params.get('explanation', '')}")
    else:
        # 没有指令，使用默认参数
        parsed_params = {
            "intent_type": "filter",
            "target_duration": params.get("target_duration"),
            "keep_rules": [{"type": "quality_above", "threshold": 50, "field": "aesthetic_score"}],
            "remove_rules": [{"type": "duration_below", "threshold": 1.0}],
            "time_range": {"start": 0, "end": None},
            "pacing": params.get("style", "normal"),
            "explanation": "无指令，自动保留高质量画面片段"
        }
    
    # 步骤 3: 应用指令生成时间线
    await _update_progress(job_id, 60, "步骤 3/4: 生成剪辑时间线...")
    segments = intent_parser.apply_to_segments(parsed_params, visual_segments)
    
    # 保存时间线
    timeline_path = TEMP_DIR / f"{job_id}_timeline.json"
    with open(timeline_path, "w", encoding="utf-8") as f:
        json.dump(segments, f, ensure_ascii=False, indent=2)
    
    # 步骤 4: 渲染
    await _update_progress(job_id, 80, "步骤 4/4: 视频渲染中...")
    # 画面模式不加字幕（因为没有语音），但支持缩放动效
    await _render_video(job_id, input_path, segments, params, None)


async def _render_video(job_id: str, input_path: str, segments: List[Dict], 
                         params: Dict, srt_path: Optional[str]):
    """统一渲染视频"""
    renderer = VideoRenderer()
    output_path = OUTPUT_DIR / f"{job_id}_final.mp4"
    
    await asyncio.to_thread(
        renderer.render,
        input_path=str(input_path),
        segments=segments,
        output_path=str(output_path),
        srt_path=srt_path if params.get("add_subtitle") else None,
        add_zoom=params.get("add_zoom", False),
        add_bgm=params.get("add_bgm", False),
        style=params.get("style", "vlog")
    )
    
    # 步骤 5: 完成
    await _update_progress(job_id, 100, "处理完成！")
    JOB_STATUS[job_id]["status"] = "completed"
    JOB_STATUS[job_id]["output_path"] = str(output_path)
    JOB_STATUS[job_id]["timeline"] = segments
    JOB_STATUS[job_id]["completed_at"] = datetime.now().isoformat()
    
    # 清理临时文件
    _cleanup_temp(job_id)


def _cleanup_temp(job_id: str):
    """清理临时文件"""
    for f in TEMP_DIR.glob(f"{job_id}*"):
        try:
            f.unlink()
        except:
            pass


# ========== 启动 ==========

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
