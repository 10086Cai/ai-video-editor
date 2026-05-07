#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Orchestrator — 主控 Agent，协调整个 Reflect+Retry 循环

完整流程：
  ┌─────────────────────────────────────────────────────────┐
  │  用户输入 (user_intent)                                  │
  │      │                                                  │
  │  [Round 1..MAX_RETRY_ROUNDS]                            │
  │      │                                                  │
  │  PromptAgent.build()  ─── 7步CoT生成提示词              │
  │      │                                                  │
  │  SeedanceClient.generate_and_download()  ── 生成视频    │
  │      │                                                  │
  │  EvalAgent.evaluate()  ─── 多维度评分                   │
  │      │                                                  │
  │  score >= threshold ? ──YES──▶ 返回最终结果             │
  │      │                                                  │
  │      NO                                                 │
  │      │                                                  │
  │  ReflectAgent.reflect()  ─── 反思 + 生成 feedback       │
  │      │                                                  │
  │  PromptAgent.refine_with_feedback()  ── 提示词优化       │
  │      │                                                  │
  │  [下一轮]                                               │
  └─────────────────────────────────────────────────────────┘
"""

import os
import json
import time
from datetime import datetime
from typing import Dict, Any, Optional

from config import (
    SEEDANCE_API_KEY, SEEDANCE_MODEL_ID,
    DEFAULT_RESOLUTION, DEFAULT_RATIO, DEFAULT_DURATION,
    DEFAULT_FPS, DEFAULT_DRAFT,
    MAX_RETRY_ROUNDS, MIN_SCORE_THRESHOLD,
    OUTPUT_DIR, LOG_DIR,
)
from prompt_agent import PromptAgent
from eval_agent import EvalAgent
from reflect_agent import ReflectAgent
from seedance_client import SeedanceClient


class Orchestrator:
    """Reflect+Retry 主控 Agent"""

    def __init__(
        self,
        api_key: str = SEEDANCE_API_KEY,
        model_id: str = SEEDANCE_MODEL_ID,
        max_rounds: int = MAX_RETRY_ROUNDS,
        resolution: str = DEFAULT_RESOLUTION,
        ratio: str = DEFAULT_RATIO,
        duration: int = DEFAULT_DURATION,
        draft: bool = DEFAULT_DRAFT,
        verbose: bool = True,
    ):
        self.seedance = SeedanceClient(api_key=api_key, model_id=model_id)
        self.prompt_agent = PromptAgent()
        self.eval_agent = EvalAgent()
        self.reflect_agent = ReflectAgent()
        self.max_rounds = max_rounds
        self.resolution = resolution
        self.ratio = ratio
        self.duration = duration
        self.draft = draft
        self.verbose = verbose

        os.makedirs(OUTPUT_DIR, exist_ok=True)
        os.makedirs(LOG_DIR, exist_ok=True)

    # ── 主入口 ────────────────────────────────────────────────────────

    def run(
        self,
        user_intent: str,
        style: str = "写实",
        shot: str = "中景",
        extras: str = "",
        job_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        执行完整的 Reflect+Retry 循环。

        Returns:
            {
                "success": bool,
                "best_video_path": str,
                "best_score": float,
                "rounds": int,
                "history": [...],     # 每轮详情
                "final_prompt": str,
            }
        """
        job_id = job_id or datetime.now().strftime("%Y%m%d_%H%M%S")
        self._log(f"\n{'═'*60}")
        self._log(f"  Seedance Reflect+Retry Agent  |  Job: {job_id}")
        self._log(f"{'═'*60}")
        self._log(f"  用户意图  : {user_intent}")
        self._log(f"  风格      : {style}")
        self._log(f"  景别      : {shot}")
        self._log(f"  最大轮次  : {self.max_rounds}")
        self._log(f"  通过阈值  : {MIN_SCORE_THRESHOLD}")
        self._log(f"{'═'*60}\n")

        history = []
        best_score = 0.0
        best_video_path = ""
        best_prompt_result = None
        prompt_result = None

        for round_num in range(1, self.max_rounds + 1):
            self._log(f"\n{'─'*50}")
            self._log(f"  第 {round_num} 轮  (max={self.max_rounds})")
            self._log(f"{'─'*50}")

            # ── Step A: 生成 / 优化提示词 ─────────────────────────────
            if round_num == 1:
                prompt_result = self.prompt_agent.build(
                    user_intent=user_intent, style=style, shot=shot, extras=extras
                )
            # else: 已由上轮 reflect 更新 prompt_result

            self._log(f"[PromptAgent] 最终提示词:\n  {prompt_result['final_prompt'][:120]}...")

            # ── Step B: 生成视频 ──────────────────────────────────────
            video_path = os.path.join(OUTPUT_DIR, f"{job_id}_round{round_num}.mp4")
            generation_meta = None
            gen_success = False

            try:
                # 先只提交，拿到 task_id
                create_resp = self.seedance.create_video(
                    prompt=prompt_result["final_prompt"],
                    resolution=self.resolution,
                    ratio=self.ratio,
                    duration=self.duration,
                    fps=DEFAULT_FPS,
                    draft=self.draft,
                )
                task_id = (
                    create_resp.get("id")
                    or create_resp.get("task_id")
                    or (create_resp.get("data") or {}).get("task_id")
                )
                if not task_id:
                    raise RuntimeError(f"未获取 task_id: {create_resp}")

                self._log(f"[Seedance] 任务提交成功，task_id={task_id}")

                # 等待完成
                gen_result = self.seedance.wait_for_video(task_id)
                generation_meta = {**gen_result, "parameters": {
                    "resolution": self.resolution,
                    "ratio": self.ratio,
                    "duration": self.duration,
                    "fps": DEFAULT_FPS,
                    "draft": self.draft,
                }}

                # 提取 video_url
                video_url = ""
                content_data = gen_result.get("content")
                if isinstance(content_data, dict):
                    video_url = content_data.get("video_url", "")
                if not video_url:
                    videos = gen_result.get("videos", [])
                    if videos:
                        video_url = videos[0].get("url", "") if isinstance(videos[0], dict) else ""

                if video_url:
                    self.seedance.download_video(video_url, video_path)
                    gen_success = True
                    self._log(f"[Seedance] 视频已下载: {video_path}")
                else:
                    self._log("[Seedance] ⚠️ 无视频 URL，跳过下载")

            except Exception as e:
                self._log(f"[Seedance] ❌ 生成失败: {e}")
                generation_meta = {"status": "failed", "error": str(e)}

            # ── Step C: 评估 ──────────────────────────────────────────
            eval_result = self.eval_agent.evaluate(
                video_path=video_path,
                prompt_result=prompt_result,
                generation_meta=generation_meta,
            )
            score = eval_result["total_score"]
            self._log(f"[EvalAgent] 综合得分: {score:.4f}  通过: {eval_result['passed']}")
            self._log(f"            各维度: {eval_result['scores']}")
            self._log(f"            问题: {eval_result['issues']}")

            # 记录最优
            if score > best_score:
                best_score = score
                best_video_path = video_path if gen_success else best_video_path
                best_prompt_result = prompt_result

            # 保存轮次记录
            round_record = {
                "round": round_num,
                "prompt": prompt_result["final_prompt"],
                "video_path": video_path if gen_success else None,
                "eval": eval_result,
            }
            history.append(round_record)

            # 判断是否通过
            if eval_result["passed"]:
                self._log(f"\n✅ 第 {round_num} 轮通过！得分 {score:.4f} >= {MIN_SCORE_THRESHOLD}")
                break

            # ── Step D: 反思 + 更新提示词 ─────────────────────────────
            if round_num < self.max_rounds:
                reflect_result = self.reflect_agent.reflect(eval_result, round_num=round_num)
                self._log(f"[ReflectAgent] 反思完成，建议: {reflect_result['feedback']}")

                # 用反馈优化提示词
                shot_override = reflect_result["feedback"].get("shot_change", shot)
                prompt_result = self.prompt_agent.refine_with_feedback(
                    original=prompt_result,
                    feedback=reflect_result["feedback"],
                )
                # 如果 reflect 建议改变景别
                if shot_override != shot:
                    self._log(f"[ReflectAgent] 景别调整: {shot} → {shot_override}")
                    shot = shot_override

                round_record["reflect"] = reflect_result
            else:
                self._log(f"\n⚠️ 已达最大轮次 {self.max_rounds}，输出最优结果")

        # ── 保存 JSON 日志 ─────────────────────────────────────────────
        log_path = os.path.join(LOG_DIR, f"{job_id}_log.json")
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(
                {"job_id": job_id, "user_intent": user_intent,
                 "best_score": best_score, "history": history},
                f, ensure_ascii=False, indent=2, default=str,
            )
        self._log(f"\n📝 日志已保存: {log_path}")

        return {
            "success": best_score >= MIN_SCORE_THRESHOLD,
            "best_video_path": best_video_path,
            "best_score": best_score,
            "rounds": len(history),
            "history": history,
            "final_prompt": best_prompt_result["final_prompt"] if best_prompt_result else "",
            "log_path": log_path,
        }

    # ── 工具 ──────────────────────────────────────────────────────────

    def _log(self, msg: str):
        if self.verbose:
            print(msg)
