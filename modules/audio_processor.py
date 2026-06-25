# -*- coding: utf-8 -*-
"""
音频处理模块
去杂音、降噪、音量标准化、音频提取
"""
import subprocess
from pathlib import Path
from typing import Optional
from pydub import AudioSegment
from pydub.effects import normalize
import numpy as np

from modules.config import FFMPEG_PATH, FFPROBE_PATH


class AudioProcessor:
    """音频处理器：降噪、音量调整、音频提取"""
    
    def __init__(self, ffmpeg_path: str = None):
        self.ffmpeg = ffmpeg_path or FFMPEG_PATH
        self.ffprobe = FFPROBE_PATH
    
    def extract_audio(self, video_path: str, output_path: str) -> str:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            self.ffmpeg, "-y", "-i", video_path, "-vn",
            "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "2", str(output)
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        print(f"[AudioProcessor] 音频提取完成: {output}")
        return str(output)
    
    def denoise(self, video_path: str, output_path: str, noise_reduction: float = 0.5) -> str:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        temp_audio = str(output).replace(".wav", "_raw.wav")
        self.extract_audio(video_path, temp_audio)
        nr_db = int(noise_reduction * 30)
        cmd = [
            self.ffmpeg, "-y", "-i", temp_audio,
            "-af", f"afftdn=nf=-20:nr={nr_db}:tn=1",
            "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "2", str(output)
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        Path(temp_audio).unlink(missing_ok=True)
        print(f"[AudioProcessor] 降噪完成: {output}")
        return str(output)
    
    def normalize_volume(self, audio_path: str, output_path: str, target_db: float = -14.0) -> str:
        cmd = [
            self.ffmpeg, "-y", "-i", audio_path,
            "-af", f"loudnorm=I={target_db}:TP=-1.5:LRA=11",
            "-acodec", "pcm_s16le", str(output_path)
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        print(f"[AudioProcessor] 音量标准化完成: {output_path}")
        return output_path
    
    def remove_humming(self, audio_path: str, output_path: str) -> str:
        cmd = [
            self.ffmpeg, "-y", "-i", audio_path,
            "-af", "highpass=f=80", "-acodec", "pcm_s16le", str(output_path)
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        print(f"[AudioProcessor] 哼鸣去除完成: {output_path}")
        return output_path
    
    def merge_audio_back(self, video_path: str, audio_path: str, output_path: str) -> str:
        cmd = [
            self.ffmpeg, "-y", "-i", video_path, "-i", audio_path,
            "-c:v", "copy", "-map", "0:v:0", "-map", "1:a:0",
            "-shortest", str(output_path)
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        print(f"[AudioProcessor] 音频合并完成: {output_path}")
        return output_path
