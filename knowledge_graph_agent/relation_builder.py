#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RelationBuilder — 实体关系推断 Agent

从文档上下文中推断实体间的关系，采用多层级推断策略:

  Level 1: 共现关系 (co-occurrence) — 同一段落/section 中出现的实体
  Level 2: 模式匹配 (pattern matching) — 识别常见关系表述模板
  Level 3: 结构推断 (structural inference) — 基于文档结构推断层次关系
  Level 4: 跨文档合并 (cross-document merge) — 多文档间的实体对齐和关系合并

输出:
{
    "relations": [
        {"source": str, "target": str, "type": str, "confidence": float, "evidence": str}
    ],
    "inference_trace": [...]
}
"""

import re
from typing import Dict, Any, List, Optional
from config import RELATION_TYPES


class RelationBuilder:
    """实体关系推断 Agent"""

    # 关系模式模板（中文）
    RELATION_PATTERNS_CN = [
        (r"([\w\s]+?)使用([\w\s]+?)(?:来|实现|完成|构建|开发)", "uses"),
        (r"([\w\s]+?)依赖于([\w\s]+?)", "depends_on"),
        (r"([\w\s]+?)属于([\w\s]+?)", "part_of"),
        (r"([\w\s]+?)包含([\w\s]+?)", "contains"),
        (r"([\w\s]+?)创建了([\w\s]+?)", "created_by"),
        (r"([\w\s]+?)参与([\w\s]+?)", "works_on"),
        (r"([\w\s]+?)位于([\w\s]+?)", "located_in"),
        (r"([\w\s]+?)引用([\w\s]+?)", "references"),
        (r"([\w\s]+?)扩展([\w\s]+?)", "extends"),
        (r"([\w\s]+?)基于([\w\s]+?)", "depends_on"),
        (r"([\w\s]+?)是对([\w\s]+?)的", "extends"),
    ]

    # 关系模式模板（英文）
    RELATION_PATTERNS_EN = [
        (r"(\w[\w\s]*?)\s+(?:uses?|using?|utilize[sd]?)\s+(\w[\w\s]*?)", "uses"),
        (r"(\w[\w\s]*?)\s+(?:depends?\s+on|rely|relies)\s+(?:on\s+)?(\w[\w\s]*?)", "depends_on"),
        (r"(\w[\w\s]*?)\s+(?:is\s+part\s+of|belongs?\s+to)\s+(\w[\w\s]*?)", "part_of"),
        (r"(\w[\w\s]*?)\s+(?:contains?|includes?)\s+(\w[\w\s]*?)", "contains"),
        (r"(\w[\w\s]*?)\s+(?:created|built|developed)\s+(?:by\s+)?(\w[\w\s]*?)", "created_by"),
        (r"(\w[\w\s]*?)\s+(?:extends?|inherit[sd]?\s+from)\s+(\w[\w\s]*?)", "extends"),
        (r"(\w[\w\s]*?)\s+(?:refer[sd]?\s+to|cite[sd]?)\s+(\w[\w\s]*?)", "references"),
    ]

    def __init__(self, co_occurrence_window: int = 150):
        self.co_occurrence_window = co_occurrence_window
        self.inference_trace: List[Dict[str, Any]] = []

    # ── 主入口 ────────────────────────────────────────────────────────

    def build_relations(
        self,
        entities: List[Dict[str, Any]],
        parsed_doc: Dict[str, Any],
    ) -> Dict[str, Any]:
        """从实体列表和文档中推断关系"""
        self.inference_trace = []
        seen_relations: set = set()
        relations: List[Dict[str, Any]] = []

        raw_text = parsed_doc.get("raw_text", "")
        sections = parsed_doc.get("sections", [])

        # ── Level 1: 共现关系 ────────────────────────────────────────
        l1 = self._level1_co_occurrence(entities, raw_text)
        for r in l1:
            key = self._relation_key(r)
            if key not in seen_relations:
                seen_relations.add(key)
                relations.append(r)
        self._log("Level1_CoOccurrence", len(entities), len(l1))

        # ── Level 2: 模式匹配 ────────────────────────────────────────
        l2 = self._level2_pattern_matching(raw_text, entities)
        for r in l2:
            key = self._relation_key(r)
            if key not in seen_relations:
                seen_relations.add(key)
                relations.append(r)
        self._log("Level2_PatternMatching", "templates", len(l2))

        # ── Level 3: 结构推断 ────────────────────────────────────────
        l3 = self._level3_structural_inference(entities, sections)
        for r in l3:
            key = self._relation_key(r)
            if key not in seen_relations:
                seen_relations.add(key)
                relations.append(r)
        self._log("Level3_StructuralInference", len(sections), len(l3))

        return {
            "relations": relations,
            "inference_trace": self.inference_trace,
            "relation_count": len(relations),
        }

    # ── Level 1: 共现关系 ────────────────────────────────────────────

    def _level1_co_occurrence(
        self, entities: List[Dict[str, Any]], text: str
    ) -> List[Dict[str, Any]]:
        """同一段落/窗口中出现的实体建立关联"""
        relations = []
        # 滑动窗口
        window_size = self.co_occurrence_window

        for i in range(0, len(text), window_size // 2):
            window = text[i:i + window_size]
            window_entities = []

            for ent in entities:
                name_lower = ent["name"].lower()
                if name_lower in window.lower():
                    window_entities.append(ent)

            # 同窗口内的实体两两建立关系
            for a in window_entities:
                for b in window_entities:
                    if a["name"] == b["name"]:
                        continue
                    # 确定关系类型（基于实体类型）
                    rel_type = self._infer_relation_type(a, b)
                    if rel_type:
                        relations.append({
                            "source": a["name"],
                            "target": b["name"],
                            "type": rel_type,
                            "confidence": 0.4,
                            "evidence": f"共现于: {window[:80]}...",
                            "inference_method": "co_occurrence",
                        })
        return relations

    # ── Level 2: 模式匹配 ────────────────────────────────────────────

    def _level2_pattern_matching(
        self, text: str, entities: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """从文本中匹配关系表述模式"""
        relations = []
        entity_names = {e["name"].lower(): e["name"] for e in entities}

        all_patterns = self.RELATION_PATTERNS_CN + self.RELATION_PATTERNS_EN

        for pattern, rel_type in all_patterns:
            for match in re.finditer(pattern, text):
                src_text = match.group(1).strip()
                tgt_text = match.group(2).strip()

                # 匹配到已知实体才建立关系
                src_name = None
                tgt_name = None

                for ent_lower, ent_name in entity_names.items():
                    if ent_lower in src_text.lower():
                        src_name = ent_name
                    if ent_lower in tgt_text.lower():
                        tgt_name = ent_name

                if src_name and tgt_name and src_name != tgt_name:
                    relations.append({
                        "source": src_name,
                        "target": tgt_name,
                        "type": rel_type,
                        "confidence": 0.85,
                        "evidence": match.group(0).strip(),
                        "inference_method": "pattern_matching",
                    })
        return relations

    # ── Level 3: 结构推断 ────────────────────────────────────────────

    def _level3_structural_inference(
        self, entities: List[Dict[str, Any]],
        sections: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """基于文档结构推断实体间层次关系"""
        relations = []
        entity_names = {e["name"].lower() for e in entities}

        # 每个 section 中提取的实体视为同一个"主题组"
        for section in sections:
            content = section.get("content", "")
            heading = section.get("heading", "")
            section_entities = []

            for ent in entities:
                if ent["name"].lower() in content.lower():
                    section_entities.append(ent)

            # 如果标题中包含实体名，该实体与其他实体建立 contains 关系
            for ent_lower in entity_names:
                if ent_lower in heading.lower():
                    # 找到原始名称
                    real_name = next(
                        (e["name"] for e in entities if e["name"].lower() == ent_lower),
                        heading,
                    )
                    for other in section_entities:
                        if other["name"].lower() != ent_lower:
                            relations.append({
                                "source": real_name,
                                "target": other["name"],
                                "type": "contains",
                                "confidence": 0.7,
                                "evidence": f"section: {heading}",
                                "inference_method": "structural_inference",
                            })
                    break

        return relations

    # ── 跨文档关系合并 ────────────────────────────────────────────────

    def merge_relations(
        self,
        all_relations: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """合并多个文档的关系，去重并提升置信度"""
        merged: Dict[str, Dict[str, Any]] = {}

        for rel in all_relations:
            key = self._relation_key(rel)
            if key in merged:
                # 提升置信度
                existing = merged[key]
                existing["confidence"] = min(
                    existing["confidence"] + 0.1, 1.0
                )
                existing["evidence"] += f" | {rel.get('evidence', '')}"
            else:
                merged[key] = rel.copy()

        # 按置信度排序
        result = sorted(merged.values(), key=lambda r: r["confidence"], reverse=True)
        return result

    # ── 工具 ──────────────────────────────────────────────────────────

    def _infer_relation_type(self, a: Dict, b: Dict) -> Optional[str]:
        """根据实体类型对推断关系类型"""
        type_rules = {
            ("person", "project"): "works_on",
            ("person", "organization"): "part_of",
            ("project", "technology"): "uses",
            ("project", "concept"): "uses",
            ("technology", "technology"): "related_to",
            ("concept", "concept"): "related_to",
            ("organization", "technology"): "uses",
            ("event", "person"): "related_to",
            ("event", "project"): "related_to",
            ("document", "concept"): "references",
        }
        key = (a["type"], b["type"])
        reverse_key = (b["type"], a["type"])
        return type_rules.get(key) or type_rules.get(reverse_key)

    def _relation_key(self, rel: Dict[str, Any]) -> str:
        src = rel["source"].lower()
        tgt = rel["target"].lower()
        rtype = rel["type"]
        return f"{min(src, tgt)}|{max(src, tgt)}|{rtype}"

    def _log(self, step: str, inp: Any, out: Any):
        self.inference_trace.append({"step": step, "input": inp, "output": out})
