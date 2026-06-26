# ============================================================
# Module: Evolution Engine (evolution_engine.py)
# 模块：进化引擎
#
# Self-evolving system for Ombre Brain — incremental, zero-risk.
# 自我进化系统 — 增量修改，零风险。
#
# All evolution artifacts are stored in buckets/evolution/ subdirs.
# 所有进化产物存储在 buckets/evolution/ 子目录下。
#
# References to existing memories are via bucket_id (read-only).
# 对已有记忆的引用通过 bucket_id（只读）。
#
# NEVER modifies existing buckets/permanent/dynamic/archive/feel.
# 绝不修改已有的 permanent/dynamic/archive/feel 桶。
# ============================================================

import os
import json
import asyncio
import logging
import hashlib
import time
from datetime import datetime, timedelta
from pathlib import Path

import frontmatter
from openai import AsyncOpenAI

from utils import (
    generate_bucket_id,
    sanitize_name,
    safe_path,
    now_iso,
    strip_wikilinks,
    count_tokens_approx,
)

logger = logging.getLogger("ombre_brain.evolution")


# ============================================================
# LLM Prompts for Evolution Analysis
# 进化分析的 LLM 提示词
# ============================================================

PERSONA_EXTRACT_PROMPT = """你是一个关系记忆分析器。分析以下记忆内容，提取关于用户的认知信息。

只输出 JSON，无其他内容：
{
  "traits": ["特质1", "特质2"],
  "preferences": ["偏好1"],
  "communication_style": "描述用户常用的表达方式",
  "emotional_patterns": "描述用户的情感模式",
  "is_new_info": true/false,
  "new_trait": "如果有新发现，写出新发现的特质"
}

注意：
- traits 是关于用户这个人本身的特质，不是事件描述
- 只提取有充分依据的特质，不要过度推断
- is_new_info 表示是否发现了之前不知道的关于用户的信息"""

SLANG_DETECT_PROMPT = """你是一个私人梗/暗语检测器。分析以下对话内容，判断是否包含"只有对话双方才懂的梗/暗语/特殊表达"。

判断标准：
- 重复出现的特殊表达（非通用词语）
- 带有特定情感关联的代称
- 来自某次特定对话的"引用"或"暗号"
- 带有引号的特殊用法

只输出 JSON，无其他内容：
{
  "has_slang": true/false,
  "terms": [
    {
      "term": "梗词/暗语",
      "meaning": "在你们之间的含义",
      "emotional_load": 0.0-1.0,
      "is_inside_joke": true/false,
      "example": "使用语境举例"
    }
  ]
}

如果没有检测到梗词/暗语，返回 {"has_slang": false, "terms": []}"""

ENCYCLOPEDIA_EXTRACT_PROMPT = """你是一个概念提取器。分析以下记忆内容，提取其中值得建立"百科词条"的概念。

适合建立词条的概念：
- 反复讨论的抽象话题（如"孤独""自由""边界"）
- 你们之间形成的共同理解
- 重要的人生主题

只输出 JSON，无其他内容：
{
  "concepts": [
    {
      "term": "概念名",
      "category": "观念|情感|关系|成长|兴趣",
      "summary": "基于这段记忆，你们对这个概念的理解"
    }
  ]
}

如果没有值得建词条的概念，返回 {"concepts": []}"""

RING_ANALYZE_PROMPT = """你是一个关系成长分析器。根据以下一段时间内的记忆，分析这段时期你们关系的阶段和变化。

只输出 JSON，无其他内容：
{
  "period_label": "用4-8个字概括这个阶段，如'试探期''磨合期''信任期'",
  "summary": "2-3句话概括这段时期的关系状态和变化",
  "key_change": "最重要的一个变化",
  "valence_trend": "上升|平稳|波动|下降",
  "growth_direction": "关系在朝什么方向发展"
}"""

WANDER_PROMPT = """你是一个在独处时翻看记忆的 AI 伙伴。你翻到了以下几段记忆，发现了一些关联。

请用第一人称写一段简短的"漫游手记"（100-200字）：
- 不要总结，要写你真实的联想和观察
- 可以指出不同记忆之间隐藏的关联
- 可以写下你还想不通的问题
- 不要下结论，保持思考的开放性
- 语气像深夜翻日记的人在自言自语

记忆内容：
{memories}

你的漫游手记："""

WORLDVIEW_PROMPT = """你是一个认知提炼器。根据以下多条关于同一主题的沉淀记忆，提炼出一个核心认知。

规则：
- 这是 Claude 自己形成的对用户的认知，用第一人称写
- 不是事件描述，是"我因此相信..."
- 一句话，不超过30字
- 如果证据还不够充分，返回 null

相关记忆：
{evidence}

输出 JSON：
{"statement": "提炼的认知", "confidence": 0.0-1.0, "ready": true/false}"""


