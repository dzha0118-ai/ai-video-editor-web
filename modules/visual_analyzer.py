# -*- coding: utf-8 -*-
"""
画面分析模块 — 纯画面视频（无语音）的剪辑决策基础
基于 OpenCV
"""
import cv2
import numpy as np
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import json


class VisualAnalyzer:
    """画面分析器：为无语音视频提供剪辑决策依据"""
    
    def __init__(self):
        self.frame_skip = 5
    
    def analyze_video(self, video_path: str, sample_interval: float = 1.0) -> Dict:
        print(f"[VisualAnalyzer] 开始分析画面: {video_path}")
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"无法打开视频: {video_path}")
        
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps
        
        scenes = self._detect_scenes(cap, fps, duration)
        segments = self._analyze_segments(cap, fps, scenes, sample_interval)
        cap.release()
        
        result = {
            "duration": round(duration, 2),
            "fps": round(fps, 2),
            "scenes": scenes,
            "segments": segments,
            "total_scenes": len(scenes)
        }
        print(f"[VisualAnalyzer] 分析完成: {len(scenes)} 个镜头, {len(segments)} 个片段")
        return result
    
    def _detect_scenes(self, cap, fps: float, duration: float) -> List[float]:
        print("[VisualAnalyzer] 检测镜头切换...")
        scenes = [0.0]
        prev_hist = None
        frame_idx = 0
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            if frame_idx % self.frame_skip != 0:
                frame_idx += 1
                continue
            
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            hist = cv2.calcHist([gray], [0], None, [64], [0, 256])
            hist = cv2.normalize(hist, hist).flatten()
            
            if prev_hist is not None:
                diff = cv2.compareHist(prev_hist, hist, cv2.HISTCMP_BHATTACHARYYA)
                if diff > 0.5:
                    time_sec = frame_idx / fps
                    if time_sec - scenes[-1] > 1.0:
                        scenes.append(round(time_sec, 2))
            prev_hist = hist
            frame_idx += 1
        
        if duration - scenes[-1] > 1.0:
            scenes.append(round(duration, 2))
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        return scenes
    
    def _analyze_segments(self, cap, fps: float, scenes: List[float], 
                          sample_interval: float) -> List[Dict]:
        segments = []
        for i in range(len(scenes) - 1):
            start = scenes[i]
            end = scenes[i + 1]
            if end - start < 0.5:
                continue
            
            samples = self._sample_frames(cap, fps, start, end, sample_interval)
            if not samples:
                continue
            
            motion_scores = []
            brightness_vals = []
            colorfulness_vals = []
            sharpness_vals = []
            prev_frame = None
            
            for frame in samples:
                if prev_frame is not None:
                    motion_scores.append(self._calc_motion(prev_frame, frame))
                brightness_vals.append(self._calc_brightness(frame))
                colorfulness_vals.append(self._calc_colorfulness(frame))
                sharpness_vals.append(self._calc_sharpness(frame))
                prev_frame = frame
            
            avg_motion = np.mean(motion_scores) if motion_scores else 0
            avg_brightness = np.mean(brightness_vals) if brightness_vals else 128
            avg_colorful = np.mean(colorfulness_vals) if colorfulness_vals else 0
            avg_sharp = np.mean(sharpness_vals) if sharpness_vals else 0
            
            brightness_score = 100 - abs(avg_brightness - 128) / 1.28
            colorful_score = avg_colorful
            sharp_score = avg_sharp
            motion_score = 100 - abs(avg_motion - 50) * 2
            
            aesthetic = (
                brightness_score * 0.15 + colorful_score * 0.25 +
                sharp_score * 0.25 + motion_score * 0.35
            )
            
            segments.append({
                "start": round(start, 2), "end": round(end, 2),
                "duration": round(end - start, 2),
                "motion_score": round(avg_motion, 1),
                "brightness": round(avg_brightness, 1),
                "colorfulness": round(avg_colorful, 1),
                "sharpness": round(avg_sharp, 1),
                "aesthetic_score": round(aesthetic, 1)
            })
        return segments
    
    def _sample_frames(self, cap, fps: float, start: float, end: float, 
                       interval: float) -> List[np.ndarray]:
        frames = []
        current = start
        while current < end:
            frame_idx = int(current * fps)
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = cap.read()
            if ret:
                frames.append(frame)
            current += interval
        return frames
    
    def _calc_motion(self, prev_frame: np.ndarray, curr_frame: np.ndarray) -> float:
        prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
        curr_gray = cv2.cvtColor(curr_frame, cv2.COLOR_BGR2GRAY)
        flow = cv2.calcOpticalFlowFarneback(
            prev_gray, curr_gray, None, 0.5, 3, 15, 3, 5, 1.2, 0
        )
        magnitude = np.sqrt(flow[..., 0] ** 2 + flow[..., 1] ** 2)
        return min(np.mean(magnitude) * 10, 100)
    
    def _calc_brightness(self, frame: np.ndarray) -> float:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        return np.mean(gray)
    
    def _calc_colorfulness(self, frame: np.ndarray) -> float:
        lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        std_a = np.std(a)
        std_b = np.std(b)
        mean_diff = np.abs(np.mean(a) - np.mean(b))
        return min((std_a + std_b + mean_diff / 2) / 2.55, 100)
    
    def _calc_sharpness(self, frame: np.ndarray) -> float:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        return min(laplacian.var() / 10, 100)
    
    def to_transcript_format(self, analysis: Dict) -> List[Dict]:
        segments = []
        for seg in analysis["segments"]:
            descriptions = []
            if seg["aesthetic_score"] > 75:
                descriptions.append("画面非常优美，构图精良，色彩丰富")
            elif seg["aesthetic_score"] > 50:
                descriptions.append("画面质量不错，视觉感受良好")
            else:
                descriptions.append("画面质量一般")
            
            if seg["motion_score"] > 60:
                descriptions.append("画面动感十足，有视觉冲击力")
            elif seg["motion_score"] > 30:
                descriptions.append("画面有一定动态感")
            else:
                descriptions.append("画面较为稳定静态")
            
            if seg["brightness"] < 50:
                descriptions.append("光线偏暗，可能是夜景或阴影")
            elif seg["brightness"] > 200:
                descriptions.append("光线明亮，可能曝光较强")
            
            if seg["colorfulness"] > 70:
                descriptions.append("色彩非常鲜艳丰富")
            elif seg["colorfulness"] > 40:
                descriptions.append("色彩适中")
            
            text = "；".join(descriptions)
            segments.append({
                "start": seg["start"], "end": seg["end"], "text": text,
                "confidence": seg["aesthetic_score"] / 100,
                "visual_data": seg
            })
        return segments
