#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EvalAgent — 对已生成的视频进行多维度评估
（纯本地启发式评分 + 可选 LLM 描述解析）

评估维度（对应 config.EVAL_WEIGHTS）：
  1. prompt_alignment  提示词对齐度
  2. visual_quality    视觉质量（分辨率/编码）
  3. motion_smoothness 运动流畅度
  4. composition       构图合理性

返回格式:
{
  "total_score": 0.0~1.0,
  "scores": {dimension: 0.0~1.0, ...},
  "passed": bool,
  "issues": [...],         # 发现的问题列表
  "eval_trace": [...],     # 每步评估详情
}
"""

import os
import json
from typing import Dict, Any, List, Optional
from config import EVAL_WEIGHTS, MIN_SCORE_THRESHOLD


class EvalAgent:
    """多维度视频质量评估 Agent"""

    def __init__(self):
        self.eval_trace: List[Dict[str, Any]] = []

    def evaluate(
        self,
        video_path: str,
        prompt_result: Dict[str, Any],
        generation_meta: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        对生成的视频进行综合评估。

        Args:
            video_path: 本地视频文件路径
            prompt_result: PromptAgent.build() 的返回值
            generation_meta: Seedance API 返回的元数据（可选）

        Returns:
            评估结果字典
        """
        self.eval_trace = []
        scores: Dict[str, float] = {}
        issues: List[str] = []

        final_prompt = prompt_result.get("final_prompt", "")
        user_intent = prompt_result.get("metadata", {}).get("user_intent", "")

        # ── 维度 1: 提示词对齐度 ─────────────────────────────────────
        s1, i1 = self._eval_prompt_alignment(
            video_path, final_prompt, user_intent, generation_meta
        )
        scores["prompt_alignment"] = s1
        issues.extend(i1)

        # ── 维度 2: 视觉质量 ─────────────────────────────────────────
        s2, i2 = self._eval_visual_quality(video_path, generation_meta)
        scores["visual_quality"] = s2
        issues.extend(i2)

        # ── 维度 3: 运动流畅度 ───────────────────────────────────────
        s3, i3 = self._eval_motion_smoothness(generation_meta)
        scores["motion_smoothness"] = s3
        issues.extend(i3)

        # ── 维度 4: 构图 ─────────────────────────────────────────────
        s4, i4 = self._eval_composition(final_prompt, generation_meta)
        scores["composition"] = s4
        issues.extend(i4)

        # ── 加权合分 ─────────────────────────────────────────────────
        total = sum(scores[k] * EVAL_WEIGHTS[k] for k in scores)

        result = {
            "total_score": round(total, 4),
            "scores": {k: round(v, 4) for k, v in scores.items()},
            "passed": total >= MIN_SCORE_THRESHOLD,
            "issues": list(dict.fromkeys(issues)),   # 去重
            "eval_trace": self.eval_trace,
        }
        self._log("FinalScore", scores, result["total_score"])
        return result

    # ── 各维度评估方法 ────────────────────────────────────────────────

    def _eval_prompt_alignment(
        self, video_path: str, prompt: str,
        user_intent: str, meta: Optional[Dict]
    ) -> tuple[float, List[str]]:
        """
        维度1：提示词对齐度
        - 文件存在且不为空        +0.4
        - API 返回 succeeded     +0.3
        - prompt 关键词覆盖度    +0.3
        """
        score = 0.0
        issues: List[str] = []

        # 文件存在
        if os.path.isfile(video_path) and os.path.getsize(video_path) > 1024:
            score += 0.4
        else:
            issues.append("主体不清晰")
            self._log("PromptAlignment/file", video_path, "文件缺失或过小")
            return 0.0, issues

        # API 状态
        if meta and meta.get("status") == "succeeded":
            score += 0.3
        elif meta and meta.get("status") == "failed":
            issues.append("生成失败")
            self._log("PromptAlignment/api", meta, "API 状态 failed")
            return score, issues
        else:
            score += 0.15  # 无 meta 时给一半

        # 关键词覆盖率（用户意图中的中文词是否出现在 prompt 中）
        keywords = [w for w in user_intent if '\u4e00' <= w <= '\u9fff']
        if keywords:
            # 提取最多5个代表性汉字
            keywords = list(dict.fromkeys(keywords))[:5]
            # 将 prompt 中的中文部分提取出来（可能有翻译词，宽松匹配）
            # 这里用简单策略：用户意图包含的核心动词/名词期望被 prompt 覆盖
            covered = sum(1 for k in keywords if k in prompt or k in (meta or {}).get("used_prompt", ""))
            coverage = covered / len(keywords) if keywords else 1.0
            score += 0.3 * coverage
            if coverage < 0.5:
                issues.append("画面单调")
        else:
            score += 0.3

        self._log("PromptAlignment", {"file": video_path, "keywords": keywords[:5] if keywords else []}, score)
        return min(score, 1.0), issues

    def _eval_visual_quality(
        self, video_path: str, meta: Optional[Dict]
    ) -> tuple[float, List[str]]:
        """
        维度2：视觉质量
        - 文件大小推断码率/质量
        - API 分辨率参数
        """
        score = 0.8   # 基准分（已生成即视为基础质量达标）
        issues: List[str] = []

        if not os.path.isfile(video_path):
            return 0.0, ["主体不清晰"]

        file_size_mb = os.path.getsize(video_path) / (1024 * 1024)

        # 文件大小合理性（5秒视频期望 > 1MB）
        if file_size_mb < 0.5:
            score -= 0.3
            issues.append("运动模糊")
        elif file_size_mb < 1.0:
            score -= 0.1

        # 分辨率参数加分
        resolution = (meta or {}).get("parameters", {}).get("resolution", "")
        if resolution == "1080p":
            score += 0.15
        elif resolution == "720p":
            score += 0.05
        elif resolution == "480p":
            score -= 0.05   # 样片模式扣少量分

        self._log("VisualQuality", {"size_mb": round(file_size_mb, 2), "resolution": resolution}, score)
        return min(max(score, 0.0), 1.0), issues

    def _eval_motion_smoothness(
        self, meta: Optional[Dict]
    ) -> tuple[float, List[str]]:
        """
        维度3：运动流畅度
        依据 fps / draft 参数推断
        """
        score = 0.75
        issues: List[str] = []

        params = (meta or {}).get("parameters", {})
        fps = params.get("fps", 24)
        is_draft = params.get("draft", False)

        if fps >= 60:
            score = 0.95
        elif fps >= 30:
            score = 0.85
        elif fps >= 24:
            score = 0.75
        else:
            score = 0.55
            issues.append("运镜不稳")

        if is_draft:
            score -= 0.1   # 样片模式降帧率

        self._log("MotionSmoothness", {"fps": fps, "draft": is_draft}, score)
        return min(max(score, 0.0), 1.0), issues

    def _eval_composition(
        self, prompt: str, meta: Optional[Dict]
    ) -> tuple[float, List[str]]:
        """
        维度4：构图合理性
        检查 prompt 中是否包含构图关键词
        """
        score = 0.7
        issues: List[str] = []

        composition_keywords = [
            "close-up", "wide", "shot", "aerial", "tracking",
            "push-in", "pull-out", "orbit", "establishing",
        ]
        found = sum(1 for kw in composition_keywords if kw in prompt.lower())
        if found >= 3:
            score = 0.95
        elif found >= 1:
            score = 0.80
        else:
            score = 0.60
            issues.append("画面单调")

        self._log("Composition", {"found_keywords": found}, score)
        return score, issues

    # ── 工具 ──────────────────────────────────────────────────────────

    def _log(self, step: str, inp: Any, out: Any):
        self.eval_trace.append({"step": step, "input": inp, "output": out})