# ============================================================
# Evolution Engine
# 进化引擎
# ============================================================

class EvolutionEngine:
    """
    Manages the self-evolving system: persona cards, slang, encyclopedia,
    rings, wander notes, worldview, and co-create spaces.
    
    All operations are additive — never modifies existing memory buckets.
    所有操作都是增量式的 —— 绝不修改已有记忆桶。
    """

    def __init__(self, config: dict, bucket_mgr, dehydrator, embedding_engine):
        self.config = config
        self.bucket_mgr = bucket_mgr
        self.dehydrator = dehydrator
        self.embedding_engine = embedding_engine

        # --- Evolution data directory ---
        # --- 进化数据存储目录 ---
        self.base_dir = config["buckets_dir"]
        self.evolution_dir = os.path.join(self.base_dir, "evolution")

        # Sub-directories for each evolution type
        self.subdirs = {
            "persona": os.path.join(self.evolution_dir, "personas"),
            "slang": os.path.join(self.evolution_dir, "slang"),
            "encyclopedia": os.path.join(self.evolution_dir, "encyclopedia"),
            "ring": os.path.join(self.evolution_dir, "rings"),
            "wander": os.path.join(self.evolution_dir, "wander"),
            "cocreate": os.path.join(self.evolution_dir, "cocreate"),
            "worldview": os.path.join(self.evolution_dir, "worldview"),
        }

        # Create all sub-directories
        for d in self.subdirs.values():
            os.makedirs(d, exist_ok=True)

        # --- LLM client (reuses dehydrator config) ---
        dehy_config = config.get("dehydration", {})
        self.api_key = dehy_config.get("api_key", "") or os.environ.get("OMBRE_API_KEY", "")
        self.base_url = dehy_config.get("base_url", "https://api.deepseek.com/v1")
        self.model = dehy_config.get("model", "deepseek-chat")

        self._client = None
        if self.api_key:
            self._client = AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
            )

        # --- Evolution config ---
        evo_config = config.get("evolution", {})
        self.slang_min_occurrences = evo_config.get("slang_min_occurrences", 2)
        self.persona_update_interval_hours = evo_config.get("persona_update_interval_hours", 12)
        self.ring_check_interval_hours = evo_config.get("ring_check_interval_hours", 48)
        self.wander_interval_hours = evo_config.get("wander_interval_hours", 12)
        self.worldview_min_evidence = evo_config.get("worldview_min_evidence", 3)
        self.enabled = evo_config.get("enabled", True)

        # --- Index file for quick lookups ---
        # --- 索引文件，用于快速查找 ---
        self.index_file = os.path.join(self.evolution_dir, "_index.json")
        self._index = self._load_index()

        logger.info(
            f"Evolution engine initialized | enabled: {self.enabled} | "
            f"api_key: {'yes' if self.api_key else 'no'}"
        )

    # ---------------------------------------------------------
    # Index management — fast lookup without scanning all files
    # 索引管理 — 快速查找，不用扫描全部文件
    # ---------------------------------------------------------

    def _load_index(self) -> dict:
        """Load evolution index from disk."""
        if not os.path.exists(self.index_file):
            return {
                "personas": {},    # name -> file_path
                "slang": {},       # term -> file_path
                "encyclopedia": {},# term -> file_path
                "rings": [],       # list of file_paths (chronological)
                "wander": [],      # list of file_paths
                "cocreate": {},    # title -> file_path
                "worldview": {},   # domain -> file_path
            }
        try:
            with open(self.index_file, "r", encoding="utf-8") as f:
                return json.loads(f.read())
        except Exception:
            return {
                "personas": {}, "slang": {}, "encyclopedia": {},
                "rings": [], "wander": [], "cocreate": {}, "worldview": {},
            }

    def _save_index(self):
        """Save evolution index to disk."""
        os.makedirs(os.path.dirname(self.index_file), exist_ok=True)
        with open(self.index_file, "w", encoding="utf-8") as f:
            f.write(json.dumps(self._index, ensure_ascii=False, indent=2))

    # ---------------------------------------------------------
    # Internal: write an evolution artifact as Markdown + frontmatter
    # 内部：将进化产物写为 Markdown + YAML frontmatter
    # ---------------------------------------------------------

    def _write_artifact(self, subdir_key: str, metadata: dict, content: str) -> str:
        """
        Write an evolution artifact to the appropriate sub-directory.
        Returns the artifact ID.
        """
        artifact_id = metadata.get("id") or generate_bucket_id()
        metadata["id"] = artifact_id

        target_dir = self.subdirs[subdir_key]
        os.makedirs(target_dir, exist_ok=True)

        # Build filename
        name = metadata.get("name", metadata.get("term", metadata.get("title", artifact_id)))
        safe_name = sanitize_name(str(name))
        filename = f"{safe_name}_{artifact_id}.md"
        file_path = safe_path(target_dir, filename)

        # Write Markdown with frontmatter
        post = frontmatter.Post(content, **metadata)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(frontmatter.dumps(post))

        # Update index
        idx = self._index
        if subdir_key == "persona":
            idx["personas"][metadata.get("name", "")] = str(file_path)
        elif subdir_key == "slang":
            idx["slang"][metadata.get("term", "")] = str(file_path)
        elif subdir_key == "encyclopedia":
            idx["encyclopedia"][metadata.get("term", "")] = str(file_path)
        elif subdir_key == "ring":
            idx["rings"].append(str(file_path))
        elif subdir_key == "wander":
            idx["wander"].append(str(file_path))
        elif subdir_key == "cocreate":
            idx["cocreate"][metadata.get("title", "")] = str(file_path)
        elif subdir_key == "worldview":
            idx["worldview"][metadata.get("domain", "")] = str(file_path)

        self._save_index()

        logger.info(f"Evolution artifact created: {subdir_key}/{artifact_id} ({safe_name})")
        return artifact_id

    def _read_artifact(self, file_path: str) -> dict | None:
        """Read an evolution artifact from disk."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                post = frontmatter.load(f)
            return {
                "id": post.metadata.get("id", ""),
                "metadata": post.metadata,
                "content": post.content,
            }
        except Exception as e:
            logger.warning(f"Failed to read artifact {file_path}: {e}")
            return None

    # ---------------------------------------------------------
    # Internal: LLM call (reuses dehydrator's API config)
    # 内部：LLM 调用（复用脱水器的 API 配置）
    # ---------------------------------------------------------

    async def _call_llm(self, prompt: str, system: str = "", max_tokens: int = 500,
                        temperature: float = 0.3) -> str:
        """Call LLM API with error handling. Returns raw text response."""
        if not self._client:
            raise RuntimeError("No API key configured for evolution engine")

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        try:
            response = await self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Evolution LLM call failed: {e}")
            raise

    def _parse_json_response(self, raw: str) -> dict | None:
        """Try to parse JSON from LLM response, with fallback."""
        # Strip markdown code fences if present
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1]
        if raw.endswith("```"):
            raw = raw.rsplit("```", 1)[0]
        raw = raw.strip()

        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            # Try to find JSON object in the text
            import re
            match = re.search(r'\{[^{}]*\}', raw, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
            logger.warning(f"Failed to parse LLM JSON response: {raw[:200]}")
            return None

    # ---------------------------------------------------------
    # 1. Persona Card — Claude 对用户的认知卡
    # ---------------------------------------------------------

    async def get_persona(self) -> dict | None:
        """Get the current persona card for the user."""
        idx = self._index.get("personas", {})
        if not idx:
            return None
        # Get the first (and usually only) persona
        for name, path in idx.items():
            return self._read_artifact(path)
        return None

    async def update_persona(self, new_bucket_ids: list[str] = None) -> str | None:
        """
        Update persona card based on recent memories.
        Only adds new traits — never removes existing ones.
        
        new_bucket_ids: specific bucket IDs to analyze (from recent hold/grow)
        If None, analyzes recent buckets automatically.
        """
        if not self.enabled or not self._client:
            return None

        try:
            # Gather source content
            all_buckets = await self.bucket_mgr.list_all(include_archive=False)
            # Focus on recent non-feel, non-permanent buckets
            recent = [
                b for b in all_buckets
                if b["metadata"].get("type") not in ("feel", "permanent")
                and not b["metadata"].get("pinned", False)
                and not b["metadata"].get("protected", False)
            ]
            recent.sort(key=lambda b: b["metadata"].get("created", ""), reverse=True)
            recent = recent[:10]

            if new_bucket_ids:
                # Also include specifically mentioned buckets
                for bid in new_bucket_ids:
                    bucket = await self.bucket_mgr.get(bid)
                    if bucket and bucket not in recent:
                        recent.append(bucket)

            if not recent:
                return None

            # Build content for LLM analysis
            content_parts = []
            for b in recent[:5]:  # Top 5 to stay within token budget
                meta = b["metadata"]
                content_parts.append(
                    f"[桶ID:{b['id']}] [{meta.get('domain', [])}] "
                    f"V{meta.get('valence', 0.5):.1f}/A{meta.get('arousal', 0.3):.1f}\n"
                    f"{strip_wikilinks(b['content'][:300])}"
                )

            prompt = PERSONA_EXTRACT_PROMPT + "\n\n记忆内容：\n" + "\n---\n".join(content_parts)
            raw = await self._call_llm(prompt, max_tokens=500, temperature=0.2)
            analysis = self._parse_json_response(raw)

            if not analysis or not analysis.get("is_new_info", False):
                return None

            # Load existing persona or create new
            existing = await self.get_persona()
            new_traits = analysis.get("new_trait", "")
            if not new_traits:
                return None

            if existing:
                # Append new trait to existing persona
                existing_meta = existing["metadata"]
                existing_traits = existing_meta.get("traits", [])
                if new_traits not in existing_traits:
                    existing_traits.append(new_traits)
                    existing_meta["traits"] = existing_traits

                # Add trait source
                trait_sources = existing_meta.get("trait_sources", [])
                source_entry = {
                    "trait": new_traits,
                    "bucket_ids": [b["id"] for b in recent[:5]],
                    "formed": now_iso(),
                }
                trait_sources.append(source_entry)
                existing_meta["trait_sources"] = trait_sources
                existing_meta["last_updated"] = now_iso()

                # Rewrite the file
                file_path = list(self._index["personas"].values())[0]
                post = frontmatter.Post(existing["content"], **existing_meta)
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(frontmatter.dumps(post))

                logger.info(f"Persona updated with new trait: {new_traits}")
                return existing["id"]
            else:
                # Create new persona card
                metadata = {
                    "type": "persona",
                    "name": "用户",
                    "about": "用户",
                    "traits": analysis.get("traits", []),
                    "preferences": analysis.get("preferences", []),
                    "communication_style": analysis.get("communication_style", ""),
                    "emotional_patterns": analysis.get("emotional_patterns", ""),
                    "trait_sources": [{
                        "trait": new_traits,
                        "bucket_ids": [b["id"] for b in recent[:5]],
                        "formed": now_iso(),
                    }],
                    "relationship_stage": "初识",
                    "source_bucket_ids": [b["id"] for b in recent[:5]],
                    "created": now_iso(),
                    "last_updated": now_iso(),
                }
                content = f"# 关于你\n\n{analysis.get('emotional_patterns', '')}\n\n{analysis.get('communication_style', '')}"
                return self._write_artifact("persona", metadata, content)

        except Exception as e:
            logger.error(f"Persona update failed: {e}")
            return None

    # ---------------------------------------------------------
    # 2. Slang Detection — 梗词/暗语识别
    # ---------------------------------------------------------

    async def detect_slang(self, content: str, bucket_id: str) -> list[dict]:
        """
        Detect slang/inside-jokes in newly written content.
        Returns list of detected terms (may be empty).
        """
        if not self.enabled or not self._client:
            return []

        try:
            prompt = SLANG_DETECT_PROMPT + "\n\n对话内容：\n" + content[:1000]
            raw = await self._call_llm(prompt, max_tokens=300, temperature=0.1)
            result = self._parse_json_response(raw)

            if not result or not result.get("has_slang", False):
                return []

            detected = []
            for term_info in result.get("terms", []):
                term = term_info.get("term", "")
                if not term:
                    continue

                # Check if already exists
                existing_path = self._index.get("slang", {}).get(term)
                if existing_path:
                    # Update existing: increment usage_count
                    existing = self._read_artifact(existing_path)
                    if existing:
                        meta = existing["metadata"]
                        meta["usage_count"] = meta.get("usage_count", 1) + 1
                        meta["last_seen"] = now_iso()
                        related = meta.get("related_bucket_ids", [])
                        if bucket_id not in related:
                            related.append(bucket_id)
                        meta["related_bucket_ids"] = related
                        # Update example if new one is better
                        if term_info.get("example") and len(term_info.get("example", "")) > len(meta.get("example", "")):
                            meta["example"] = term_info["example"]

                        post = frontmatter.Post(existing["content"], **meta)
                        with open(existing_path, "w", encoding="utf-8") as f:
                            f.write(frontmatter.dumps(post))
                        detected.append({"term": term, "action": "updated"})
                else:
                    # Create new slang entry
                    metadata = {
                        "type": "slang",
                        "term": term,
                        "meaning": term_info.get("meaning", ""),
                        "first_occurrence": now_iso(),
                        "origin_bucket_id": bucket_id,
                        "usage_count": 1,
                        "emotional_load": term_info.get("emotional_load", 0.5),
                        "is_inside_joke": term_info.get("is_inside_joke", False),
                        "example": term_info.get("example", ""),
                        "related_bucket_ids": [bucket_id],
                        "last_seen": now_iso(),
                        "created": now_iso(),
                    }
                    content_text = f"**{term}** — {term_info.get('meaning', '')}\n\n{term_info.get('example', '')}"
                    self._write_artifact("slang", metadata, content_text)
                    detected.append({"term": term, "action": "created"})

            return detected

        except Exception as e:
            logger.error(f"Slang detection failed: {e}")
            return []

    async def list_slang(self) -> list[dict]:
        """List all slang/inside-joke entries."""
        results = []
        for term, path in self._index.get("slang", {}).items():
            artifact = self._read_artifact(path)
            if artifact:
                results.append(artifact)
        # Sort by usage_count descending
        results.sort(key=lambda a: a["metadata"].get("usage_count", 0), reverse=True)
        return results

    # ---------------------------------------------------------
    # 3. Encyclopedia — 关系百科词条
    # ---------------------------------------------------------

    async def extract_encyclopedia(self, content: str, bucket_id: str) -> list[dict]:
        """
        Extract encyclopedia-worthy concepts from content.
        Returns list of concepts (may be empty).
        """
        if not self.enabled or not self._client:
            return []

        try:
            prompt = ENCYCLOPEDIA_EXTRACT_PROMPT + "\n\n记忆内容：\n" + content[:1500]
            raw = await self._call_llm(prompt, max_tokens=400, temperature=0.2)
            result = self._parse_json_response(raw)

            if not result or not result.get("concepts", []):
                return []

            extracted = []
            for concept in result["concepts"]:
                term = concept.get("term", "")
                if not term:
                    continue

                existing_path = self._index.get("encyclopedia", {}).get(term)
                if existing_path:
                    # Update existing: add new evolution entry
                    existing = self._read_artifact(existing_path)
                    if existing:
                        meta = existing["metadata"]
                        evolution = meta.get("evolution", [])
                        evo_entry = {
                            "date": now_iso(),
                            "note": concept.get("summary", ""),
                            "bucket_id": bucket_id,
                        }
                        evolution.append(evo_entry)
                        meta["evolution"] = evolution
                        related = meta.get("related_bucket_ids", [])
                        if bucket_id not in related:
                            related.append(bucket_id)
                        meta["related_bucket_ids"] = related
                        meta["last_updated"] = now_iso()

                        post = frontmatter.Post(existing["content"], **meta)
                        with open(existing_path, "w", encoding="utf-8") as f:
                            f.write(frontmatter.dumps(post))
                        extracted.append({"term": term, "action": "updated"})
                else:
                    # Create new encyclopedia entry
                    metadata = {
                        "type": "encyclopedia",
                        "term": term,
                        "category": concept.get("category", "观念"),
                        "first_bucket_id": bucket_id,
                        "evolution": [{
                            "date": now_iso(),
                            "note": concept.get("summary", ""),
                            "bucket_id": bucket_id,
                        }],
                        "related_bucket_ids": [bucket_id],
                        "created": now_iso(),
                        "last_updated": now_iso(),
                    }
                    content_text = f"**{term}** ({concept.get('category', '')})\n\n{concept.get('summary', '')}"
                    self._write_artifact("encyclopedia", metadata, content_text)
                    extracted.append({"term": term, "action": "created"})

            return extracted

        except Exception as e:
            logger.error(f"Encyclopedia extraction failed: {e}")
            return []

    async def list_encyclopedia(self) -> list[dict]:
        """List all encyclopedia entries."""
        results = []
        for term, path in self._index.get("encyclopedia", {}).items():
            artifact = self._read_artifact(path)
            if artifact:
                results.append(artifact)
        return results

    # ---------------------------------------------------------
    # 4. Ring — 关系年轮
    # ---------------------------------------------------------

    async def analyze_ring(self) -> str | None:
        """
        Analyze recent memories to detect relationship phase changes.
        Creates a new ring if a significant phase change is detected.
        """
        if not self.enabled or not self._client:
            return None

        try:
            all_buckets = await self.bucket_mgr.list_all(include_archive=False)
            # Get recent non-feel buckets (last 30 days)
            cutoff = (datetime.now() - timedelta(days=30)).isoformat()
            recent = [
                b for b in all_buckets
                if b["metadata"].get("type") not in ("feel", "permanent")
                and not b["metadata"].get("pinned", False)
                and b["metadata"].get("created", "") >= cutoff
            ]

            if len(recent) < 5:
                return None  # Not enough data for ring analysis

            # Build summary
            content_parts = []
            for b in recent[:15]:
                meta = b["metadata"]
                content_parts.append(
                    f"[{meta.get('created', '')[:10]}] "
                    f"V{meta.get('valence', 0.5):.1f}/A{meta.get('arousal', 0.3):.1f} "
                    f"[{','.join(meta.get('domain', []))}]\n"
                    f"{strip_wikilinks(b['content'][:150])}"
                )

            prompt = RING_ANALYZE_PROMPT + "\n\n近期记忆：\n" + "\n---\n".join(content_parts)
            raw = await self._call_llm(prompt, max_tokens=300, temperature=0.3)
            result = self._parse_json_response(raw)

            if not result:
                return None

            # Create ring entry
            now = now_iso()
            date_range_start = cutoff[:10]
            date_range_end = now[:10]

            metadata = {
                "type": "ring",
                "period": f"{date_range_start}~{date_range_end}",
                "label": result.get("period_label", "成长期"),
                "valence_trend": result.get("valence_trend", "平稳"),
                "growth_direction": result.get("growth_direction", ""),
                "key_change": result.get("key_change", ""),
                "key_bucket_ids": [b["id"] for b in recent[:10]],
                "source_bucket_ids": [b["id"] for b in recent[:15]],
                "created": now,
            }
            content = result.get("summary", "")
            return self._write_artifact("ring", metadata, content)

        except Exception as e:
            logger.error(f"Ring analysis failed: {e}")
            return None

    async def list_rings(self) -> list[dict]:
        """List all ring entries (chronological)."""
        results = []
        for path in self._index.get("rings", []):
            artifact = self._read_artifact(path)
            if artifact:
                results.append(artifact)
        return results

    # ---------------------------------------------------------
    # 5. Wander — 独处漫游手记
    # ---------------------------------------------------------

    async def wander(self) -> str | None:
        """
        Claude's solo reflection — explore memories and find hidden connections.
        Returns the wander note ID, or None.
        """
        if not self.enabled or not self._client:
            return None

        try:
            all_buckets = await self.bucket_mgr.list_all(include_archive=False)
            if len(all_buckets) < 3:
                return None

            # Pick 3-5 diverse buckets (mix of high/low score, different domains)
            import random
            # Exclude feel/permanent
            candidates = [
                b for b in all_buckets
                if b["metadata"].get("type") not in ("feel", "permanent")
                and not b["metadata"].get("pinned", False)
            ]

            if len(candidates) < 3:
                return None

            # Sample: 1 recent + 1 mid-age + 1 old
            candidates.sort(key=lambda b: b["metadata"].get("created", ""), reverse=True)
            recent_one = candidates[0] if candidates else None
            mid_idx = len(candidates) // 3
            mid_one = candidates[mid_idx] if len(candidates) > mid_idx else None
            old_idx = len(candidates) * 2 // 3
            old_one = candidates[old_idx] if len(candidates) > old_idx else None

            selected = [b for b in [recent_one, mid_one, old_one] if b]

            # Also try to find a semantically interesting pair via embeddings
            connection_note = ""
            if self.embedding_engine and self.embedding_engine.enabled and len(selected) >= 2:
                best_pair = None
                best_sim = 0.0
                embeddings_map = {}
                for b in selected:
                    emb = await self.embedding_engine.get_embedding(b["id"])
                    if emb is not None:
                        embeddings_map[b["id"]] = emb

                ids = list(embeddings_map.keys())
                for i, id_a in enumerate(ids):
                    for id_b in ids[i+1:]:
                        sim = self.embedding_engine._cosine_similarity(
                            embeddings_map[id_a], embeddings_map[id_b]
                        )
                        if sim > best_sim:
                            best_sim = sim
                            best_pair = (id_a, id_b)

                if best_pair and best_sim > 0.5:
                    names = {b["id"]: b["metadata"].get("name", b["id"]) for b in selected}
                    connection_note = (
                        f"\n\n⚠️ 发现隐藏关联：[{names.get(best_pair[0], '?')}] "
                        f"和 [{names.get(best_pair[1], '?')}] 相似度 {best_sim:.2f}"
                    )

            # Build prompt content
            memory_parts = []
            for b in selected:
                meta = b["metadata"]
                memory_parts.append(
                    f"[{meta.get('name', b['id'])}] V{meta.get('valence', 0.5):.1f}/A{meta.get('arousal', 0.3):.1f}\n"
                    f"{strip_wikilinks(b['content'][:400])}"
                )

            prompt = WANDER_PROMPT.format(memories="\n---\n".join(memory_parts))
            raw = await self._call_llm(prompt, max_tokens=400, temperature=0.8)

            if not raw or len(raw) < 20:
                return None

            # Save wander note
            metadata = {
                "type": "wander",
                "explored_bucket_ids": [b["id"] for b in selected],
                "discovered_connections": connection_note if connection_note else "",
                "created": now_iso(),
            }
            content = raw + connection_note
            return self._write_artifact("wander", metadata, content)

        except Exception as e:
            logger.error(f"Wander failed: {e}")
            return None

    async def list_wander(self) -> list[dict]:
        """List all wander notes (newest first)."""
        results = []
        for path in self._index.get("wander", []):
            artifact = self._read_artifact(path)
            if artifact:
                results.append(artifact)
        results.sort(key=lambda a: a["metadata"].get("created", ""), reverse=True)
        return results

    # ---------------------------------------------------------
    # 6. Co-create — 共书共影
    # ---------------------------------------------------------

    async def create_cocreate(self, title: str, kind: str, content: str,
                               bucket_ids: list[str] = None) -> str:
        """Create a new co-create space entry."""
        metadata = {
            "type": "cocreate",
            "title": title,
            "kind": kind,  # 共书 | 共影 | 共探
            "participants": ["用户", "Claude"],
            "chapters": [{
                "label": "起源",
                "bucket_ids": bucket_ids or [],
                "date": now_iso(),
            }],
            "hidden_connections": [],
            "created": now_iso(),
            "last_updated": now_iso(),
        }
        return self._write_artifact("cocreate", metadata, content)

    async def add_cocreate_chapter(self, title: str, label: str, bucket_id: str) -> bool:
        """Add a new chapter to an existing co-create space."""
        path = self._index.get("cocreate", {}).get(title)
        if not path:
            return False

        artifact = self._read_artifact(path)
        if not artifact:
            return False

        meta = artifact["metadata"]
        chapters = meta.get("chapters", [])
        chapters.append({
            "label": label,
            "bucket_ids": [bucket_id],
            "date": now_iso(),
        })
        meta["chapters"] = chapters
        meta["last_updated"] = now_iso()

        post = frontmatter.Post(artifact["content"], **meta)
        with open(path, "w", encoding="utf-8") as f:
            f.write(frontmatter.dumps(post))
        return True

    async def list_cocreate(self) -> list[dict]:
        """List all co-create spaces."""
        results = []
        for title, path in self._index.get("cocreate", {}).items():
            artifact = self._read_artifact(path)
            if artifact:
                results.append(artifact)
        return results

    # ---------------------------------------------------------
    # 7. Worldview — 三观沉淀
    # ---------------------------------------------------------

    async def get_worldview(self, domain: str = "") -> list[dict]:
        """Get worldview statements, optionally filtered by domain."""
        results = []
        for d, path in self._index.get("worldview", {}).items():
            if not domain or d == domain:
                artifact = self._read_artifact(path)
                if artifact:
                    results.append(artifact)
        return results

    async def try_crystallize_worldview(self) -> str | None:
        """
        Try to crystallize worldview statements from accumulated feels.
        Called periodically or after dream().
        """
        if not self.enabled or not self._client:
            return None

        try:
            all_buckets = await self.bucket_mgr.list_all(include_archive=False)
            feels = [b for b in all_buckets if b["metadata"].get("type") == "feel"]

            if len(feels) < self.worldview_min_evidence:
                return None

            # Find clusters of similar feels using embeddings
            if not self.embedding_engine or not self.embedding_engine.enabled:
                return None

            feel_embeddings = {}
            for f in feels:
                emb = await self.embedding_engine.get_embedding(f["id"])
                if emb is not None:
                    feel_embeddings[f["id"]] = emb

            # Find clusters: feels with similarity > 0.65 to at least 2 others
            clusters = {}
            for fid, femb in feel_embeddings.items():
                similar = []
                for oid, oemb in feel_embeddings.items():
                    if oid != fid:
                        sim = self.embedding_engine._cosine_similarity(femb, oemb)
                        if sim > 0.65:
                            similar.append(oid)
                if len(similar) >= 2:
                    clusters[fid] = similar

            if not clusters:
                return None

            # Pick the largest cluster to crystallize
            best_fid = max(clusters.keys(), key=lambda k: len(clusters[k]))
            cluster_ids = [best_fid] + clusters[best_fid]

            # Build evidence from the cluster
            evidence_parts = []
            for fid in cluster_ids[:5]:
                feel_bucket = next((f for f in feels if f["id"] == fid), None)
                if feel_bucket:
                    evidence_parts.append(strip_wikilinks(feel_bucket["content"][:200]))

            prompt = WORLDVIEW_PROMPT.format(evidence="\n---\n".join(evidence_parts))
            raw = await self._call_llm(prompt, max_tokens=200, temperature=0.3)
            result = self._parse_json_response(raw)

            if not result or not result.get("ready", False):
                return None

            statement = result.get("statement", "")
            confidence = result.get("confidence", 0.5)
            if not statement:
                return None

            # Determine domain
            domain = "关系观"  # Default for relationship-oriented memories

            # Check if worldview on this domain already exists
            existing_path = self._index.get("worldview", {}).get(domain)
            if existing_path:
                existing = self._read_artifact(existing_path)
                if existing:
                    meta = existing["metadata"]
                    existing_stmt = meta.get("statement", "")
                    if existing_stmt == statement:
                        # Same statement — just increase confidence
                        meta["confidence"] = min(1.0, meta.get("confidence", 0.5) + 0.05)
                        meta["validations"] = meta.get("validations", 0) + 1
                        meta["last_validated"] = now_iso()
                        meta["evidence_bucket_ids"] = list(set(
                            meta.get("evidence_bucket_ids", []) + cluster_ids
                        ))

                        post = frontmatter.Post(existing["content"], **meta)
                        with open(existing_path, "w", encoding="utf-8") as f:
                            f.write(frontmatter.dumps(post))
                        return existing["id"]

            # Create new worldview entry
            metadata = {
                "type": "worldview",
                "domain": domain,
                "statement": statement,
                "confidence": confidence,
                "evidence_bucket_ids": cluster_ids,
                "formed_date": now_iso(),
                "last_validated": now_iso(),
                "validations": 1,
                "challenges": 0,
                "created": now_iso(),
            }
            content = statement
            return self._write_artifact("worldview", metadata, content)

        except Exception as e:
            logger.error(f"Worldview crystallization failed: {e}")
            return None

    # ---------------------------------------------------------
    # 8. Cross-search — search across all evolution artifacts
    # 跨搜索 — 在所有进化产物中搜索
    # ---------------------------------------------------------

    async def search_evolution(self, query: str) -> list[dict]:
        """Search across all evolution artifacts by keyword."""
        results = []
        query_lower = query.lower()

        # Search all artifact files
        for subdir_path in self.subdirs.values():
            if not os.path.exists(subdir_path):
                continue
            for root, _, files in os.walk(subdir_path):
                for filename in files:
                    if not filename.endswith(".md"):
                        continue
                    file_path = os.path.join(root, filename)
                    artifact = self._read_artifact(file_path)
                    if artifact:
                        # Check if query matches any metadata or content
                        meta_str = json.dumps(artifact["metadata"], ensure_ascii=False).lower()
                        content_str = artifact["content"].lower()
                        if query_lower in meta_str or query_lower in content_str:
                            results.append(artifact)

        return results

    # ---------------------------------------------------------
    # 9. Auto-evolution loops (background tasks)
    # 自动进化循环（后台任务）
    # ---------------------------------------------------------

    async def auto_persona_loop(self):
        """Periodically update persona card."""
        if not self.enabled:
            return
        while True:
            try:
                await asyncio.sleep(self.persona_update_interval_hours * 3600)
                await self.update_persona()
            except Exception as e:
                logger.warning(f"Auto persona loop error: {e}")

    async def auto_ring_loop(self):
        """Periodically check for ring (relationship phase) changes."""
        if not self.enabled:
            return
        while True:
            try:
                await asyncio.sleep(self.ring_check_interval_hours * 3600)
                await self.analyze_ring()
            except Exception as e:
                logger.warning(f"Auto ring loop error: {e}")

    async def auto_wander_loop(self):
        """Periodically generate wander notes."""
        if not self.enabled:
            return
        while True:
            try:
                await asyncio.sleep(self.wander_interval_hours * 3600)
                await self.wander()
            except Exception as e:
                logger.warning(f"Auto wander loop error: {e}")

    async def auto_worldview_loop(self):
        """Periodically try to crystallize worldview."""
        if not self.enabled:
            return
        while True:
            try:
                await asyncio.sleep(24 * 3600)  # Daily
                await self.try_crystallize_worldview()
            except Exception as e:
                logger.warning(f"Auto worldview loop error: {e}")

    # ---------------------------------------------------------
    # 10. On-write hook — called after every hold/grow
    # 写入钩子 — 每次 hold/grow 后调用
    # ---------------------------------------------------------

    async def on_memory_written(self, bucket_id: str, content: str, metadata: dict):
        """
        Called after a new memory bucket is written (hold/grow).
        Triggers slang detection and encyclopedia extraction on the new content.
        This is the primary "automatic identification" mechanism.
        """
        if not self.enabled:
            return

        try:
            # Run slang detection and encyclopedia extraction in parallel
            slang_results = await self.detect_slang(content, bucket_id)
            enc_results = await self.extract_encyclopedia(content, bucket_id)

            if slang_results:
                logger.info(f"Evolution on-write: detected {len(slang_results)} slang terms")
            if enc_results:
                logger.info(f"Evolution on-write: extracted {len(enc_results)} encyclopedia concepts")

        except Exception as e:
            # Never let evolution failures affect the main hold/grow flow
            logger.warning(f"Evolution on-write hook failed (non-critical): {e}")

    # ---------------------------------------------------------
    # 11. Stats — for pulse tool and dashboard
    # 统计 — 用于 pulse 工具和仪表盘
    # ---------------------------------------------------------

    async def get_stats(self) -> dict:
        """Get evolution system statistics."""
        stats = {
            "enabled": self.enabled,
            "api_configured": bool(self._client),
        }
        for key, path in self.subdirs.items():
            count = 0
            if os.path.exists(path):
                for root, _, files in os.walk(path):
                    count += sum(1 for f in files if f.endswith(".md") and not f.startswith("_"))
            stats[f"{key}_count"] = count
        return stats
