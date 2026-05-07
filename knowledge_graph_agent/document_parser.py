#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DocumentParser — 多格式文档解析 Agent

支持格式:
  - Markdown (.md)
  - Python 源码 (.py)
  - 纯文本 (.txt)
  - JSON (.json)

输出统一结构:
{
    "source": "文件路径",
    "format": "markdown|python|text|json",
    "sections": [{"heading": str, "content": str, "level": int}],
    "metadata": {...},
    "raw_text": str,
}
"""

import os
import re
import json
from typing import Dict, Any, List, Optional


class DocumentParser:
    """多格式文档解析 Agent"""

    def parse(self, file_path: str) -> Dict[str, Any]:
        """根据扩展名自动选择解析器"""
        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"文件不存在: {file_path}")

        ext = os.path.splitext(file_path)[1].lower()
        parsers = {
            ".md": self._parse_markdown,
            ".py": self._parse_python,
            ".txt": self._parse_text,
            ".json": self._parse_json_file,
        }

        parser = parsers.get(ext, self._parse_text)
        result = parser(file_path)
        result["source"] = file_path
        result["format"] = {
            ".md": "markdown", ".py": "python",
            ".txt": "text", ".json": "json",
        }.get(ext, "text")

        # 统计信息
        result["metadata"] = {
            "char_count": len(result["raw_text"]),
            "line_count": result["raw_text"].count("\n") + 1,
            "section_count": len(result["sections"]),
            "word_count": len(result["raw_text"].split()),
        }
        return result

    # ── Markdown 解析 ───────────────────────────────────────────────

    def _parse_markdown(self, file_path: str) -> Dict[str, Any]:
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()

        sections: List[Dict[str, Any]] = []
        current_heading = "Introduction"
        current_level = 1
        current_content: List[str] = []
        lines = text.split("\n")

        for line in lines:
            heading_match = re.match(r"^(#{1,6})\s+(.+)", line)
            if heading_match:
                # 保存上一节
                if current_content or sections:
                    sections.append({
                        "heading": current_heading,
                        "content": "\n".join(current_content).strip(),
                        "level": current_level,
                    })
                current_heading = heading_match.group(2).strip()
                current_level = len(heading_match.group(1))
                current_content = []
            else:
                # 去掉 markdown 格式符号
                clean = re.sub(r"[*_`#>\[\]\(\)!|]", "", line)
                current_content.append(clean)

        # 最后一节
        if current_content or not sections:
            sections.append({
                "heading": current_heading,
                "content": "\n".join(current_content).strip(),
                "level": current_level,
            })

        # 提取 code blocks
        code_blocks = re.findall(r"```[\w]*\n(.*?)```", text, re.DOTALL)
        clean_text = re.sub(r"```[\w]*\n.*?```", "", text, flags=re.DOTALL)
        clean_text = re.sub(r"[*_`#>\[\]\(\)!|]", "", clean_text)

        return {
            "sections": sections,
            "code_blocks": code_blocks,
            "raw_text": clean_text.strip(),
        }

    # ── Python 源码解析 ─────────────────────────────────────────────

    def _parse_python(self, file_path: str) -> Dict[str, Any]:
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()

        sections: List[Dict[str, Any]] = []

        # 提取 docstring（模块级）
        module_doc = re.findall(r'^"""(.*?)"""', text, re.DOTALL | re.MULTILINE)
        if module_doc:
            sections.append({
                "heading": "Module Docstring",
                "content": module_doc[0].strip(),
                "level": 1,
            })

        # 提取 class 定义 + docstring
        docstr_pat = r'"""(.*?)"""'
        classes = re.finditer(
            r'class\s+(\w+)(?:\(.*?\))?:\s*\n\s*(?:' + docstr_pat + r')?',
            text, re.DOTALL
        )
        for m in classes:
            name = m.group(1)
            doc = m.group(2) or ""
            sections.append({
                "heading": f"Class: {name}",
                "content": doc.strip(),
                "level": 2,
            })

        # 提取 function 定义 + docstring
        funcs = re.finditer(
            r'(?:async\s+)?def\s+(\w+)\s*\([^)]*\).*?:\s*\n\s*(?:' + docstr_pat + r')?',
            text, re.DOTALL
        )
        for m in funcs:
            name = m.group(1)
            doc = m.group(2) or ""
            if doc.strip():
                sections.append({
                    "heading": f"Function: {name}",
                    "content": doc.strip(),
                    "level": 3,
                })

        # 提取 import 语句
        imports = re.findall(r"^(?:from\s+([\w.]+)\s+)?import\s+(.+)", text, re.MULTILINE)
        import_text = "\n".join(
            f"from {m[0]} import {m[1]}" if m[0] else f"import {m[1]}"
            for m in imports if not any(m[1].startswith(x) for x in ["os.", "sys.", "json.", "re."])
        )
        if import_text:
            sections.insert(0, {
                "heading": "Imports",
                "content": import_text,
                "level": 2,
            })

        # 提取注释
        comments = re.findall(r"#\s*(.+)", text)
        comment_text = "\n".join(comments)

        clean_text = re.sub(r'""".*?"""', "", text, flags=re.DOTALL)
        clean_text = re.sub(r"#[^\n]*", "", clean_text)
        clean_text = re.sub(r'"""|\'\'\'', "", clean_text)

        return {
            "sections": sections,
            "imports": import_text,
            "comments": comment_text,
            "raw_text": clean_text.strip(),
        }

    # ── 纯文本解析 ──────────────────────────────────────────────────

    def _parse_text(self, file_path: str) -> Dict[str, Any]:
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()

        lines = text.split("\n")
        sections: List[Dict[str, Any]] = []
        current_heading = "Content"
        current_content: List[str] = []

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            # 简单标题检测：短行且无句号结尾
            if len(stripped) < 50 and not stripped.endswith(("。", ".", "：", ":", "，", ",")) and not stripped.startswith(("  ", "\t")):
                if current_content:
                    sections.append({
                        "heading": current_heading,
                        "content": "\n".join(current_content).strip(),
                        "level": 1,
                    })
                current_heading = stripped
                current_content = []
            else:
                current_content.append(stripped)

        if current_content:
            sections.append({
                "heading": current_heading,
                "content": "\n".join(current_content).strip(),
                "level": 1,
            })

        return {
            "sections": sections,
            "raw_text": text.strip(),
        }

    # ── JSON 解析 ───────────────────────────────────────────────────

    def _parse_json_file(self, file_path: str) -> Dict[str, Any]:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 递归提取所有文本值
        texts: List[str] = []

        def extract(obj, prefix=""):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    extract(v, f"{prefix}.{k}")
            elif isinstance(obj, list):
                for i, v in enumerate(obj):
                    extract(v, f"{prefix}[{i}]")
            elif isinstance(obj, str) and len(obj) > 5:
                texts.append(f"{prefix}: {obj}")

        extract(data)

        sections = []
        current: List[str] = []
        for t in texts:
            current.append(t)
            if len(current) >= 5:
                sections.append({
                    "heading": f"Section {len(sections)+1}",
                    "content": "\n".join(current),
                    "level": 1,
                })
                current = []
        if current:
            sections.append({
                "heading": f"Section {len(sections)+1}",
                "content": "\n".join(current),
                "level": 1,
            })

        raw = json.dumps(data, ensure_ascii=False, indent=2)
        return {
            "sections": sections,
            "data": data,
            "raw_text": raw,
        }

    # ── 批量解析 ────────────────────────────────────────────────────

    def parse_directory(self, dir_path: str,
                        extensions: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """递归解析目录下所有支持的文件"""
        if extensions is None:
            extensions = [".md", ".py", ".txt", ".json"]

        results = []
        for root, dirs, files in os.walk(dir_path):
            dirs[:] = [d for d in dirs if not d.startswith((".", "__"))]
            for fname in sorted(files):
                ext = os.path.splitext(fname)[1].lower()
                if ext in extensions:
                    fpath = os.path.join(root, fname)
                    try:
                        result = self.parse(fpath)
                        results.append(result)
                    except Exception as e:
                        print(f"  解析失败 {fpath}: {e}")
        return results
