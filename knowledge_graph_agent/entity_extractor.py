#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EntityExtractor — 实体识别与分类 Agent

采用多策略混合抽取:
  Strategy 1: 精确匹配（关键词库 + 大小写敏感）
  Strategy 2: 正则模式（人名/版本号/邮箱/URL/路径）
  Strategy 3: 上下文推断（段落中的技术名词识别）
  Strategy 4: 代码感知（import语句中的模块名/类名）

输出:
{
    "entities": [
        {"name": str, "type": str, "source": str, "confidence": float, "context": str}
    ],
    "extraction_trace": [...]
}
"""

import re
import os
from typing import Dict, Any, List, Set, Optional
from config import ENTITY_TYPES, ENTITY_KEYWORDS


class EntityExtractor:
    """多策略实体抽取 Agent"""

    def __init__(self, custom_keywords: Optional[Dict[str, List[str]]] = None):
        self.keywords = {k: list(v) for k, v in ENTITY_KEYWORDS.items()}
        if custom_keywords:
            for k, v in custom_keywords.items():
                self.keywords.setdefault(k, []).extend(v)
        self.extraction_trace: List[Dict[str, Any]] = []

    # ── 主入口 ────────────────────────────────────────────────────────

    def extract(self, parsed_doc: Dict[str, Any]) -> Dict[str, Any]:
        """从解析后的文档中抽取所有实体"""
        self.extraction_trace = []
        seen: Set[str] = set()
        entities: List[Dict[str, Any]] = []
        raw_text = parsed_doc.get("raw_text", "")
        sections = parsed_doc.get("sections", [])
        source = parsed_doc.get("source", "unknown")
        fmt = parsed_doc.get("format", "text")

        # Strategy 1: 关键词库精确匹配
        s1_entities = self._strategy_keyword_match(raw_text, source)
        self._log("Strategy1_KeywordMatch", len(s1_entities), len(s1_entities))

        # Strategy 2: 正则模式匹配
        s2_entities = self._strategy_regex_patterns(raw_text, source)
        self._log("Strategy2_RegexPatterns", len(s2_entities), len(s2_entities))

        # Strategy 3: 基于词频的候选名词（中文语境）
        s3_entities = self._strategy_frequency_candidates(raw_text, source)
        self._log("Strategy3_FrequencyCandidates", len(s3_entities), len(s3_entities))

        # Strategy 4: 代码感知（仅 Python 文件）
        s4_entities = []
        if fmt == "python":
            s4_entities = self._strategy_code_aware(parsed_doc, source)
            self._log("Strategy4_CodeAware", len(s4_entities), len(s4_entities))

        # 合并去重（高置信度优先）
        all_candidates = s1_entities + s2_entities + s3_entities + s4_entities
        for ent in all_candidates:
            key = (ent["name"].lower(), ent["type"])
            if key not in seen:
                seen.add(key)
                entities.append(ent)

        return {
            "entities": entities,
            "extraction_trace": self.extraction_trace,
            "source": source,
            "entity_count": len(entities),
        }

    # ── Strategy 1: 关键词精确匹配 ──────────────────────────────────

    def _strategy_keyword_match(self, text: str, source: str) -> List[Dict[str, Any]]:
        entities = []
        for ent_type, keywords in self.keywords.items():
            for kw in keywords:
                # 大小写不敏感搜索
                pattern = re.compile(re.escape(kw), re.IGNORECASE)
                for m in pattern.finditer(text):
                    # 提取上下文（前后30字符）
                    start = max(0, m.start() - 30)
                    end = min(len(text), m.end() + 30)
                    context = text[start:end].strip()
                    entities.append({
                        "name": kw,
                        "type": ent_type,
                        "source": source,
                        "confidence": 0.95,
                        "context": context,
                        "extraction_method": "keyword_match",
                    })
        return entities

    # ── Strategy 2: 正则模式匹配 ─────────────────────────────────────

    def _strategy_regex_patterns(self, text: str, source: str) -> List[Dict[str, Any]]:
        entities = []

        patterns = [
            # 语义化版本号
            (r"\b(\d+\.\d+(?:\.\d+)*(?:-[a-zA-Z0-9.]+)?)\b", "technology", 0.7),
            # URL
            (r"https?://[^\s<>\"')\]]+", "document", 0.6),
            # 文件路径
            (r"(?:[A-Z]:\\|/home/|/usr/|~/)[^\s<>\"')\]]+", "document", 0.5),
            # Python 类名引用 (驼峰)
            (r"\b([A-Z][a-z]+(?:[A-Z][a-z]+)+)\b", "concept", 0.6),
            # 蛇形模块名 (import后的)
            (r"(?:import|from)\s+([a-z_][a-z0-9_]*(?:\.[a-z_][a-z0-9_]*)*)", "technology", 0.8),
        ]

        for pattern, ent_type, confidence in patterns:
            for m in re.finditer(pattern, text):
                name = m.group(1)
                # 过滤太短或太长的
                if len(name) < 3 or len(name) > 100:
                    continue
                start = max(0, m.start() - 20)
                end = min(len(text), m.end() + 20)
                context = text[start:end].strip()
                entities.append({
                    "name": name,
                    "type": ent_type,
                    "source": source,
                    "confidence": confidence,
                    "context": context,
                    "extraction_method": "regex_pattern",
                })

        return entities

    # ── Strategy 3: 词频候选名词 ────────────────────────────────────

    def _strategy_frequency_candidates(self, text: str, source: str) -> List[Dict[str, Any]]:
        """基于出现频率识别潜在专有名词"""
        entities = []

        # 中文：提取连续2-6个汉字组成的短语
        chinese_phrases = re.findall(r'([\u4e00-\u9fff]{2,6})', text)
        freq: Dict[str, int] = {}
        for p in chinese_phrases:
            freq[p] = freq.get(p, 0) + 1

        # 高频词（出现2次以上）
        for phrase, count in freq.items():
            if count >= 2:
                # 排除常见虚词
                stopwords = {
                    "但是", "因为", "所以", "如果", "那么", "可以", "已经",
                    "通过", "进行", "实现", "使用", "包括", "支持", "以及",
                    "这个", "那个", "一个", "我们", "他们", "什么", "怎么",
                    "没有", "不是", "如何", "对于", "关于", "当前", "其中",
                }
                if phrase not in stopwords:
                    entities.append({
                        "name": phrase,
                        "type": self._guess_chinese_type(phrase),
                        "source": source,
                        "confidence": min(0.5 + count * 0.1, 0.85),
                        "context": f"出现{count}次",
                        "extraction_method": "frequency_candidate",
                    })

        # 英文：提取连续的驼峰/下划线标识符
        identifiers = re.findall(r'\b([a-z][a-z0-9]*(?:_[a-z0-9]+)+)\b', text)
        id_freq: Dict[str, int] = {}
        for ident in identifiers:
            if len(ident) >= 5:
                id_freq[ident] = id_freq.get(ident, 0) + 1

        for ident, count in id_freq.items():
            if count >= 2:
                entities.append({
                    "name": ident,
                    "type": "technology",
                    "source": source,
                    "confidence": 0.65,
                    "context": f"出现{count}次",
                    "extraction_method": "frequency_candidate",
                })

        return entities

    def _guess_chinese_type(self, phrase: str) -> str:
        """根据中文短语内容推断实体类型"""
        tech_hints = ["学习", "模型", "算法", "训练", "推理", "嵌入", "向量",
                       "网络", "生成", "编码", "解码", "注意力", "激活"]
        project_hints = ["项目", "系统", "平台", "工具", "框架", "引擎",
                          "编辑器", "管理器", "处理器"]
        concept_hints = ["原理", "理论", "方法", "策略", "机制", "模式",
                          "架构", "流程", "范式", "思想"]

        for hint in tech_hints:
            if hint in phrase:
                return "technology"
        for hint in project_hints:
            if hint in phrase:
                return "project"
        for hint in concept_hints:
            if hint in phrase:
                return "concept"
        return "concept"

    # ── Strategy 4: 代码感知抽取 ────────────────────────────────────

    def _strategy_code_aware(self, parsed_doc: Dict[str, Any],
                              source: str) -> List[Dict[str, Any]]:
        """从 Python 代码中提取有意义的实体"""
        entities = []
        imports = parsed_doc.get("imports", "")

        for line in imports.split("\n"):
            line = line.strip()
            if not line:
                continue
            # 提取第三方库名
            for kw in self.keywords.get("technology", []):
                if kw.lower() in line.lower():
                    entities.append({
                        "name": kw,
                        "type": "technology",
                        "source": source,
                        "confidence": 0.9,
                        "context": line,
                        "extraction_method": "code_import",
                    })

        # 从 sections 提取类名
        for section in parsed_doc.get("sections", []):
            if section["heading"].startswith("Class:"):
                class_name = section["heading"].replace("Class:", "").strip()
                entities.append({
                    "name": class_name,
                    "type": "concept",
                    "source": source,
                    "confidence": 0.85,
                    "context": section["heading"],
                    "extraction_method": "code_class",
                })
            elif section["heading"].startswith("Function:"):
                func_name = section["heading"].replace("Function:", "").strip()
                entities.append({
                    "name": func_name,
                    "type": "concept",
                    "source": source,
                    "confidence": 0.75,
                    "context": section["heading"],
                    "extraction_method": "code_function",
                })

        return entities

    # ── 工具 ──────────────────────────────────────────────────────────

    def _log(self, step: str, inp: Any, out: Any):
        self.extraction_trace.append({"step": step, "input": inp, "output": out})
