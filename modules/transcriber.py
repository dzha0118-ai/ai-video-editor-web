# -*- coding: utf-8 -*-
"""
语音识别模块 - 基于 OpenAI Whisper
支持多语言，生成带时间轴的字幕
"""
import os
import json
import whisper
from pathlib import Path
from typing import List, Dict

from modules.config import WHISPER_MODEL, WHISPER_LANGUAGE


class Transcriber:
    """语音识别器：提取视频中的语音并生成时间轴"""
    
    def __init__(self, model_size: str = None):
        """
        model_size: tiny, base, small, medium, large
        """
        model = model_size or WHISPER_MODEL
        print(f"[Transcriber] 正在加载 Whisper 模型: {model}...")
        self.model = whisper.load_model(model)
        print("[Transcriber] 模型加载完成！")
    
    def transcribe(self, video_path: str, language: str = None) -> List[Dict]:
        """
        转录视频，返回带时间戳的文本片段
        """
        print(f"[Transcriber] 开始转录: {video_path}")
        
        lang = language or WHISPER_LANGUAGE
        kwargs = {"verbose": False, "word_timestamps": False}
        if lang and lang != "auto":
            kwargs["language"] = lang
        
        result = self.model.transcribe(video_path, **kwargs)
        
        segments = []
        for seg in result.get("segments", []):
            segments.append({
                "start": round(seg["start"], 2),
                "end": round(seg["end"], 2),
                "text": seg["text"].strip(),
                "confidence": round(seg.get("avg_logprob", -0.5), 3)
            })
        
        print(f"[Transcriber] 转录完成，共 {len(segments)} 个片段")
        return segments
    
    def detect_silence(self, segments: List[Dict], threshold: float = 1.0) -> List[Dict]:
        """
        检测片段间的静音/停顿区域
        """
        silences = []
        for i in range(len(segments) - 1):
            gap = segments[i + 1]["start"] - segments[i]["end"]
            if gap >= threshold:
                silences.append({
                    "start": segments[i]["end"],
                    "end": segments[i + 1]["start"],
                    "duration": round(gap, 2),
                    "type": "silence"
                })
        
        print(f"[Transcriber] 检测到 {len(silences)} 处长停顿（>{threshold}s）")
        return silences
    
    def save_srt(self, segments: List[Dict], output_path: str):
        """保存为 SRT 字幕格式"""
        def format_time(seconds: float) -> str:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            secs = int(seconds % 60)
            millis = int((seconds % 1) * 1000)
            return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
        
        with open(output_path, "w", encoding="utf-8") as f:
            for i, seg in enumerate(segments, 1):
                if not seg["text"].strip():
                    continue
                f.write(f"{i}\n")
                f.write(f"{format_time(seg['start'])} --> {format_time(seg['end'])}\n")
                f.write(f"{seg['text']}\n\n")
        
        print(f"[Transcriber] 字幕已保存: {output_path}")
    
    def save_json(self, segments: List[Dict], output_path: str):
        """保存为 JSON 格式"""
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(segments, f, ensure_ascii=False, indent=2)
        print(f"[Transcriber] JSON 已保存: {output_path}")
