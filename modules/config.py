# -*- coding: utf-8 -*-
"""
配置加载模块
"""
import os
from pathlib import Path
import toml

BASE_DIR = Path(__file__).parent.parent.resolve()
CONFIG_PATH = BASE_DIR / "config.toml"

def load_config():
    """加载配置文件，如果不存在则返回默认值"""
    defaults = {
        "deepseek": {
            "api_key": os.environ.get("DEEPSEEK_API_KEY", ""),
            "base_url": "https://api.deepseek.com/v1",
            "model": "deepseek-chat",
            "temperature": 0.3,
        },
        "ffmpeg": {
            "ffmpeg_path": os.environ.get("FFMPEG_PATH", "ffmpeg"),
            "ffprobe_path": os.environ.get("FFPROBE_PATH", "ffprobe"),
        },
        "whisper": {
            "model_size": "base",
            "language": "auto",
        },
        "app": {
            "max_upload_mb": int(os.environ.get("MAX_UPLOAD_MB", 500)),
            "temp_cleanup_min": 30,
        },
    }
    
    if CONFIG_PATH.exists():
        user_config = toml.load(CONFIG_PATH)
        # 合并用户配置到默认值
        for section, values in user_config.items():
            if section in defaults:
                defaults[section].update(values)
    
    return defaults

# 全局配置对象
CONFIG = load_config()

# 导出常用配置
DEEPSEEK_API_KEY = CONFIG["deepseek"]["api_key"]
DEEPSEEK_BASE_URL = CONFIG["deepseek"]["base_url"]
DEEPSEEK_MODEL = CONFIG["deepseek"]["model"]
DEEPSEEK_TEMPERATURE = CONFIG["deepseek"]["temperature"]

FFMPEG_PATH = CONFIG["ffmpeg"]["ffmpeg_path"]
FFPROBE_PATH = CONFIG["ffmpeg"]["ffprobe_path"]

WHISPER_MODEL = CONFIG["whisper"]["model_size"]
WHISPER_LANGUAGE = CONFIG["whisper"]["language"]

MAX_UPLOAD_MB = CONFIG["app"]["max_upload_mb"]
