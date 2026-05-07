#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ReflectAgent — 自我反思 + 优化建议生成

输入: EvalAgent 的评估结果
输出: 针对每个问题的具体改进方案（结构化反馈）

推理过程（5步 Reflect-Chain）:
  Reflect-1  问题归因（what went wrong?）
  Reflect-2  根本原因分析（why did it fail?）
  Reflect-3  解决策略（which fix applies?）
  Reflect-4  优先级排序（order by impact）
  Reflect-5  生成结构化建议（actionable feedback）
"""

from typing import Dict, Any, List


# ── 问题 → 根本原因 → 修复策略 知识库 ────────────────────────────────
REFLECT_KB = {
    "主体不清晰": {
        "root_cause": "提示词未明确主体焦点或镜头景别",
        "strategy": "shot_type",
        "fix": {
            "issues": ["主体不清晰"],
            "suggestions": ["sharp subject focus, shallow depth of field, bokeh background"],
            "shot_change": "特写",
        },
    },
    "运镜不稳": {
        "root_cause": "未指定稳定器或 fps 不足",
        "strategy": "camera_stability",
        "fix": {
            "issues": ["运镜不稳"],
            "suggestions": ["camera stabilizer, gimbal smooth motion, DJI stabilization"],
        },
    },
    "色调偏暗": {
        "root_cause": "光线描述缺失或环境光不足",
        "strategy": "lighting",
        "fix": {
            "issues": ["色调偏暗"],
            "suggestions": ["well-exposed, bright highlights, HDR tone mapping, golden hour lighting"],
        },
    },
    "运动模糊": {
        "root_cause": "快门速度描述缺失或文件编码质量低",
        "strategy": "shutter_fix",
        "fix": {
            "issues": ["运动模糊"],
            "suggestions": ["sharp motion capture, high shutter speed, crisp details"],
        },
    },
    "画面单调": {
        "root_cause": "提示词缺乏环境层次感或构图指令",
        "strategy": "composition_enrich",
        "fix": {
            "issues": ["画面单调"],
            "suggestions": ["rich visual layers, dynamic depth of field, foreground elements, atmospheric haze"],
        },
    },
    "生成失败": {
        "root_cause": "API 错误或内容违规",
        "strategy": "retry_clean",
        "fix": {
            "issues": ["生成失败"],
            "suggestions": ["simplified prompt, remove sensitive content"],
        },
    },
}


class ReflectAgent:
    """自我反思 Agent：分析评估结果并输出结构化改进建议"""

    def __init__(self):
        self.reflect_trace: List[Dict[str, Any]] = []

    def reflect(
        self,
        eval_result: Dict[str, Any],
        round_num: int = 1,
    ) -> Dict[str, Any]:
        """
        5步 Reflect-Chain 反思推理。

        Args:
            eval_result: EvalAgent.evaluate() 的返回值
            round_num:   当前优化轮次（1-indexed）

        Returns:
            {
                "should_retry": bool,
                "feedback": {issues: [...], suggestions: [...]},
                "priority_issues": [...],     # 按影响排序
                "reflect_trace": [...],
                "round": int,
            }
        """
        self.reflect_trace = []
        issues = eval_result.get("issues", [])
        scores = eval_result.get("scores", {})
        total = eval_result.get("total_score", 0.0)
        passed = eval_result.get("passed", False)

        # Reflect-1: 问题归因
        r1 = self._reflect_1_attribution(issues, scores)

        # Reflect-2: 根本原因分析
        r2 = self._reflect_2_root_cause(r1)

        # Reflect-3: 解决策略
        r3 = self._reflect_3_strategy(r2)

        # Reflect-4: 优先级排序（按权重得分差异）
        r4 = self._reflect_4_priority(r3, scores)

        # Reflect-5: 生成结构化建议
        feedback = self._reflect_5_feedback(r4)

        should_retry = not passed and round_num <= 3

        result = {
            "should_retry": should_retry,
            "feedback": feedback,
            "priority_issues": r4,
            "reflect_trace": self.reflect_trace,
            "round": round_num,
            "total_score": total,
        }
        return result

    # ── Reflect Steps ──────────────────────────────────────────────

    def _reflect_1_attribution(
        self, issues: List[str], scores: Dict[str, float]
    ) -> List[Dict[str, Any]]:
        """Reflect-1: 将 issue 与低分维度关联"""
        attributed = []
        for issue in issues:
            kb = REFLECT_KB.get(issue, {})
            attributed.append({
                "issue": issue,
                "known": bool(kb),
                "kb": kb,
            })
        # 找出得分最低的维度
        if scores:
            worst_dim = min(scores, key=lambda k: scores[k])
            attributed.append({
                "issue": f"低分维度:{worst_dim}({scores[worst_dim]:.2f})",
                "known": False,
                "kb": {},
            })
        self._log("Reflect1_Attribution", issues, attributed)
        return attributed

    def _reflect_2_root_cause(
        self, attributed: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Reflect-2: 提取根本原因"""
        with_cause = []
        for item in attributed:
            cause = item["kb"].get("root_cause", "未知原因，尝试通用优化") if item["known"] else "未知原因"
            with_cause.append({**item, "root_cause": cause})
        self._log("Reflect2_RootCause", len(attributed), with_cause)
        return with_cause

    def _reflect_3_strategy(
        self, with_cause: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Reflect-3: 确定修复策略"""
        with_strategy = []
        for item in with_cause:
            fix = item["kb"].get("fix", {"issues": [], "suggestions": ["improve overall quality"]})
            with_strategy.append({**item, "fix": fix})
        self._log("Reflect3_Strategy", len(with_cause), with_strategy)
        return with_strategy

    def _reflect_4_priority(
        self, with_strategy: List[Dict[str, Any]], scores: Dict[str, float]
    ) -> List[Dict[str, Any]]:
        """Reflect-4: 按问题影响力排序（已知问题优先）"""
        # 已知问题在 KB 中有精准修复，优先处理
        known = [i for i in with_strategy if i["known"]]
        unknown = [i for i in with_strategy if not i["known"]]
        priority = known + unknown
        self._log("Reflect4_Priority", len(with_strategy), [p["issue"] for p in priority])
        return priority

    def _reflect_5_feedback(
        self, priority: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Reflect-5: 聚合所有修复建议为结构化 feedback"""
        all_issues: List[str] = []
        all_suggestions: List[str] = []
        shot_change = None

        for item in priority:
            fix = item.get("fix", {})
            all_issues.extend(fix.get("issues", []))
            all_suggestions.extend(fix.get("suggestions", []))
            if "shot_change" in fix and not shot_change:
                shot_change = fix["shot_change"]

        # 去重
        all_issues = list(dict.fromkeys(all_issues))
        all_suggestions = list(dict.fromkeys(all_suggestions))

        feedback = {
            "issues": all_issues,
            "suggestions": all_suggestions,
        }
        if shot_change:
            feedback["shot_change"] = shot_change

        self._log("Reflect5_Feedback", priority, feedback)
        return feedback

    def _log(self, step: str, inp: Any, out: Any):
        self.reflect_trace.append({"step": step, "input": inp, "output": out})
