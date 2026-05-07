#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全局配置 — 个人知识图谱 Agent
"""

# ── 实体类型定义 ─────────────────────────────────────────────────────
ENTITY_TYPES = {
    "person": "人物",
    "project": "项目",
    "technology": "技术/框架",
    "concept": "概念/理论",
    "event": "事件",
    "organization": "组织",
    "document": "文档/论文",
    "location": "地点",
}

# ── 关系类型定义 ─────────────────────────────────────────────────────
RELATION_TYPES = {
    "uses": "使用",
    "part_of": "属于",
    "depends_on": "依赖于",
    "contains": "包含",
    "related_to": "相关",
    "created_by": "创建者",
    "works_on": "参与",
    "located_in": "位于",
    "references": "引用",
    "precedes": "先于",
    "extends": "扩展",
}

# ── 抽取规则 ─────────────────────────────────────────────────────────
# 实体识别关键词映射
ENTITY_KEYWORDS = {
    "technology": [
        "Python", "Java", "JavaScript", "TypeScript", "Go", "Rust", "C++",
        "React", "Vue", "Angular", "Django", "Flask", "FastAPI", "Spring",
        "Docker", "Kubernetes", "K8s", "MySQL", "PostgreSQL", "Redis",
        "MongoDB", "Elasticsearch", "TensorFlow", "PyTorch", "GPT",
        "LLM", "RAG", "Agent", "API", "REST", "GraphQL", "WebSocket",
        "OpenCV", "FFmpeg", "Git", "Linux", "Nginx", "Node.js",
        "Seedance", "LangChain", "LlamaIndex", "HuggingFace",
    ],
    "organization": [
        "Google", "Meta", "OpenAI", "Microsoft", "Apple", "Amazon",
        "字节跳动", "腾讯", "阿里巴巴", "百度", "华为", "火山方舟",
        "GitHub", "Stack Overflow", "Reddit", "知乎", "CSDN",
    ],
    "concept": [
        "机器学习", "深度学习", "神经网络", "自然语言处理", "NLP",
        "计算机视觉", "知识图谱", "强化学习", "迁移学习",
        "微服务", "容器化", "CI/CD", "敏捷开发", "DevOps",
        "CoT", "Prompt Engineering", "RAG", "Agent", "Reflection",
        "向量数据库", "Embedding", "Attention", "Transformer",
        "多模态", "Few-shot", "Zero-shot", "Fine-tuning",
    ],
}

# ── 知识图谱存储 ──────────────────────────────────────────────────────
GRAPH_STORE_FILE = "knowledge_graph.json"
DOT_EXPORT_FILE = "knowledge_graph.dot"

# ── 输出 ──────────────────────────────────────────────────────────────
OUTPUT_DIR = "output"
