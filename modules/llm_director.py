# -*- coding: utf-8 -*-
"""
LLM 导演模块 - 基于 DeepSeek API
将语音识别文本交给 LLM 做剪辑决策，替代简单的规则引擎
"""
import json
import requests
from typing import List, Dict, Optional
from modules.config import (
    DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, 
    DEEPSEEK_MODEL, DEEPSEEK_TEMPERATURE
)


class LLMDirector:
    """LLM 导演：用大语言模型做剪辑决策"""
    
    SYSTEM_PROMPT = """你是一位资深视频剪辑导演。你的任务是根据视频的语音识别文本，决定哪些片段应该保留、哪些应该删除，并生成最优剪辑时间线。

## 剪辑原则
1. 删除：语气词（嗯、啊、那个）、长停顿、重复内容、口误、与主题无关的闲聊
2. 保留：核心观点、金句、总结、关键数据、情绪高潮、转折性语句
3. 节奏：相邻保留片段之间如果间隔超过1.5秒，视为可删除的停顿
4. 每个保留片段至少2秒，避免碎剪

## 输出格式
你必须输出严格合法的 JSON，格式如下：
{
  "reasoning": "整体分析思路（50字以内）",
  "segments": [
    {"start": 0.0, "end": 5.2, "action": "keep", "reason": "开场白，保留"},
    {"start": 5.2, "end": 8.0, "action": "remove", "reason": "停顿，删除"},
    ...
  ]
}

- action 只能是 "keep" 或 "remove"
- start 和 end 使用原始时间（秒），精确到0.1秒
- segments 必须覆盖视频的完整时间线，不能遗漏任何时间段
- 如果两个 keep 片段之间只有很短停顿（<1.5s），建议合并为一个 keep 段
"""
    
    STYLE_PROMPTS = {
        "vlog": "Vlog风格：保留日常感、真实感、情绪自然的片段。可以适当保留一些口语化表达，但去掉明显卡顿。",
        "podcast": "播客风格：优先保留信息密度高的内容、核心观点、数据、结论。口语化填充词（就是、那个、然后）一律删除。",
        "short": "短视频风格：极度紧凑，只保留最抓人的金句、爆点、反转。每段保留2-6秒，节奏要快。",
    }
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or DEEPSEEK_API_KEY
        self.base_url = DEEPSEEK_BASE_URL.rstrip("/")
        self.model = DEEPSEEK_MODEL
        self.temperature = DEEPSEEK_TEMPERATURE
        if not self.api_key:
            print("[LLMDirector] ⚠️ 警告：未配置 DeepSeek API Key，将回退到规则引擎")
    
    def is_available(self) -> bool:
        return bool(self.api_key)
    
    def analyze(self, segments: List[Dict], style: str = "vlog", 
                target_duration: Optional[float] = None) -> List[Dict]:
        if not self.is_available():
            print("[LLMDirector] API Key 未配置，跳过 LLM 分析")
            return None
        
        transcript_text = self._build_transcript_text(segments)
        style_hint = self.STYLE_PROMPTS.get(style, self.STYLE_PROMPTS["vlog"])
        duration_hint = f"\n目标总时长：约 {target_duration} 秒" if target_duration else ""
        
        user_prompt = f"""请分析以下视频转录文本，并生成剪辑时间线。

{style_hint}{duration_hint}

## 转录文本（每行格式：时间戳 -> 文本）

{transcript_text}

请输出 JSON 格式的剪辑时间线。"""
        
        try:
            print("[LLMDirector] 正在调用 DeepSeek API 进行剪辑分析...")
            result = self._call_api(user_prompt)
            timeline = self._parse_llm_response(result, segments)
            print(f"[LLMDirector] LLM 分析完成，生成 {len(timeline)} 个剪辑点")
            return timeline
        except Exception as e:
            print(f"[LLMDirector] LLM 调用失败: {e}，将回退到规则引擎")
            return None
    
    def _build_transcript_text(self, segments: List[Dict]) -> str:
        lines = []
        for seg in segments:
            start = seg["start"]
            end = seg["end"]
            text = seg["text"].strip()
            if text:
                lines.append(f"[{start:.1f}s -> {end:.1f}s] {text}")
        return "\n".join(lines)
    
    def _call_api(self, user_prompt: str) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self.temperature,
            "max_tokens": 4000,
            "stream": False,
        }
        response = requests.post(
            f"{self.base_url}/chat/completions",
            headers=headers,
            json=payload,
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        return content
    
    def _parse_llm_response(self, content: str, original_segments: List[Dict]) -> List[Dict]:
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        elif content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()
        
        data = json.loads(content)
        reasoning = data.get("reasoning", "")
        print(f"[LLMDirector] 导演思路: {reasoning}")
        timeline = data.get("segments", [])
        if not timeline:
            raise ValueError("LLM 返回的时间线为空")
        
        formatted = []
        for item in timeline:
            formatted.append({
                "start": round(float(item["start"]), 2),
                "end": round(float(item["end"]), 2),
                "text": item.get("text", "[LLM分析]"),
                "action": item.get("action", "keep"),
                "reason": item.get("reason", ""),
                "duration": round(float(item["end"]) - float(item["start"]), 2),
            })
        return formatted
    
    def quick_judge(self, text: str) -> Dict:
        if not self.is_available():
            return None
        prompt = f"""请判断以下这句话在视频剪辑中是否值得保留。只输出 JSON：
{{"keep": true/false, "reason": "原因", "confidence": 0.0~1.0}}

文本：{text!r}"""
        try:
            result = self._call_api(prompt)
            if "```json" in result:
                result = result.split("```json")[1].split("```")[0].strip()
            elif "```" in result:
                result = result.split("```")[1].split("```")[0].strip()
            return json.loads(result)
        except:
            return None
