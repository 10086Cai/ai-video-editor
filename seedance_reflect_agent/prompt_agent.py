#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PromptAgent — 负责将用户的自然语言意图
转化为高质量的 Seedance 专业提示词。

推理流程（7步 CoT）：
  Step 1  解析用户意图（主体/场景/动作/情绪）
  Step 2  选定镜头语言（景别/运镜/光线）
  Step 3  补充环境细节（天气/时段/氛围）
  Step 4  加入风格标签（写实/电影/赛博朋克等）
  Step 5  控制节奏词（slow-motion / timelapse 等）
  Step 6  负向约束（avoid: 水印/文字/低质量）
  Step 7  组合输出最终提示词
"""

import json
import re
from typing import Dict, Any


class PromptAgent:
    """将自然语言意图映射为 Seedance 高质量提示词（纯本地规则引擎）"""

    # ── 风格标签库 ──────────────────────────────────────────────────
    STYLE_TAGS = {
        "写实": "photorealistic, high detail, 8K resolution",
        "电影": "cinematic, film grain, anamorphic lens, color grading",
        "赛博朋克": "cyberpunk, neon lights, rain-slicked streets, volumetric fog",
        "卡通": "3D cartoon, Pixar style, vibrant colors",
        "纪录片": "documentary style, handheld camera, natural lighting",
        "商业": "commercial photography style, clean background, soft studio light",
        "自然": "nature documentary, 4K HDR, macro lens",
    }

    # ── 运镜标签库 ──────────────────────────────────────────────────
    SHOT_TYPES = {
        "特写": "extreme close-up (ECU)",
        "近景": "close-up (CU)",
        "中景": "medium shot (MS)",
        "全景": "full shot (FS)",
        "远景": "wide establishing shot",
        "航拍": "aerial drone shot, bird's-eye view",
        "跟随": "tracking shot, camera follows subject",
        "推进": "slow camera push-in",
        "拉出": "slow camera pull-out",
        "环绕": "360-degree orbit around subject",
    }

    # ── 负向词 ──────────────────────────────────────────────────────
    NEGATIVE_TERMS = (
        "no watermark, no text overlay, no logo, "
        "no blur artifacts, no distorted faces, "
        "avoid low quality, avoid pixelation"
    )

    def __init__(self):
        self.cot_trace: list[Dict[str, Any]] = []

    def build(self, user_intent: str, style: str = "写实",
              shot: str = "中景", extras: str = "") -> Dict[str, Any]:
        """
        7步 CoT 推理，返回:
        {
            "final_prompt": str,
            "cot_trace": [...],
            "metadata": {style, shot, ...}
        }
        """
        self.cot_trace = []

        # Step 1 — 解析意图
        intent = self._step_parse_intent(user_intent)

        # Step 2 — 镜头语言
        shot_desc = self._step_shot_language(shot)

        # Step 3 — 环境细节
        env = self._step_environment(user_intent)

        # Step 4 — 风格标签
        style_desc = self._step_style(style)

        # Step 5 — 节奏词
        rhythm = self._step_rhythm(user_intent)

        # Step 6 — 负向约束
        negative = self._step_negative()

        # Step 7 — 组合
        final_prompt = self._step_compose(
            intent, shot_desc, env, style_desc, rhythm, extras, negative
        )

        return {
            "final_prompt": final_prompt,
            "cot_trace": self.cot_trace,
            "metadata": {
                "style": style,
                "shot": shot,
                "extras": extras,
                "user_intent": user_intent,
            },
        }

    # ── CoT Steps ────────────────────────────────────────────────────

    def _step_parse_intent(self, text: str) -> str:
        """Step 1: 提取主体、场景、动作"""
        # 简单启发式：保留原意，添加英文并列
        step_out = f"Subject/Action: {text}"
        self._log("Step1_ParseIntent", text, step_out)
        return text

    def _step_shot_language(self, shot_key: str) -> str:
        """Step 2: 将中文镜头名映射为英文描述"""
        desc = self.SHOT_TYPES.get(shot_key, self.SHOT_TYPES["中景"])
        self._log("Step2_ShotLanguage", shot_key, desc)
        return desc

    def _step_environment(self, text: str) -> str:
        """Step 3: 基于文本提取/推断环境细节"""
        hints = []
        time_map = {"夜": "night, moonlight", "清晨": "early morning, golden hour",
                    "黄昏": "golden hour, sunset", "正午": "midday, harsh sunlight"}
        weather_map = {"雨": "rainy, wet streets", "雪": "snowy, frosty",
                       "雾": "misty fog", "晴": "clear sunny day"}
        for k, v in time_map.items():
            if k in text:
                hints.append(v)
        for k, v in weather_map.items():
            if k in text:
                hints.append(v)
        env = ", ".join(hints) if hints else "natural ambient lighting"
        self._log("Step3_Environment", text, env)
        return env

    def _step_style(self, style_key: str) -> str:
        """Step 4: 映射风格标签"""
        desc = self.STYLE_TAGS.get(style_key, self.STYLE_TAGS["写实"])
        self._log("Step4_Style", style_key, desc)
        return desc

    def _step_rhythm(self, text: str) -> str:
        """Step 5: 推断节奏关键词"""
        if any(w in text for w in ["慢动作", "slow", "缓缓", "慢慢"]):
            r = "slow motion, 120fps"
        elif any(w in text for w in ["延时", "timelapse", "快进"]):
            r = "time-lapse, 10x speed"
        elif any(w in text for w in ["快速", "激烈", "动感"]):
            r = "dynamic motion, fast cuts"
        else:
            r = "smooth motion, steady pace"
        self._log("Step5_Rhythm", text, r)
        return r

    def _step_negative(self) -> str:
        """Step 6: 负向约束词"""
        self._log("Step6_Negative", "fixed", self.NEGATIVE_TERMS)
        return self.NEGATIVE_TERMS

    def _step_compose(self, intent, shot, env, style, rhythm, extras, negative) -> str:
        """Step 7: 将所有元素组合为最终提示词"""
        parts = [intent, shot, env, style, rhythm]
        if extras:
            parts.append(extras)
        # 正向提示词
        positive = ", ".join(p for p in parts if p)
        final = f"{positive}. {negative}"
        self._log("Step7_Compose", {"parts": parts}, final)
        return final

    def _log(self, step: str, inp: Any, out: Any):
        self.cot_trace.append({"step": step, "input": inp, "output": out})

    def refine_with_feedback(self, original: Dict[str, Any],
                              feedback: Dict[str, Any]) -> Dict[str, Any]:
        """
        根据 ReflectAgent 的反思反馈，对提示词进行定向增强。
        feedback 示例:
        {
            "issues": ["运镜不稳", "色调偏暗"],
            "suggestions": ["增加稳定镜头描述", "提升曝光描述"]
        }
        """
        issues = feedback.get("issues", [])
        suggestions = feedback.get("suggestions", [])
        extras = original["metadata"].get("extras", "")

        # 根据常见问题自动追加修正词
        fix_map = {
            "运镜不稳": "camera stabilizer, gimbal smooth motion",
            "色调偏暗": "well-exposed, bright highlights, HDR",
            "人脸变形": "perfect facial anatomy, natural face",
            "运动模糊": "sharp motion capture, 120fps",
            "画面单调": "rich visual layers, dynamic depth of field",
            "主体不清晰": "sharp subject focus, shallow depth of field",
        }

        new_extras_parts = [extras] if extras else []
        for issue in issues:
            for key, fix in fix_map.items():
                if key in issue:
                    new_extras_parts.append(fix)

        for suggestion in suggestions:
            new_extras_parts.append(suggestion)

        new_extras = ", ".join(p for p in new_extras_parts if p)

        return self.build(
            user_intent=original["metadata"]["user_intent"],
            style=original["metadata"]["style"],
            shot=original["metadata"]["shot"],
            extras=new_extras,
        )
