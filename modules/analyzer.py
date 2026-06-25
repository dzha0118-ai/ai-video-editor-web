# -*- coding: utf-8 -*-
"""
智能分析模块 V2
支持 LLM 导演模式（DeepSeek）和规则引擎模式
"""
import json
import re
from typing import List, Dict, Optional
from pathlib import Path

from modules.llm_director import LLMDirector


class ClipAnalyzer:
    """剪辑分析器：决定保留哪些片段、删除哪些片段"""
    
    KEYWORDS_IMPORTANT = [
        "重点", "关键", "核心", "总结", "结论", "必须", "一定要",
        "important", "key point", "summary", "conclusion", "must",
        "首先", "第一", "最后", "总之", "所以", "因此",
        "first", "finally", "so", "therefore", "in conclusion"
    ]
    
    KEYWORDS_FILLER = [
        "嗯", "啊", "那个", "这个", "就是", "然后", "对吧",
        "呃", "好吧", "你知道", "我觉得", "可能", "大概",
        "um", "uh", "like", "you know", "actually", "basically",
        "sort of", "kind of", "I mean", "so yeah"
    ]
    
    def __init__(self, use_llm: bool = True, api_key: str = None):
        self.llm_director = LLMDirector(api_key=api_key) if use_llm else None
    
    def remove_silence(self, segments: List[Dict], 
                       silence_threshold: float = 1.0,
                       min_segment: float = 2.0,
                       style: str = "vlog") -> List[Dict]:
        if self.llm_director and self.llm_director.is_available():
            try:
                llm_timeline = self.llm_director.analyze(segments, style=style)
                if llm_timeline:
                    return llm_timeline
            except Exception as e:
                print(f"[Analyzer] LLM 模式失败，回退到规则引擎: {e}")
        return self._rule_based_remove_silence(segments, silence_threshold, min_segment)
    
    def auto_highlight(self, segments: List[Dict], 
                       style: str = "vlog",
                       target_duration: Optional[float] = None) -> List[Dict]:
        if self.llm_director and self.llm_director.is_available():
            try:
                llm_timeline = self.llm_director.analyze(
                    segments, style=style, target_duration=target_duration
                )
                if llm_timeline:
                    return llm_timeline
            except Exception as e:
                print(f"[Analyzer] LLM 模式失败，回退到规则引擎: {e}")
        return self._rule_based_highlight(segments, style, target_duration)
    
    def _rule_based_remove_silence(self, segments: List[Dict], 
                                    silence_threshold: float,
                                    min_segment: float) -> List[Dict]:
        timeline = []
        for i, seg in enumerate(segments):
            duration = seg["end"] - seg["start"]
            text = seg["text"].strip()
            if duration < 0.5 and len(text) < 5:
                continue
            filler_ratio = self._count_filler_ratio(text)
            is_important = self._is_important(text)
            if duration < min_segment and not is_important:
                action = "remove"
                reason = "片段过短且无实质内容"
            elif filler_ratio > 0.6 and not is_important:
                action = "remove"
                reason = "填充词过多"
            else:
                action = "keep"
                reason = "保留"
            timeline.append({
                "start": seg["start"], "end": seg["end"], "text": text,
                "action": action, "reason": reason, "duration": round(duration, 2)
            })
        timeline = self._merge_adjacent_keeps(timeline)
        timeline = self._filter_long_gaps(timeline, silence_threshold)
        return timeline
    
    def _rule_based_highlight(self, segments: List[Dict], 
                               style: str, target_duration: Optional[float]) -> List[Dict]:
        scored = []
        for seg in segments:
            score = self._score_segment(seg, style)
            scored.append({**seg, "score": score, "duration": seg["end"] - seg["start"]})
        scored.sort(key=lambda x: x["score"], reverse=True)
        if target_duration is None:
            total = sum(s["duration"] for s in segments)
            if style == "short":
                target_duration = min(total * 0.3, 60)
            elif style == "podcast":
                target_duration = total * 0.6
            else:
                target_duration = total * 0.7
        selected = []
        current_duration = 0
        for seg in scored:
            if current_duration + seg["duration"] <= target_duration:
                selected.append(seg)
                current_duration += seg["duration"]
        selected.sort(key=lambda x: x["start"])
        timeline = []
        for seg in selected:
            timeline.append({
                "start": seg["start"], "end": seg["end"], "text": seg["text"],
                "action": "keep", "reason": f"精华片段 (score: {seg['score']:.1f})",
                "duration": round(seg["duration"], 2)
            })
        timeline = self._merge_adjacent_keeps(timeline)
        return timeline
    
    def _score_segment(self, seg: Dict, style: str) -> float:
        text = seg["text"]
        duration = seg["end"] - seg["start"]
        confidence = seg.get("confidence", 0)
        score = 50.0
        word_count = len(text) / max(duration, 1)
        score += min(word_count * 5, 20)
        if self._is_important(text):
            score += 25
        score += confidence * 10
        filler_ratio = self._count_filler_ratio(text)
        score -= filler_ratio * 30
        if style == "short":
            if any(w in text for w in ["震惊", "没想到", "竟然", "爆", "惊", "!"]):
                score += 15
            score += (10 - min(duration, 10)) * 2
        elif style == "podcast":
            score += word_count * 3
        else:
            if 3 <= duration <= 8:
                score += 10
        return max(0, min(100, score))
    
    def _is_important(self, text: str) -> bool:
        text_lower = text.lower()
        return any(kw in text_lower for kw in self.KEYWORDS_IMPORTANT)
    
    def _count_filler_ratio(self, text: str) -> float:
        text_lower = text.lower()
        words = text_lower.split()
        if not words:
            return 0.0
        filler_count = sum(1 for w in words if w in [k.lower() for k in self.KEYWORDS_FILLER])
        return filler_count / len(words)
    
    def _merge_adjacent_keeps(self, timeline: List[Dict], gap_threshold: float = 0.5) -> List[Dict]:
        if not timeline:
            return timeline
        merged = [timeline[0].copy()]
        for item in timeline[1:]:
            if item["action"] != "keep":
                merged.append(item)
                continue
            last = merged[-1]
            if last["action"] == "keep" and (item["start"] - last["end"]) <= gap_threshold:
                last["end"] = item["end"]
                last["text"] += " " + item["text"]
                last["duration"] = round(last["end"] - last["start"], 2)
            else:
                merged.append(item)
        return merged
    
    def _filter_long_gaps(self, timeline: List[Dict], threshold: float) -> List[Dict]:
        result = []
        for i in range(len(timeline)):
            result.append(timeline[i])
            if i < len(timeline) - 1:
                gap = timeline[i + 1]["start"] - timeline[i]["end"]
                if gap > threshold:
                    result.append({
                        "start": timeline[i]["end"], "end": timeline[i + 1]["start"],
                        "text": "[停顿]", "action": "remove", "reason": f"长停顿 {gap:.1f}s",
                        "duration": round(gap, 2)
                    })
        return result
