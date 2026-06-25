# -*- coding: utf-8 -*-
"""
用户意图解析模块 — 将自然语言指令转化为结构化剪辑参数
"""
import re
import json
from typing import Dict, List, Optional, Tuple
from modules.config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL, DEEPSEEK_TEMPERATURE
import requests


class IntentParser:
    """用户意图解析器：自然语言 → 剪辑参数"""
    
    SYSTEM_PROMPT = """你是一位视频剪辑指令解析器。用户用自然语言描述他们的剪辑需求，你需要将其解析为结构化的剪辑参数。

请输出严格合法的 JSON，格式如下：
{
  "intent_type": "filter",
  "target_duration": 60,
  "keep_rules": [{"type": "quality_above", "threshold": 70, "field": "aesthetic_score"}],
  "remove_rules": [{"type": "duration_below", "threshold": 1.0}],
  "time_range": {"start": 0, "end": null},
  "pacing": "normal",
  "explanation": "用户想要..."
}
"""
    
    QUICK_RULES = [
        (r"从\s*(\d+(?:\.\d+)?)\s*秒开始", "time_after", None, "start"),
        (r"跳过前\s*(\d+(?:\.\d+)?)\s*秒", "time_after", None, "start"),
        (r"去掉前\s*(\d+(?:\.\d+)?)\s*秒", "time_after", None, "start"),
        (r"前\s*(\d+(?:\.\d+)?)\s*秒.*(不要|去掉|删除)", "time_before", None, "end"),
        (r"(\d+(?:\.\d+)?)\s*秒", "target_duration", None, None),
        (r"(\d+(?:\.\d+)?)\s*分钟", "target_duration_min", None, None),
        (r"(不要|去掉|删除|跳过).*晃", "motion_above", 60, "remove"),
        (r"(稳定|不晃|慢节奏|平静)", "motion_below", 40, "keep"),
        (r"(动感|快节奏|运动|活力)", "motion_above", 50, "keep"),
        (r"(清晰|高清|锐利)", "sharp_above", 70, "keep"),
        (r"(模糊|不清楚)", "sharp_below", 40, "remove"),
        (r"(黑屏|过暗|太黑|看不清)", "brightness_below", 30, "remove"),
        (r"(过曝|太亮|刺眼)", "brightness_above", 220, "remove"),
        (r"(黄金时刻|日落|黄昏|暖色)", "brightness_range", (80, 180), "keep"),
        (r"精华", "quality_above", 70, "keep"),
        (r"最好的", "quality_above", 75, "keep"),
    ]
    
    def __init__(self, use_llm: bool = True, api_key: str = None):
        self.api_key = api_key or DEEPSEEK_API_KEY
        self.use_llm = use_llm and bool(self.api_key)
    
    def parse(self, instruction: str, video_info: Optional[Dict] = None) -> Dict:
        quick_result = self._quick_parse(instruction)
        if self.use_llm:
            try:
                llm_result = self._llm_parse(instruction, video_info, quick_result)
                if llm_result:
                    return llm_result
            except Exception as e:
                print(f"[IntentParser] LLM 解析失败，回退到快速规则: {e}")
        return quick_result
    
    def _quick_parse(self, instruction: str) -> Dict:
        result = {
            "intent_type": "filter", "target_duration": None,
            "keep_rules": [], "remove_rules": [],
            "time_range": {"start": 0, "end": None},
            "pacing": "normal", "explanation": instruction,
        }
        text = instruction.lower()
        for pattern, rule_type, threshold, target in self.QUICK_RULES:
            match = re.search(pattern, text)
            if match:
                self._apply_rule(result, rule_type, threshold, target, match)
        if any(w in text for w in ["慢", "稳定", "平静", "舒缓", "慢节奏"]):
            result["pacing"] = "slow"
        elif any(w in text for w in ["快", "动感", "活力", "节奏快", "短"]):
            result["pacing"] = "fast"
        return result
    
    def _apply_rule(self, result: Dict, rule_type: str, threshold, target, match):
        if rule_type == "target_duration":
            result["target_duration"] = float(match.group(1))
        elif rule_type == "target_duration_min":
            result["target_duration"] = float(match.group(1)) * 60
        elif rule_type == "time_after":
            result["time_range"]["start"] = float(match.group(1))
        elif rule_type == "time_before":
            result["time_range"]["end"] = float(match.group(1))
        elif rule_type == "brightness_range":
            lo, hi = threshold
            result["keep_rules"].append({"type": "brightness_above", "threshold": lo, "field": "brightness"})
            result["keep_rules"].append({"type": "brightness_below", "threshold": hi, "field": "brightness"})
        elif rule_type.startswith("quality_") or rule_type.startswith("motion_") or \
             rule_type.startswith("brightness_") or rule_type.startswith("colorful_") or \
             rule_type.startswith("sharp_") or rule_type.startswith("duration_"):
            rule = {"type": rule_type, "threshold": threshold}
            field_map = {
                "quality_": "aesthetic_score", "motion_": "motion_score",
                "brightness_": "brightness", "colorful_": "colorfulness",
                "sharp_": "sharpness", "duration_": "duration",
            }
            for prefix, field in field_map.items():
                if rule_type.startswith(prefix):
                    rule["field"] = field
                    break
            if target == "keep":
                result["keep_rules"].append(rule)
            elif target == "remove":
                result["remove_rules"].append(rule)
    
    def _llm_parse(self, instruction: str, video_info: Optional[Dict], 
                   quick_result: Dict) -> Optional[Dict]:
        video_hint = ""
        if video_info:
            segments = video_info.get("segments", [])
            if segments:
                avg_motion = sum(s["motion_score"] for s in segments) / len(segments)
                avg_aesthetic = sum(s["aesthetic_score"] for s in segments) / len(segments)
                avg_brightness = sum(s["brightness"] for s in segments) / len(segments)
                video_hint = f"\n视频画面统计：共 {len(segments)} 个镜头，平均运动分 {avg_motion:.1f}，平均美学分 {avg_aesthetic:.1f}，平均亮度 {avg_brightness:.1f}"
        
        user_prompt = f"""用户指令："{instruction}"{video_hint}

快速规则解析结果：{json.dumps(quick_result, ensure_ascii=False)}

请根据以上信息，输出最终的结构化剪辑参数。"""
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": DEEPSEEK_MODEL,
            "messages": [
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
            "max_tokens": 2000,
            "stream": False,
        }
        response = requests.post(
            f"{DEEPSEEK_BASE_URL}/chat/completions",
            headers=headers,
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        return json.loads(content)
    
    def apply_to_segments(self, params: Dict, segments: List[Dict]) -> List[Dict]:
        timeline = []
        for seg in segments:
            start = seg["start"]
            end = seg["end"]
            time_range = params.get("time_range", {})
            if time_range.get("start") and end < time_range["start"]:
                timeline.append({"start": start, "end": end, "text": seg.get("text", ""), "action": "remove", "reason": f"在目标时间范围之前", "duration": round(end - start, 2)})
                continue
            if time_range.get("end") and start > time_range["end"]:
                timeline.append({"start": start, "end": end, "text": seg.get("text", ""), "action": "remove", "reason": f"在目标时间范围之后", "duration": round(end - start, 2)})
                continue
            
            should_remove = False
            remove_reason = ""
            for rule in params.get("remove_rules", []):
                if self._matches_rule(rule, seg):
                    should_remove = True
                    remove_reason = self._rule_to_text(rule)
                    break
            if should_remove:
                timeline.append({"start": start, "end": end, "text": seg.get("text", ""), "action": "remove", "reason": remove_reason, "duration": round(end - start, 2)})
                continue
            
            should_keep = True
            keep_reason = "保留"
            keep_rules = params.get("keep_rules", [])
            if keep_rules:
                should_keep = False
                for rule in keep_rules:
                    if self._matches_rule(rule, seg):
                        should_keep = True
                        keep_reason = self._rule_to_text(rule, keep=True)
                        break
            if should_keep:
                timeline.append({"start": start, "end": end, "text": seg.get("text", ""), "action": "keep", "reason": keep_reason, "duration": round(end - start, 2)})
            else:
                timeline.append({"start": start, "end": end, "text": seg.get("text", ""), "action": "remove", "reason": "不符合保留条件", "duration": round(end - start, 2)})
        
        target = params.get("target_duration")
        if target:
            timeline = self._apply_target_duration(timeline, target, params.get("pacing", "normal"))
        timeline = self._merge_adjacent_keeps(timeline)
        return timeline
    
    def _matches_rule(self, rule: Dict, seg: Dict) -> bool:
        field = rule.get("field", "aesthetic_score")
        threshold = rule.get("threshold", 0)
        if field == "duration":
            value = seg.get("end", 0) - seg.get("start", 0)
        else:
            value = seg.get(field, seg.get("visual_data", {}).get(field, 0))
        rule_type = rule.get("type", "")
        if rule_type.endswith("_above"):
            return value > threshold
        elif rule_type.endswith("_below"):
            return value < threshold
        elif rule_type == "time_after":
            return seg.get("start", 0) > threshold
        elif rule_type == "time_before":
            return seg.get("end", 0) < threshold
        return False
    
    def _rule_to_text(self, rule: Dict, keep: bool = False) -> str:
        field_names = {
            "aesthetic_score": "美学分", "motion_score": "运动分",
            "brightness": "亮度", "colorfulness": "色彩丰富度",
            "sharpness": "清晰度", "duration": "时长",
        }
        field = field_names.get(rule.get("field", ""), rule.get("field", ""))
        threshold = rule.get("threshold", 0)
        if rule["type"].endswith("_above"):
            return f"{field}高于{threshold}"
        elif rule["type"].endswith("_below"):
            return f"{field}低于{threshold}"
        elif rule["type"] == "time_after":
            return f"在时间{threshold}秒之后"
        elif rule["type"] == "time_before":
            return f"在时间{threshold}秒之前"
        return str(rule)
    
    def _apply_target_duration(self, timeline: List[Dict], target: float, 
                               pacing: str) -> List[Dict]:
        keeps = [t for t in timeline if t["action"] == "keep"]
        total = sum(t["duration"] for t in keeps)
        if total <= target:
            return timeline
        if pacing == "slow":
            keeps.sort(key=lambda t: (-t.get("duration", 0), t.get("visual_data", {}).get("motion_score", 0)))
        elif pacing == "fast":
            keeps.sort(key=lambda t: (-t.get("visual_data", {}).get("motion_score", 0), -t.get("duration", 0)))
        else:
            keeps.sort(key=lambda t: t.get("visual_data", {}).get("aesthetic_score", 0), reverse=True)
        selected = []
        current = 0
        for t in keeps:
            if current + t["duration"] <= target:
                selected.append(t)
                current += t["duration"]
        selected_starts = {t["start"] for t in selected}
        for t in timeline:
            if t["action"] == "keep" and t["start"] not in selected_starts:
                t["action"] = "remove"
                t["reason"] = f"超出目标时长 {target} 秒"
        return timeline
    
    def _merge_adjacent_keeps(self, timeline: List[Dict], gap_threshold: float = 0.5) -> List[Dict]:
        if not timeline:
            return timeline
        merged = [dict(timeline[0])]
        for item in timeline[1:]:
            if item["action"] != "keep":
                merged.append(dict(item))
                continue
            last = merged[-1]
            if last["action"] == "keep" and (item["start"] - last["end"]) <= gap_threshold:
                last["end"] = item["end"]
                last["text"] = (last.get("text", "") + " " + item.get("text", "")).strip()
                last["duration"] = round(last["end"] - last["start"], 2)
            else:
                merged.append(dict(item))
        return merged
