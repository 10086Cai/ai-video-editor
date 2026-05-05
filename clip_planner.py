# clip_planner.py - 长链推理 + 智能剪辑方案规划模块

import logging
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from config import (
    MIN_CLIP_DURATION,
    MAX_CLIP_DURATION,
    TARGET_DURATION,
    MAX_REASONING_STEPS,
)
from video_analyzer import SceneSegment

logger = logging.getLogger("ClipPlanner")


@dataclass
class ClipSegment:
    """单个剪辑片段"""
    clip_id: int
    start_time: float
    end_time: float
    source_scene_id: int
    priority: int        # 优先级 1(最高) ~ 5(最低)
    reason: str          # 保留原因（推理日志）
    transition: str = "cut"  # 转场方式: cut / fade / dissolve

    @property
    def duration(self) -> float:
        return self.end_time - self.start_time


@dataclass
class EditPlan:
    """完整剪辑方案"""
    clips: List[ClipSegment] = field(default_factory=list)
    total_duration: float = 0.0
    reasoning_log: List[str] = field(default_factory=list)

    def add_clip(self, clip: ClipSegment):
        self.clips.append(clip)
        self.total_duration += clip.duration

    def add_log(self, msg: str):
        self.reasoning_log.append(msg)
        logger.info(f"  [推理] {msg}")


