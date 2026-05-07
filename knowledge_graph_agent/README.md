# 个人知识图谱 Agent 🧠

> **从文档/代码自动构建知识图谱，支持自然语言问答**  
> 输入你的笔记、代码、文档 → 自动抽取实体和关系 → 构建知识图谱 → 用中文提问

---

## 系统架构

```
文件/目录输入
      │
      ▼
┌──────────────────┐   多格式解析    ┌──────────────────┐
│  DocumentParser  │ ─────────────▶ │  结构化文档      │
│  (文档解析Agent)  │  .md/.py/.txt │  sections+元数据  │
└──────────────────┘  /.json        └──────────────────┘
                                         │
                                         ▼
                              ┌──────────────────────┐
                              │   EntityExtractor     │
                              │  (实体抽取Agent)      │
                              │  4种抽取策略:         │
                              │  1. 关键词精确匹配    │
                              │  2. 正则模式匹配      │
                              │  3. 词频候选名词      │
                              │  4. 代码感知抽取      │
                              └──────────────────────┘
                                         │
                                         ▼
                              ┌──────────────────────┐
                              │   RelationBuilder     │
                              │  (关系推断Agent)      │
                              │  3级推断:             │
                              │  L1. 共现关系         │
                              │  L2. 模式匹配         │
                              │  L3. 结构推断         │
                              └──────────────────────┘
                                         │
                                         ▼
                              ┌──────────────────────┐
                              │   GraphBuilder       │
                              │  (图构建Agent)       │
                              │  • JSON持久化        │
                              │  • DOT导出           │
                              │  • Mermaid导出       │
                              │  • 图统计+Hub分析    │
                              └──────────────────────┘
                                         │
                                         ▼
                              ┌──────────────────────┐
                              │   QueryAgent         │
                              │  (查询Agent)         │
                              │  6种查询模式:         │
                              │  • 实体详情          │
                              │  • 邻居查询          │
                              │  • 关系查询          │
                              │  • 搜索/路径/统计    │
                              └──────────────────────┘
```

---

## 快速开始

### 从代码目录构建图谱

```bash
# 分析一个 Python 项目
python main.py build ./my_project/

# 分析单个文件
python main.py build README.md
```

### 交互式查询

```bash
python main.py query
# Q: 有哪些技术
# Q: Python和什么有关
# Q: 最热门的技术是什么
# Q: 统计
# Q: quit
```

### 单次查询

```bash
python main.py ask "有哪些技术"
python main.py ask "GraphBuilder和QueryAgent的关系"
python main.py ask "最热门的技术"
```

### 一站式（构建+查询）

```bash
python main.py run ./src/ --ask "统计"
```

---

## 核心创新点

### 1. 4策略混合实体抽取（EntityExtractor）

| 策略 | 方法 | 适用场景 |
|------|------|----------|
| 精确匹配 | 100+技术关键词库 + 大小写不敏感 | 已知技术名/公司名 |
| 正则模式 | URL/路径/版本号/驼峰/蛇形名 | 代码中的引用和标识符 |
| 词频候选 | 中文字频统计 + 去虚词 + 类型推断 | 未预注册的专有名词 |
| 代码感知 | import解析/类名/函数名提取 | Python 源码文件 |

### 2. 3级层次关系推断（RelationBuilder）

- **Level 1 — 共现**: 滑动窗口内同现的实体建立 weak link
- **Level 2 — 模式**: 18种中英文关系模板（"X使用Y"/"X depends on Y"...）
- **Level 3 — 结构**: 文档标题中的实体与 section 内容实体的 contains 关系

### 3. 6种自然语言查询模式（QueryAgent）

| 模式 | 示例 | 实现 |
|------|------|------|
| 实体详情 | "Python是什么" | 节点属性 + 邻居列表 |
| 邻居查询 | "Python和什么有关" | 邻接表遍历 + 按类型分组 |
| 关系查询 | "Python和FastAPI的关系" | 直接边匹配 + BFS 间接路径 |
| 搜索 | "有哪些技术" | 按类型过滤 + 度排序 |
| 路径 | "X到Y怎么连" | BFS 最短路径 |
| 统计 | "最热门的技术" | 度分布 + Hub 排序 |

### 4. 多格式可视化导出

- **JSON**: 完整图谱数据，可被其他工具加载
- **DOT**: Graphviz 格式，渲染为高清关系图
- **Mermaid**: 可直接嵌入 Markdown/GitHub 渲染

---

## 实体与关系类型

### 实体类型

| 类型 | 中文 | 例子 |
|------|------|------|
| technology | 技术/框架 | Python, Docker, React, Redis |
| organization | 组织 | Google, 字节跳动, GitHub |
| concept | 概念/理论 | 知识图谱, RAG, Agent, 微服务 |
| project | 项目 | 知识图谱Agent |
| person | 人物 | （从文本中识别） |
| document | 文档 | 论文URL, 文件路径 |
| event | 事件 | （从文本中识别） |
| location | 地点 | （从文本中识别） |

### 关系类型

| 关系 | 中文 | 推断规则 |
|------|------|----------|
| uses | 使用 | 技术→项目, 项目→技术 |
| depends_on | 依赖 | A import B |
| contains | 包含 | 标题实体→section实体 |
| part_of | 属于 | 人→组织 |
| created_by | 创建 | 项目→人 |
| extends | 扩展 | 子类→父类 |
| references | 引用 | 文档→概念 |
| related_to | 相关 | 兜底关系 |

---

## 文件结构

```
knowledge_graph_agent/
├── main.py              # CLI 入口
├── orchestrator.py      # 主控 Agent（构建+查询）
├── document_parser.py   # 文档解析 Agent（4格式）
├── entity_extractor.py  # 实体抽取 Agent（4策略）
├── relation_builder.py  # 关系推断 Agent（3层级）
├── graph_builder.py     # 图构建 Agent（JSON/DOT/Mermaid）
├── query_agent.py       # 查询 Agent（6模式）
├── config.py            # 全局配置
├── README.md            # 使用文档
└── output/              # 构建产物（自动创建）
    ├── knowledge_graph.json
    ├── knowledge_graph.dot
    ├── knowledge_graph.mmd
    └── build_log.json
```

---

## 示例

```bash
# 对自己构建的知识图谱Agent项目做自分析
$ python main.py build ./knowledge_graph_agent/

[Step 1] 文档解析...
  解析完成: 7 个文件
  总 section 数: 42
  总字符数: 28530

[Step 2] 实体抽取...
  config.py: 18 个实体
  entity_extractor.py: 12 个实体
  graph_builder.py: 8 个实体
  ...

[Step 3] 关系推断...
  推断完成: 45 条关系（合并后）

[Step 4] 知识图谱构建...
  节点: 89, 边: 45
  连通分量: 3

$ python main.py ask "最热门的技术"

知识图谱统计:
  节点总数: 89
  关系总数: 45

  关联最多的节点 (Hub):
    Python: 28个关联
    knowledge: 15个关联
    Agent: 12个关联
    ...
```

---

## 注意事项

- 纯 Python 实现，零外部依赖（不需要 NLP 库）
- 支持 Markdown/Python/TXT/JSON 四种输入格式
- 实体识别基于关键词库 + 规则引擎，可自由扩展 config.py
- 图谱数据持久化为 JSON，支持增量更新
- DOT 文件可用 `dot -Tpng knowledge_graph.dot -o graph.png` 渲染
