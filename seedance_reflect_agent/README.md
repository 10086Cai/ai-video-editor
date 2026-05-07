# Seedance Reflect+Retry Agent 🎬

> **AI 视频自优化 Agent** — 基于 Seedance 1.5 Pro + Reflect+Retry 架构  
> 自动生成视频 → 多维评估 → 反思优化 → 再次生成，最多循环 3 轮直到满意

---

## 🏗️ 系统架构

```
用户意图（中文）
      │
      ▼
┌─────────────────┐   7步CoT推理    ┌──────────────────┐
│  PromptAgent    │ ─────────────▶ │  专业提示词       │
│  (提示词专家)    │                │  (英文，多维度)   │
└─────────────────┘                └──────────────────┘
                                          │
                                          ▼
                                  ┌──────────────────┐
                                  │  SeedanceClient  │
                                  │  (火山方舟 API)   │
                                  │  submit→poll→dl  │
                                  └──────────────────┘
                                          │
                                          ▼
                              ┌───────────────────────┐
                              │      EvalAgent        │
                              │  4维度评分:           │
                              │  ・提示词对齐度 40%   │
                              │  ・视觉质量    25%   │
                              │  ・运动流畅度  20%   │
                              │  ・构图合理性  15%   │
                              └───────────────────────┘
                                          │
                              score >= 0.75?
                              YES ──▶ 输出最终视频 ✅
                              NO  ──▶ ReflectAgent
                                          │
                              ┌───────────────────────┐
                              │     ReflectAgent      │
                              │  5步Reflect-Chain:    │
                              │  1. 问题归因          │
                              │  2. 根本原因分析      │
                              │  3. 修复策略选择      │
                              │  4. 优先级排序        │
                              │  5. 结构化建议输出    │
                              └───────────────────────┘
                                          │
                              PromptAgent.refine() ──▶ [下一轮]
```

---

## 🚀 快速开始

### 安装依赖

```bash
pip install -r requirements.txt
```

### 基础用法

```bash
# 最简命令（样片模式，480p，3轮自优化）
python main.py --intent "夕阳下的海浪拍打礁石，慢动作"

# 指定风格和景别
python main.py --intent "赛博朋克城市夜景" --style 赛博朋克 --shot 航拍

# 正式 1080p 高清生成
python main.py --intent "玫瑰花缓缓盛开" --style 自然 --shot 特写 --no-draft --resolution 1080p

# 竖屏抖音格式
python main.py --intent "女孩在咖啡馆看书" --style 电影 --shot 近景 --ratio 9:16

# 输出 JSON（便于自动化处理）
python main.py --intent "雪山日出延时" --style 自然 --shot 航拍 --json-output
```

### 参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--intent` | 视频内容意图（中文自然语言）| 必填 |
| `--style` | 风格: 写实/电影/赛博朋克/卡通/纪录片/商业/自然 | 写实 |
| `--shot` | 景别: 特写/近景/中景/全景/远景/航拍/跟随/推进/拉出/环绕 | 中景 |
| `--resolution` | 分辨率: 480p/720p/1080p | 480p |
| `--ratio` | 宽高比: 16:9/9:16/1:1 | 16:9 |
| `--duration` | 视频时长（秒，2-12）| 5 |
| `--max-rounds` | 最大自优化轮次 | 3 |
| `--no-draft` | 关闭样片模式 | 否 |
| `--extras` | 附加英文提示词 | 空 |

---

## 📁 文件结构

```
seedance_reflect_agent/
├── main.py              # CLI 入口
├── orchestrator.py      # 主控 Agent（Reflect+Retry 循环）
├── prompt_agent.py      # 提示词生成 Agent（7步 CoT）
├── eval_agent.py        # 评估 Agent（4维度）
├── reflect_agent.py     # 反思 Agent（5步 Reflect-Chain）
├── seedance_client.py   # 火山方舟 Seedance API 客户端
├── config.py            # 全局配置
├── requirements.txt     # 依赖
├── output/              # 生成的视频（自动创建）
└── logs/                # 每次运行的 JSON 日志（自动创建）
```