class ClipPlanner:
    """
    剪辑规划器 Agent（长链推理核心）

    推理流程（CoT Chain-of-Thought）：
    Step 1: 评估总时长 → 确定目标时长
    Step 2: 场景质量评估 → 过滤低质量场景
    Step 3: 场景时长检查 → 裁剪过长/合并过短片段
    Step 4: 优先级排序 → 按重要性排列
    Step 5: 目标时长对齐 → 动态取舍片段
    Step 6: 转场规划 → 分配过渡效果
    Step 7: 最终校验 → 确保片段连续性
    """

    def __init__(self, scenes: List[SceneSegment], video_duration: float):
        self.scenes = scenes
        self.video_duration = video_duration
        self.plan = EditPlan()
        self.step = 0
        logger.info(
            f"[ClipPlanner] 初始化，场景数：{len(scenes)}，"
            f"视频时长：{video_duration:.2f}s"
        )

    def _next_step(self, description: str):
        self.step += 1
        msg = f"Step {self.step}: {description}"
        self.plan.add_log(msg)
        if self.step > MAX_REASONING_STEPS:
            raise RuntimeError("超出最大推理步数，终止规划")

    def plan_edit(self) -> EditPlan:
        """执行完整的长链推理规划，返回剪辑方案"""
        logger.info("[ClipPlanner] 开始长链推理规划...")

        # Step 1: 确定目标时长
        target = self._step1_determine_target()

        # Step 2: 场景质量过滤
        good_scenes = self._step2_filter_quality()

        # Step 3: 时长规范化
        normalized = self._step3_normalize_duration(good_scenes)

        # Step 4: 优先级排序
        ranked = self._step4_rank_priority(normalized)

        # Step 5: 时长对齐
        selected = self._step5_align_duration(ranked, target)

        # Step 6: 转场规划
        self._step6_plan_transitions(selected)

        # Step 7: 最终校验
        self._step7_final_verify()

        logger.info(
            f"[ClipPlanner] 规划完成：{len(self.plan.clips)} 个片段，"
            f"总时长 {self.plan.total_duration:.2f}s"
        )
        return self.plan

    # ─────────────────────────────────────────────
    # Step 1: 确定目标时长
    # ─────────────────────────────────────────────
    def _step1_determine_target(self) -> float:
        if TARGET_DURATION > 0:
            target = float(TARGET_DURATION)
            self._next_step(
                f"用户指定目标时长 {target}s"
            )
        else:
            # 自动策略：保留原视频约 40%~60% 的内容
            target = self.video_duration * 0.5
            self._next_step(
                f"自动目标时长 = 原时长 {self.video_duration:.1f}s × 50% "
                f"= {target:.1f}s（无用户指定）"
            )
        return target

    # ─────────────────────────────────────────────
    # Step 2: 场景质量过滤
    # ─────────────────────────────────────────────
    def _step2_filter_quality(self) -> List[SceneSegment]:
        self._next_step("场景质量过滤：去除过暗/过亮/极短场景")
        good = []
        dropped = []
        for s in self.scenes:
            reasons = []
            # 过暗（亮度 < 20）
            if s.avg_brightness < 20:
                reasons.append(f"过暗(亮度={s.avg_brightness:.1f})")
            # 过亮（亮度 > 235）
            if s.avg_brightness > 235:
                reasons.append(f"过亮(亮度={s.avg_brightness:.1f})")
            # 时长太短（< 1s）
            if s.duration < 1.0:
                reasons.append(f"时长太短({s.duration:.2f}s)")

            if reasons:
                dropped.append((s.scene_id, ", ".join(reasons)))
            else:
                good.append(s)

        if dropped:
            self.plan.add_log(
                f"  过滤掉 {len(dropped)} 个低质量场景：" +
                "; ".join(f"场景{sid}({r})" for sid, r in dropped)
            )
        self.plan.add_log(f"  保留 {len(good)} / {len(self.scenes)} 个场景")
        return good

    # ─────────────────────────────────────────────
    # Step 3: 时长规范化
    # ─────────────────────────────────────────────
    def _step3_normalize_duration(
        self, scenes: List[SceneSegment]
    ) -> List[Tuple[float, float, SceneSegment]]:
        """
        返回 (start, end, scene) 列表，对超长片段做截断
        """
        self._next_step(
            f"时长规范化：MIN={MIN_CLIP_DURATION}s, MAX={MAX_CLIP_DURATION}s"
        )
        result = []
        for s in scenes:
            start = s.start_time
            end = s.end_time
            dur = end - start

            if dur > MAX_CLIP_DURATION:
                # 超长：取场景最佳帧附近的片段
                best_t = s.keyframe.timestamp
                clip_start = max(start, best_t - MAX_CLIP_DURATION / 2)
                clip_end = min(end, clip_start + MAX_CLIP_DURATION)
                self.plan.add_log(
                    f"  场景{s.scene_id} 时长 {dur:.1f}s 超限，"
                    f"裁剪为 [{clip_start:.1f}s, {clip_end:.1f}s]"
                )
                start, end = clip_start, clip_end

            elif dur < MIN_CLIP_DURATION:
                # 过短：向后扩展（不超过视频结尾）
                end = min(s.end_time + (MIN_CLIP_DURATION - dur), self.video_duration)
                self.plan.add_log(
                    f"  场景{s.scene_id} 时长 {dur:.1f}s 不足，"
                    f"扩展至 [{start:.1f}s, {end:.1f}s]"
                )

            result.append((start, end, s))

        return result

    # ─────────────────────────────────────────────
    # Step 4: 优先级排序
    # ─────────────────────────────────────────────
    def _step4_rank_priority(
        self, segments: List[Tuple[float, float, SceneSegment]]
    ) -> List[Tuple[float, float, SceneSegment, int]]:
        """
        优先级规则（长链推理）：
        - 关键帧清晰度高 → 优先级高
        - 场景发生切换 → 优先级提升
        - 亮度适中（60~180）→ 额外加分
        - 时长适中（MIN~MAX/2）→ 额外加分
        """
        self._next_step("优先级评分：综合清晰度/场景变化/亮度/时长")
        ranked = []
        for start, end, scene in segments:
            score = scene.keyframe.blur_score  # 清晰度基础分

            # 亮度适中加分
            if 60 <= scene.avg_brightness <= 180:
                score += 50

            # 时长适中加分
            dur = end - start
            if MIN_CLIP_DURATION <= dur <= MAX_CLIP_DURATION / 2:
                score += 30

            # 场景切换帧加分
            if scene.keyframe.scene_change:
                score += 40

            # 映射为 1~5 优先级
            priority = 1 if score > 200 else 2 if score > 100 else 3 if score > 50 else 4

            ranked.append((start, end, scene, priority))
            self.plan.add_log(
                f"  场景{scene.scene_id} 评分={score:.1f} → 优先级{priority}"
            )

        # 按优先级升序（1 最高）
        ranked.sort(key=lambda x: x[3])
        return ranked

    # ─────────────────────────────────────────────
    # Step 5: 目标时长对齐
    # ─────────────────────────────────────────────
    def _step5_align_duration(
        self,
        ranked: List[Tuple[float, float, SceneSegment, int]],
        target: float,
    ) -> List[ClipSegment]:
        self._next_step(f"目标时长对齐：贪心选取片段，目标 {target:.1f}s")
        selected = []
        total = 0.0
        clip_id = 0

        for start, end, scene, priority in ranked:
            dur = end - start
            if target > 0 and total + dur > target * 1.2:
                # 已超出目标 120%，跳过
                self.plan.add_log(
                    f"  跳过场景{scene.scene_id}：加入后总时长 "
                    f"{total+dur:.1f}s 超出目标 20%"
                )
                continue

            clip = ClipSegment(
                clip_id=clip_id,
                start_time=start,
                end_time=end,
                source_scene_id=scene.scene_id,
                priority=priority,
                reason=f"优先级{priority}，时长{dur:.1f}s",
            )
            selected.append(clip)
            total += dur
            clip_id += 1

            self.plan.add_log(
                f"  选入场景{scene.scene_id} [{start:.1f}s~{end:.1f}s]，"
                f"累计时长 {total:.1f}s"
            )

        # 按时间顺序重排
        selected.sort(key=lambda c: c.start_time)
        self.plan.add_log(
            f"  最终选入 {len(selected)} 个片段，总时长 {total:.1f}s"
        )
        return selected

    # ─────────────────────────────────────────────
    # Step 6: 转场规划
    # ─────────────────────────────────────────────
    def _step6_plan_transitions(self, clips: List[ClipSegment]):
        self._next_step("转场规划：分配过渡效果")
        for i, clip in enumerate(clips):
            if i == 0:
                clip.transition = "cut"
            elif clips[i].start_time - clips[i - 1].end_time < 0.5:
                # 紧密相邻 → 直接切
                clip.transition = "cut"
            else:
                # 有间隔 → 淡入淡出
                clip.transition = "fade"
            self.plan.add_clip(clip)
            self.plan.add_log(
                f"  片段{clip.clip_id} 转场: {clip.transition}"
            )

    # ─────────────────────────────────────────────
    # Step 7: 最终校验
    # ─────────────────────────────────────────────
    def _step7_final_verify(self):
        self._next_step("最终校验：确保片段合法性")
        issues = []
        for clip in self.plan.clips:
            if clip.start_time >= clip.end_time:
                issues.append(f"片段{clip.clip_id}: start >= end")
            if clip.duration < 0.1:
                issues.append(f"片段{clip.clip_id}: 时长过短 ({clip.duration:.2f}s)")

        if issues:
            self.plan.add_log(f"  ⚠ 发现 {len(issues)} 个问题: {'; '.join(issues)}")
            # 过滤非法片段
            self.plan.clips = [
                c for c in self.plan.clips
                if c.start_time < c.end_time and c.duration >= 0.1
            ]
            self.plan.total_duration = sum(c.duration for c in self.plan.clips)
        else:
            self.plan.add_log("  ✓ 所有片段校验通过")

    def print_plan(self):
        """打印剪辑方案摘要"""
        print("\n" + "=" * 60)
        print("📋 剪辑方案摘要")
        print("=" * 60)
        for clip in self.plan.clips:
            print(
                f"  片段 {clip.clip_id:02d} | "
                f"[{clip.start_time:7.2f}s ~ {clip.end_time:7.2f}s] "
                f"| {clip.duration:5.2f}s "
                f"| 优先级{clip.priority} "
                f"| 转场:{clip.transition}"
            )
        print(f"\n  总片段数: {len(self.plan.clips)}")
        print(f"  总时长:   {self.plan.total_duration:.2f}s")
        print("=" * 60)
        print("\n📝 推理日志：")
        for log in self.plan.reasoning_log:
            print(f"  {log}")
