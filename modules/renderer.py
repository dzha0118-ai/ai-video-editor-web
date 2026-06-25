# -*- coding: utf-8 -*-
"""
视频渲染模块 - 基于 FFmpeg 和 MoviePy
负责：裁剪拼接、加字幕、加动效、加BGM
"""
import os
import subprocess
import json
from pathlib import Path
from typing import List, Dict, Optional
from moviepy import (
    VideoFileClip, AudioFileClip, CompositeVideoClip, 
    concatenate_videoclips, TextClip, ColorClip
)
import numpy as np

from modules.config import FFMPEG_PATH


class VideoRenderer:
    """视频渲染器：将时间线脚本渲染为最终视频"""
    
    def __init__(self, ffmpeg_path: str = None):
        self.ffmpeg = ffmpeg_path or FFMPEG_PATH
        
    def render(self, input_path: str, segments: List[Dict], 
               output_path: str, srt_path: Optional[str] = None,
               add_zoom: bool = False, add_bgm: bool = False,
               style: str = "vlog") -> str:
        print(f"[Renderer] 开始渲染: {input_path} -> {output_path}")
        keep_segments = [s for s in segments if s["action"] == "keep"]
        if not keep_segments:
            raise ValueError("没有可保留的片段！")
        
        print(f"[Renderer] 裁剪 {len(keep_segments)} 个片段...")
        clips = []
        for i, seg in enumerate(keep_segments):
            clip = VideoFileClip(input_path).subclipped(seg["start"], seg["end"])
            if add_zoom and i % 3 == 0:
                clip = self._add_zoom_effect(clip, scale=1.15, duration=0.5)
            clips.append(clip)
        
        final_video = concatenate_videoclips(clips, method="compose")
        
        if srt_path and Path(srt_path).exists():
            print("[Renderer] 添加字幕...")
            final_video = self._add_subtitle_to_video(final_video, srt_path, keep_segments)
        
        if add_bgm:
            print("[Renderer] 添加背景音乐...")
            final_video = self._add_bgm(final_video, style)
        
        print(f"[Renderer] 写入文件...")
        final_video.write_videofile(
            output_path, codec="libx264", audio_codec="aac",
            fps=30, preset="fast", threads=4
        )
        final_video.close()
        for c in clips:
            c.close()
        print(f"[Renderer] 渲染完成: {output_path}")
        return output_path
    
    def _add_zoom_effect(self, clip, scale: float = 1.15, duration: float = 0.5):
        import cv2
        def zoom_effect(get_frame, t):
            frame = get_frame(t)
            h, w = frame.shape[:2]
            progress = min(t / duration, 1.0) if duration > 0 else 1.0
            current_scale = 1.0 + (scale - 1.0) * progress
            new_h, new_w = int(h * current_scale), int(w * current_scale)
            resized = cv2.resize(frame, (new_w, new_h))
            y_start = (new_h - h) // 2
            x_start = (new_w - w) // 2
            return resized[y_start:y_start + h, x_start:x_start + w]
        if clip.duration <= duration:
            return clip.fl(zoom_effect)
        else:
            zoom_part = clip.subclipped(0, duration).fl(zoom_effect)
            rest_part = clip.subclipped(duration)
            return concatenate_videoclips([zoom_part, rest_part])
    
    def _add_subtitle_to_video(self, video_clip, srt_path: str, keep_segments: List[Dict]):
        subtitles = self._parse_srt(srt_path)
        adjusted_subtitles = self._adjust_subtitle_timing(subtitles, keep_segments)
        txt_clips = []
        for sub in adjusted_subtitles:
            if not sub["text"].strip():
                continue
            txt_clip = TextClip(
                sub["text"], fontsize=36, color="white", font="Arial-Bold",
                stroke_color="black", stroke_width=2,
                size=(int(video_clip.w * 0.9), None), method="caption"
            )
            txt_clip = txt_clip.with_position(("center", "bottom")).with_start(sub["start"]).with_duration(sub["duration"])
            txt_clips.append(txt_clip)
        if txt_clips:
            return CompositeVideoClip([video_clip] + txt_clips)
        return video_clip
    
    def _add_bgm(self, video_clip, style: str = "vlog"):
        if video_clip.audio:
            video_clip = video_clip.with_audio(video_clip.audio.with_volume_scaled(1.2))
        return video_clip
    
    def _parse_srt(self, srt_path: str) -> List[Dict]:
        subtitles = []
        with open(srt_path, "r", encoding="utf-8") as f:
            content = f.read()
        blocks = content.strip().split("\n\n")
        for block in blocks:
            lines = block.strip().split("\n")
            if len(lines) < 3:
                continue
            time_line = lines[1]
            start_str, end_str = time_line.split(" --> ")
            start = self._srt_time_to_seconds(start_str)
            end = self._srt_time_to_seconds(end_str)
            text = "\n".join(lines[2:])
            subtitles.append({"start": start, "end": end, "duration": end - start, "text": text.strip()})
        return subtitles
    
    def _srt_time_to_seconds(self, time_str: str) -> float:
        time_str = time_str.strip().replace(",", ".")
        parts = time_str.split(":")
        return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
    
    def _adjust_subtitle_timing(self, subtitles: List[Dict], keep_segments: List[Dict]) -> List[Dict]:
        adjusted = []
        time_offset = 0
        seg_idx = 0
        for sub in subtitles:
            while seg_idx < len(keep_segments):
                seg = keep_segments[seg_idx]
                if seg["start"] <= sub["start"] < seg["end"]:
                    new_start = time_offset + (sub["start"] - seg["start"])
                    new_end = time_offset + (sub["end"] - seg["start"])
                    adjusted.append({"start": new_start, "end": new_end, "duration": new_end - new_start, "text": sub["text"]})
                    break
                elif sub["start"] >= seg["end"]:
                    time_offset += (seg["end"] - seg["start"])
                    seg_idx += 1
                else:
                    break
        return adjusted