---

## 🧠 核心创新点

### 1. 7步 CoT 提示词推理（PromptAgent）

```
Step 1  解析用户意图 → 主体/场景/动作
Step 2  镜头语言     → 景别/运镜英文描述
Step 3  环境细节     → 时段/天气/氛围（自动从中文推断）
Step 4  风格标签     → 写实/电影/赛博朋克
Step 5  节奏词       → slow motion / timelapse / dynamic
Step 6  负向约束     → 排除水印/文字/低质量
Step 7  组合输出     → 最终专业英文提示词
```

### 2. 5步 Reflect-Chain 反思链（ReflectAgent）

```
Reflect-1  问题归因  → 将 issue 与低分维度关联
Reflect-2  根本原因  → 从知识库查找根本原因
Reflect-3  修复策略  → 匹配对应的修复 prompt 片段
Reflect-4  优先排序  → 按影响力排序（已知问题优先）
Reflect-5  结构输出  → 生成 {issues, suggestions} 反馈
```

### 3. 4维度评估体系（EvalAgent）

| 维度 | 权重 | 评估方法 |
|------|------|----------|
| 提示词对齐度 | 40% | 文件大小 + API 状态 + 关键词覆盖率 |
| 视觉质量 | 25% | 文件大小推断码率 + 分辨率参数 |
| 运动流畅度 | 20% | FPS 参数 + 样片模式判断 |
| 构图合理性 | 15% | 提示词中构图关键词覆盖数 |

---

## 📊 示例输出

```
════════════════════════════════════════════════════════════
  Seedance Reflect+Retry Agent  |  Job: 20260507_143000
════════════════════════════════════════════════════════════
  用户意图  : 夕阳下的海浪拍打礁石，慢动作
  风格      : 电影
  景别      : 全景
  最大轮次  : 3
  通过阈值  : 0.75

──────────────────────────────────────────────────
  第 1 轮  (max=3)
──────────────────────────────────────────────────
[PromptAgent] 最终提示词:
  夕阳下的海浪拍打礁石，慢动作, full shot (FS), golden hour, sunset...
[Seedance] 任务提交成功，task_id=cgt-xxx
[EvalAgent] 综合得分: 0.7200  通过: False
            问题: ['运镜不稳']

[ReflectAgent] 反思完成，建议: {issues: ['运镜不稳'], suggestions: ['camera stabilizer...']}

  第 2 轮  (max=3)
──────────────────────────────────────────────────
[PromptAgent] 最终提示词（优化后）:
  ...camera stabilizer, gimbal smooth motion...
[EvalAgent] 综合得分: 0.8100  通过: True

✅ 第 2 轮通过！得分 0.8100 >= 0.75

════════════════════════════════════════════════════════════
  最终结果
════════════════════════════════════════════════════════════
  状态      : ✅ 成功
  最优得分  : 0.8100
  执行轮次  : 2
  视频文件  : output/20260507_143000_round2.mp4
  日志文件  : logs/20260507_143000_log.json
════════════════════════════════════════════════════════════
```

---

## ⚙️ 配置说明（config.py）

```python
MAX_RETRY_ROUNDS = 3        # 最多自优化轮次
MIN_SCORE_THRESHOLD = 0.75  # 通过得分阈值
DEFAULT_DRAFT = True        # 默认样片模式（省配额）
EVAL_WEIGHTS = {
    "prompt_alignment": 0.40,
    "visual_quality": 0.25,
    "motion_smoothness": 0.20,
    "composition": 0.15,
}
```

---

## 📌 注意事项

- **API 配额**：每次视频生成消耗配额，建议先用样片模式（默认）测试
- **生成时间**：每轮约 60-180 秒，3轮最多 ~9 分钟
- **视频有效期**：Seedance 视频 URL 48小时后失效，已自动下载到 `output/`
- **日志追溯**：每次运行在 `logs/` 保存完整 JSON 日志，含每轮 CoT 推理详情
