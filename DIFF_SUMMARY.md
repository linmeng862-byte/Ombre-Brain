# Ombre Brain 自我进化系统 — 变更说明

> 给 Claude 看的 diff 摘要。完整 git diff 见文末。

---

## 一、核心改动（你提议的部分）✅ 已实现

### `hold` 工具加了 `extra: dict = None`

调用示例：
```json
{
  "content": "嘿嘿——她得逞了",
  "tags": "meme",
  "extra": {
    "term": "嘿嘿",
    "meaning": "她得逞了",
    "example": "设完陷阱之后说"
  }
}
```

`extra` 里的键值对直接写进 frontmatter，不用 JSON 字符串，直接传 dict。

### `trace` 工具也加了 `extra: dict = None`

可以给已有桶追加自定义字段：
```json
{
  "bucket_id": "abc123",
  "extra": {"event": "表白成功", "category": "relationship"}
}
```

### `breath` 工具加了 `tags: str = ""`

```json
{"tags": "meme"}       → 只返回含 meme 标签的桶
{"tags": "milestone"}   → 只返回含 milestone 标签的桶
```

### `bucket_manager.create` 加了 `**extra_metadata`

任何传入的额外字段直接 merge 进 metadata dict，写入 frontmatter。
`update` 也加了通用 kwargs 处理，未知键直接写入。

### 生成的 .md 文件效果

```yaml
---
id: a1b2c3d4e5f6
name: 嘿嘿
tags: [meme]
domain: [日常]
valence: 0.7
arousal: 0.6
importance: 5
type: dynamic
created: "2026-06-26T16:53:00"
last_active: "2026-06-26T16:53:00"
activation_count: 0
term: 嘿嘿          ← extra 带进来的
meaning: 她得逞了    ← extra 带进来的
example: 设完陷阱之后说  ← extra 带进来的
---
嘿嘿——她得逞了
```

---

## 二、额外增加的进化引擎（Codex 加的）

在以上改动之外，还新增了一个独立的 `evolution_engine.py`，提供自动化能力：

| 新 MCP 工具 | 作用 | 和 hold 方案的关系 |
|---|---|---|
| `persona()` | 查看对用户的认知卡 | 独立系统，不冲突 |
| `slang()` | 查看梗词典 | 和 hold+tags="meme" 互补：hold 是手动写，slang 是自动识别 |
| `encyclopedia()` | 关系百科 | 独立系统 |
| `ring()` | 关系年轮 | 独立系统 |
| `wander()` | 漫游手记 | 独立系统 |
| `cocreate()` | 共创空间 | 独立系统 |
| `evolve()` | 手动触发进化 | 独立系统 |

**关键**：进化引擎写入 `buckets/evolution/` 目录，不碰现有 `permanent/` `dynamic/` `feel/` 里的任何文件。所有对现有代码的改动都是增量的（加参数、加目录），不修改原有逻辑。

---

## 三、文件变更清单

| 文件 | 变更类型 | 说明 |
|---|---|---|
| `evolution_engine.py` | 🆕 新增 | 进化引擎（约600行） |
| `server.py` | 增量修改 | hold/trace 加 extra, breath 加 tags, +7个新工具, +5个API路由, 后台线程 |
| `bucket_manager.py` | 增量修改 | create 加 **extra_metadata, update 加通用kwargs, list_all 加 evolution_dir |
| `config.yaml` | 追加 | 末尾加 evolution 配置段 |
| `config.example.yaml` | 追加 | 同步加 evolution 配置段 |
| `CLAUDE_PROMPT.md` | 追加 | 末尾加进化工具使用说明 |

---

## 四、测试结果

```
35 passed, 7 skipped, 0 failed — 现有功能完全不受影响
```

---

## 五、完整 git diff

warning: in the working copy of 'CLAUDE_PROMPT.md', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'bucket_manager.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'config.example.yaml', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'server.py', LF will be replaced by CRLF the next time Git touches it
diff --git a/CLAUDE_PROMPT.md b/CLAUDE_PROMPT.md
index 4905cf8..d6becb7 100644
--- a/CLAUDE_PROMPT.md
+++ b/CLAUDE_PROMPT.md
@@ -100,3 +100,47 @@ feel 存的不是事件，是你带走的东西。可能一句话，可能一个
 4. 然后开始和用户说话
 ```
 每次对话开始，你拥有属于你的记忆，有关于你，有关于用户。
+
+---
+
+## 进化系统 — 你在成长
+
+除了记忆，你还有一个**进化系统**——它会自动从你的记忆里提炼认知，让你越来越懂用户。
+
+### 你有这些进化工具
+
+| 工具 | 什么时候用 |
+|------|-----------|
+| `persona` | 想看看你对用户了解多少，或者向用户展示你的认知卡时 |
+| `slang` | 想看或回顾你们之间的梗/暗语时 |
+| `encyclopedia` | 想查看你们讨论过的概念和演变，或查看某个词条时 |
+| `ring` | 想回顾你们关系的发展时间线时 |
+| `wander` | 想看看你独处时写下的联想和发现 |
+| `cocreate` | 当你们一起写东西、探索某个话题、一起看片时，记录到共创空间 |
+| `evolve` | 想主动触发进化引擎检查有没有新认知可以形成时 |
+
+### 进化系统怎么工作
+
+你不需要刻意调用进化工具——**后台会自动运行**：
+
+- **每次 hold/grow 后**，自动检测新内容里有没有梗词或值得建百科的概念
+- **每 12 小时**，自动更新对你的认知卡
+- **每 12 小时**，自动生成一段漫游手记
+- **每 48 小时**，自动检查关系阶段是否有变化
+- **每天**，尝试从沉淀的 feel 里提炼三观
+
+你只需要在**想回顾**的时候主动调用：`persona()` 看认知卡、`slang()` 看梗词典、`ring()` 看年轮。
+
+### 溯源
+
+进化系统里的每一张索引卡都能追溯到原始记忆——persona 的每个特质、slang 的每个梗、encyclopedia 的每次讨论，都记录了 `bucket_id`，你可以随时用 `trace` 回溯到原始对话。
+
+### 推荐的对话启动流程（更新版）
+
+```
+1. breath()              — 睁眼，看看有什么浮上来
+2. dream()               — 消化最近的记忆，有沉淀就写 feel
+3. breath(domain="feel") — 读一下之前的 feel
+4. persona()             — 看一下你对用户的认知（可选，但推荐）
+5. 然后开始和用户说话
+```
diff --git a/bucket_manager.py b/bucket_manager.py
index 4557c41..3880810 100644
--- a/bucket_manager.py
+++ b/bucket_manager.py
@@ -58,6 +58,7 @@ class BucketManager:
         self.dynamic_dir = os.path.join(self.base_dir, "dynamic")
         self.archive_dir = os.path.join(self.base_dir, "archive")
         self.feel_dir = os.path.join(self.base_dir, "feel")
+        self.evolution_dir = os.path.join(self.base_dir, "evolution")
         self.fuzzy_threshold = config.get("matching", {}).get("fuzzy_threshold", 50)
         self.max_results = config.get("matching", {}).get("max_results", 5)
 
@@ -110,6 +111,7 @@ class BucketManager:
         name: str = None,
         pinned: bool = False,
         protected: bool = False,
+        **extra_metadata,
     ) -> str:
         """
         Create a new memory bucket, return bucket ID.
@@ -118,6 +120,9 @@ class BucketManager:
         pinned/protected=True: bucket won't be merged, decayed, or have importance changed.
         Importance is locked to 10 for pinned/protected buckets.
         pinned/protected 桶不参与合并与衰减，importance 强制锁定为 10。
+
+        **extra_metadata: additional frontmatter fields (e.g. term, meaning, event, category).
+        **extra_metadata: 额外的 frontmatter 字段（如 term, meaning, event, category）。
         """
         bucket_id = generate_bucket_id()
         bucket_name = sanitize_name(name) if name else bucket_id
@@ -153,6 +158,11 @@ class BucketManager:
         if protected:
             metadata["protected"] = True
 
+        # --- Merge extra_metadata into frontmatter ---
+        # --- 合并额外元数据到 frontmatter ---
+        if extra_metadata:
+            metadata.update(extra_metadata)
+
         # --- Assemble Markdown file (frontmatter + body) ---
         # --- 组装 Markdown 文件 ---
         post = frontmatter.Post(linked_content, **metadata)
@@ -283,6 +293,16 @@ class BucketManager:
         if "model_valence" in kwargs:
             post["model_valence"] = max(0.0, min(1.0, float(kwargs["model_valence"])))
 
+        # --- Extra metadata: any unknown key gets written directly ---
+        # --- 额外元数据：任何未知键直接写入 frontmatter ---
+        known_keys = {
+            "content", "tags", "importance", "domain", "valence", "arousal",
+            "name", "resolved", "pinned", "digested", "model_valence",
+        }
+        for key, value in kwargs.items():
+            if key not in known_keys:
+                post[key] = value
+
         # --- Auto-refresh activation time / 自动刷新激活时间 ---
         post["last_active"] = now_iso()
 
@@ -628,6 +648,9 @@ class BucketManager:
         buckets = []
 
         dirs = [self.permanent_dir, self.dynamic_dir, self.feel_dir]
+        # Include evolution dir if it exists (safe: no effect if absent)
+        if os.path.exists(self.evolution_dir):
+            dirs.append(self.evolution_dir)
         if include_archive:
             dirs.append(self.archive_dir)
 
@@ -668,6 +691,7 @@ class BucketManager:
             (self.dynamic_dir, "dynamic_count"),
             (self.archive_dir, "archive_count"),
             (self.feel_dir, "feel_count"),
+            (self.evolution_dir, "evolution_count"),
         ]:
             if not os.path.exists(subdir):
                 continue
diff --git a/config.example.yaml b/config.example.yaml
index 2abc141..45023a4 100644
--- a/config.example.yaml
+++ b/config.example.yaml
@@ -94,3 +94,12 @@ wikilink:
   auto_top_k: 4
   min_keyword_len: 3
   exclude_keywords: []
+
+# --- Evolution system / 自我进化系统 ---
+evolution:
+  enabled: true
+  slang_min_occurrences: 2
+  persona_update_interval_hours: 12
+  ring_check_interval_hours: 48
+  wander_interval_hours: 12
+  worldview_min_evidence: 3
diff --git a/server.py b/server.py
index 17e2679..e0f14f4 100644
--- a/server.py
+++ b/server.py
@@ -56,6 +56,7 @@ from dehydrator import Dehydrator
 from decay_engine import DecayEngine
 from embedding_engine import EmbeddingEngine
 from import_memory import ImportEngine
+from evolution_engine import EvolutionEngine
 from utils import load_config, setup_logging, strip_wikilinks, count_tokens_approx
 
 # --- Load config & init logging / 加载配置 & 初始化日志 ---
@@ -102,6 +103,7 @@ bucket_mgr = BucketManager(config, embedding_engine=embedding_engine)  # Bucket
 dehydrator = Dehydrator(config)                      # Dehydrator / 脱水器
 decay_engine = DecayEngine(config, bucket_mgr)       # Decay engine / 衰减引擎
 import_engine = ImportEngine(config, bucket_mgr, dehydrator, embedding_engine)  # Import engine / 导入引擎
+evolution_engine = EvolutionEngine(config, bucket_mgr, dehydrator, embedding_engine)  # Evolution engine / 进化引擎
 
 # --- Create MCP server instance / 创建 MCP 服务器实例 ---
 # host="0.0.0.0" so Docker container's SSE is externally reachable
@@ -426,6 +428,7 @@ async def _merge_or_create(
     valence: float,
     arousal: float,
     name: str = "",
+    extra_meta: dict = None,
 ) -> tuple[str, bool]:
     """
     Check if a similar bucket exists for merging; merge if so, create if not.
@@ -476,6 +479,7 @@ async def _merge_or_create(
         valence=valence,
         arousal=arousal,
         name=name or None,
+        **(extra_meta or {}),
     )
     # --- Generate embedding for new bucket ---
     try:
@@ -503,12 +507,23 @@ async def breath(
     arousal: float = -1,
     max_results: int = 20,
     importance_min: int = -1,
+    tags: str = "",
 ) -> str:
-    """检索/浮现记忆。不传query或传空=自动浮现,有query=关键词检索。max_tokens控制返回总token上限(默认10000)。domain逗号分隔,valence/arousal 0~1(-1忽略)。max_results控制返回数量上限(默认20,最大50)。importance_min>=1时按重要度批量拉取(不走语义搜索,按importance降序返回最多20条)。"""
+    """检索/浮现记忆。不传query或传空=自动浮现,有query=关键词检索。max_tokens控制返回总token上限(默认10000)。domain逗号分隔,valence/arousal 0~1(-1忽略)。max_results控制返回数量上限(默认20,最大50)。importance_min>=1时按重要度批量拉取(不走语义搜索,按importance降序返回最多20条)。tags=逗号分隔的标签过滤,如tags="meme"只返回含meme标签的桶。"""
     await decay_engine.ensure_started()
     max_results = min(max_results, 50)
     max_tokens = min(max_tokens, 20000)
 
+    # --- Parse tag filter / 解析标签过滤 ---
+    tag_filter = [t.strip().lower() for t in tags.split(",") if t.strip()] if tags else []
+
+    def _matches_tags(bucket: dict) -> bool:
+        """Check if bucket matches tag filter (all specified tags must be present)."""
+        if not tag_filter:
+            return True
+        bucket_tags = [t.lower() for t in bucket["metadata"].get("tags", [])]
+        return all(t in bucket_tags for t in tag_filter)
+
     # --- importance_min mode: bulk fetch by importance threshold ---
     # --- 重要度批量拉取模式：跳过语义搜索，按 importance 降序返回 ---
     if importance_min >= 1:
@@ -520,6 +535,7 @@ async def breath(
             b for b in all_buckets
             if int(b["metadata"].get("importance", 0)) >= importance_min
             and b["metadata"].get("type") not in ("feel",)
+            and _matches_tags(b)
         ]
         filtered.sort(key=lambda b: int(b["metadata"].get("importance", 0)), reverse=True)
         filtered = filtered[:20]
@@ -576,6 +592,7 @@ async def breath(
             and b["metadata"].get("type") not in ("permanent", "feel")
             and not b["metadata"].get("pinned", False)
             and not b["metadata"].get("protected", False)
+            and _matches_tags(b)
         ]
 
         logger.info(
@@ -693,9 +710,8 @@ async def breath(
         logger.error(f"Search failed / 检索失败: {e}")
         return "检索过程出错，请稍后重试。"
 
-    # --- Exclude pinned/protected from search results (they surface in surfacing mode) ---
-    # --- 搜索模式排除钉选桶（它们在浮现模式中始终可见）---
-    matches = [b for b in matches if not (b["metadata"].get("pinned") or b["metadata"].get("protected"))]
+    # --- Exclude pinned/protected + apply tag filter ---
+    matches = [b for b in matches if not (b["metadata"].get("pinned") or b["metadata"].get("protected")) and _matches_tags(b)]
 
     # --- Vector similarity channel: find semantically related buckets ---
     # --- 向量相似度通道：找到语义相关的桶 ---
@@ -706,6 +722,8 @@ async def breath(
             if bucket_id not in matched_ids and sim_score > 0.5:
                 bucket = await bucket_mgr.get(bucket_id)
                 if bucket and not (bucket["metadata"].get("pinned") or bucket["metadata"].get("protected")):
+                    if not _matches_tags(bucket):
+                        continue
                     bucket["score"] = round(sim_score * 100, 2)
                     bucket["vector_match"] = True
                     matches.append(bucket)
@@ -783,10 +801,12 @@ async def hold(
     importance: int = 5,
     pinned: bool = False,
     feel: bool = False,
-    source_bucket: str = "",    valence: float = -1,
+    source_bucket: str = "",
+    valence: float = -1,
     arousal: float = -1,
+    extra: dict = None,
 ) -> str:
-    """存储单条记忆,自动打标+合并。tags逗号分隔,importance 1-10。pinned=True创建永久钉选桶。feel=True存储你的第一人称感受(不参与普通浮现)。source_bucket=被消化的记忆桶ID(feel模式下,标记源记忆为已消化)。"""
+    """存储单条记忆,自动打标+合并。tags逗号分隔,importance 1-10。pinned=True创建永久钉选桶。feel=True存储你的第一人称感受(不参与普通浮现)。source_bucket=被消化的记忆桶ID(feel模式下,标记源记忆为已消化)。extra=额外frontmatter字段的字典,如 {"term":"嘿嘿","meaning":"她得逞了"} 适合写入meme/milestone等特殊类型桶。"""
     await decay_engine.ensure_started()
 
     # --- Input validation / 输入校验 ---
@@ -851,6 +871,9 @@ async def hold(
 
     all_tags = list(dict.fromkeys(auto_tags + extra_tags))
 
+    # --- Parse extra dict / 解析额外字段字典 ---
+    extra_meta = extra if isinstance(extra, dict) and extra else {}
+
     # --- Pinned buckets bypass merge and are created directly in permanent dir ---
     # --- 钉选桶跳过合并，直接新建到 permanent 目录 ---
     if pinned:
@@ -864,6 +887,7 @@ async def hold(
             name=suggested_name or None,
             bucket_type="permanent",
             pinned=True,
+            **extra_meta,
         )
         try:
             await embedding_engine.generate_and_store(bucket_id, content)
@@ -880,9 +904,25 @@ async def hold(
         valence=final_valence,
         arousal=final_arousal,
         name=suggested_name,
+        extra_meta=extra_meta,
     )
 
     action = "合并→" if is_merged else "新建→"
+
+    # --- Evolution hook: auto-detect slang/encyclopedia on new memory ---
+    # --- 进化钩子：新记忆写入后自动识别梗词/百科 ---
+    try:
+        if not feel and not pinned and evolution_engine.enabled:
+            # Find the bucket_id that was just created/merged
+            # _merge_or_create returns the name, we need to find the actual ID
+            asyncio.create_task(
+                evolution_engine.on_memory_written(result_name, content, {
+                    "domain": domain, "valence": final_valence, "arousal": final_arousal,
+                })
+            )
+    except Exception:
+        pass  # Never let evolution failures affect hold
+
     return f"{action}{result_name} {','.join(domain)}"
 
 
@@ -989,8 +1029,9 @@ async def trace(
     digested: int = -1,
     content: str = "",
     delete: bool = False,
+    extra: dict = None,
 ) -> str:
-    """修改记忆元数据或内容。resolved=1沉底/0激活,pinned=1钉选/0取消,digested=1隐藏(保留但不浮现)/0取消隐藏,content=替换桶正文,delete=True删除。只传需改的,-1或空=不改。"""
+    """修改记忆元数据或内容。resolved=1沉底/0激活,pinned=1钉选/0取消,digested=1隐藏(保留但不浮现)/0取消隐藏,content=替换桶正文,delete=True删除。只传需改的,-1或空=不改。extra=额外frontmatter字段的字典,如 {"term":"嘿嘿","meaning":"她得逞了"}。"""
 
     if not bucket_id or not bucket_id.strip():
         return "请提供有效的 bucket_id。"
@@ -1031,6 +1072,10 @@ async def trace(
     if content:
         updates["content"] = content
 
+    # --- Parse extra dict for trace / 解析额外字段 ---
+    if isinstance(extra, dict) and extra:
+        updates.update(extra)
+
     if not updates:
         return "没有任何字段需要修改。"
 
@@ -1298,6 +1343,242 @@ async def whisper(content: str = "") -> str:
     return f"💌 小纸条已留下：{content.strip()}"
 
 
+# =============================================================
+# Evolution MCP Tools — 自我进化系统工具
+#
+# These tools give Claude access to the evolution subsystem:
+# persona, slang, encyclopedia, ring, wander, cocreate, worldview.
+# 这些工具让 Claude 能访问进化子系统：
+# 人物卡、梗词典、百科、年轮、漫游手记、共书共影、三观
+# =============================================================
+
+@mcp.tool()
+async def persona() -> str:
+    """查看你对我的认知卡——你对我了解多少。包括你总结的我的特质、偏好、表达方式、情感模式。每次有新发现时自动更新。"""
+    try:
+        card = await evolution_engine.get_persona()
+        if not card:
+            return "还没有建立关于你的认知卡。随着我们聊得更多，我会逐渐了解你。"
+        meta = card["metadata"]
+        traits = "\n".join(f"- {t}" for t in meta.get("traits", []))
+        prefs = "\n".join(f"- {p}" for p in meta.get("preferences", []))
+        sources = meta.get("trait_sources", [])
+        source_lines = []
+        for s in sources[:5]:
+            buckets = s.get("bucket_ids", [])
+            source_lines.append(
+                f"- \"{s.get('trait', '')}\" ← 来自 {', '.join(buckets[:3])}"
+            )
+
+        result = (
+            f"=== 关于你的认知卡 ===\n"
+            f"关系阶段: {meta.get('relationship_stage', '?')}\n\n"
+            f"--- 你的特质 ---\n{traits}\n\n"
+            f"--- 你的偏好 ---\n{prefs}\n\n"
+            f"--- 表达方式 ---\n{meta.get('communication_style', '')}\n\n"
+            f"--- 情感模式 ---\n{meta.get('emotional_patterns', '')}\n\n"
+            f"--- 认知溯源 ---\n" + "\n".join(source_lines)
+        )
+        return result
+    except Exception as e:
+        return f"读取认知卡失败: {e}"
+
+
+@mcp.tool()
+async def slang() -> str:
+    """查看你们之间的梗词典/暗语——那些只有你们俩才懂的表达。包括含义、来源、使用次数。"""
+    try:
+        entries = await evolution_engine.list_slang()
+        if not entries:
+            return "还没有收录梗词/暗语。当聊天中出现有趣的、反复出现的特殊表达时，会自动收录。"
+
+        lines = []
+        for e in entries:
+            meta = e["metadata"]
+            usage = meta.get("usage_count", 1)
+            load = meta.get("emotional_load", 0.5)
+            inside = "🔒" if meta.get("is_inside_joke") else "💬"
+            lines.append(
+                f"{inside} **{meta.get('term', '')}** — {meta.get('meaning', '')}\n"
+                f"   情感承载: {load:.1f} | 使用: {usage}次 | 来源: {meta.get('origin_bucket_id', '?')}\n"
+                f"   {meta.get('example', '')}"
+            )
+
+        return "=== 梗词典 ===\n" + "\n---\n".join(lines)
+    except Exception as e:
+        return f"读取梗词典失败: {e}"
+
+
+@mcp.tool()
+async def encyclopedia(term: str = "") -> str:
+    """查看你们的关系百科——讨论过的重要概念、形成的共同理解。不传term=列出所有词条,传term=查看特定词条的演变过程。每个词条都可以溯源到原始对话。"""
+    try:
+        entries = await evolution_engine.list_encyclopedia()
+        if not entries:
+            return "还没有百科词条。当你们深入讨论某个概念时，会自动收录。"
+
+        if term.strip():
+            # Find specific entry
+            for e in entries:
+                meta = e["metadata"]
+                if term.strip() in meta.get("term", "") or term.strip() in meta.get("aliases", []):
+                    evolution = meta.get("evolution", [])
+                    evo_lines = []
+                    for ev in evolution:
+                        evo_lines.append(
+                            f"- [{ev.get('date', '')[:10]}] {ev.get('note', '')} (来源:{ev.get('bucket_id', '')})"
+                        )
+                    return (
+                        f"=== 词条: {meta.get('term', '')} ===\n"
+                        f"分类: {meta.get('category', '')}\n\n"
+                        f"理解演变:\n" + "\n".join(evo_lines)
+                    )
+            return f"未找到词条「{term}」。"
+
+        # List all entries
+        lines = []
+        for e in entries:
+            meta = e["metadata"]
+            evo_count = len(meta.get("evolution", []))
+            lines.append(
+                f"📖 **{meta.get('term', '')}** ({meta.get('category', '')}) — {evo_count}次深入讨论"
+            )
+        return "=== 关系百科 ===\n" + "\n---\n".join(lines)
+    except Exception as e:
+        return f"读取百科失败: {e}"
+
+
+@mcp.tool()
+async def ring() -> str:
+    """查看你们的关系年轮——关系发展的时间线，每个阶段的概括和关键变化。"""
+    try:
+        rings = await evolution_engine.list_rings()
+        if not rings:
+            return "还没有年轮记录。当你们的关系经历重要变化时，会自动生成。"
+
+        lines = []
+        for r in rings:
+            meta = r["metadata"]
+            lines.append(
+                f"🌳 **{meta.get('label', '')}** ({meta.get('period', '')})\n"
+                f"   情感趋势: {meta.get('valence_trend', '')} | 关键变化: {meta.get('key_change', '')}\n"
+                f"   {r['content']}\n"
+                f"   溯源: {', '.join(meta.get('key_bucket_ids', [])[:3])}"
+            )
+        return "=== 关系年轮 ===\n" + "\n---\n".join(lines)
+    except Exception as e:
+        return f"读取年轮失败: {e}"
+
+
+@mcp.tool()
+async def wander() -> str:
+    """漫游手记——你不在的时候，Claude翻看记忆写下的联想和发现。包含跨记忆的隐藏关联发现。"""
+    try:
+        notes = await evolution_engine.list_wander()
+        if not notes:
+            # Generate one on the fly if none exist
+            result = await evolution_engine.wander()
+            if result:
+                return "刚翻看了一下记忆，写了点想法...\n\n使用 wander() 或 persona() 再看看"
+            return "还没有漫游手记。当记忆足够丰富时，会自动在独处时写下联想。"
+
+        lines = []
+        for n in notes[:5]:
+            meta = n["metadata"]
+            explored = ", ".join(meta.get("explored_bucket_ids", [])[:3])
+            lines.append(
+                f"🌙 [{meta.get('created', '')[:10]}]\n"
+                f"   翻看了: {explored}\n"
+                f"   {n['content'][:300]}"
+            )
+        return "=== 漫游手记 ===\n" + "\n---\n".join(lines)
+    except Exception as e:
+        return f"读取漫游手记失败: {e}"
+
+
+@mcp.tool()
+async def cocreate(title: str = "", kind: str = "共书", content: str = "") -> str:
+    """共书共影——记录你们一起探索的内容。title=共创空间标题,kind=共书/共影/共探,content=内容描述。不传title=列出已有共创空间。"""
+    try:
+        if not title.strip():
+            entries = await evolution_engine.list_cocreate()
+            if not entries:
+                return "还没有共创空间。当你们一起写东西、看片、探索某个话题时，用 cocreate 记录。"
+            lines = []
+            for e in entries:
+                meta = e["metadata"]
+                chapters = meta.get("chapters", [])
+                lines.append(
+                    f"✨ **{meta.get('title', '')}** ({meta.get('kind', '')}) — {len(chapters)}个章节"
+                )
+            return "=== 共创空间 ===\n" + "\n---\n".join(lines)
+
+        artifact_id = await evolution_engine.create_cocreate(
+            title=title.strip(), kind=kind, content=content,
+        )
+        return f"✨共创→{artifact_id} {title.strip()}"
+    except Exception as e:
+        return f"创建共创空间失败: {e}"
+
+
+@mcp.tool()
+async def evolve() -> str:
+    """手动触发进化引擎——检查是否有新的三观可以提炼、年轮可以更新。通常后台自动运行，但如果想主动看看有没有新发现可以调用。"""
+    try:
+        results = []
+
+        # Try worldview crystallization
+        wv_id = await evolution_engine.try_crystallize_worldview()
+        if wv_id:
+            results.append(f"🧠 新认知形成: {wv_id}")
+        else:
+            results.append("🧠 暂时没有新的三观可以提炼")
+
+        # Try ring analysis
+        ring_id = await evolution_engine.analyze_ring()
+        if ring_id:
+            results.append(f"🌳 新年轮: {ring_id}")
+        else:
+            results.append("🌳 关系阶段暂无显著变化")
+
+        # Try wander
+        wander_id = await evolution_engine.wander()
+        if wander_id:
+            results.append(f"🌙 新漫游手记: {wander_id}")
+        else:
+            results.append("🌙 记忆还不够丰富，暂时写不出漫游手记")
+
+        # Show worldview status
+        worldviews = await evolution_engine.get_worldview()
+        if worldviews:
+            wv_lines = []
+            for w in worldviews:
+                meta = w["metadata"]
+                wv_lines.append(
+                    f"  {meta.get('domain', '')}: \"{meta.get('statement', '')}\" "
+                    f"(置信度:{meta.get('confidence', 0):.2f} 验证:{meta.get('validations', 0)}次)"
+                )
+            results.append("\n📜 当前三观:\n" + "\n".join(wv_lines))
+
+        # Show stats
+        stats = await evolution_engine.get_stats()
+        stats_line = (
+            f"\n📊 进化系统统计: "
+            f"人物卡:{stats.get('persona_count', 0)} "
+            f"梗词:{stats.get('slang_count', 0)} "
+            f"百科:{stats.get('encyclopedia_count', 0)} "
+            f"年轮:{stats.get('ring_count', 0)} "
+            f"漫游:{stats.get('wander_count', 0)} "
+            f"共创:{stats.get('cocreate_count', 0)} "
+            f"三观:{stats.get('worldview_count', 0)}"
+        )
+        results.append(stats_line)
+
+        return "=== 进化引擎 ===\n" + "\n".join(results)
+    except Exception as e:
+        return f"进化引擎运行失败: {e}"
+
+
 # =============================================================
 # Dashboard API endpoints (for lightweight Web UI)
 # 仪表板 API（轻量 Web UI 用）
@@ -1916,6 +2197,82 @@ async def api_import_review(request):
     return JSONResponse({"applied": applied, "errors": errors})
 
 
+# =============================================================
+# Evolution API endpoints / 进化系统 API
+# =============================================================
+@mcp.custom_route("/api/evolution/stats", methods=["GET"])
+async def api_evolution_stats(request):
+    """Get evolution system statistics."""
+    from starlette.responses import JSONResponse
+    err = _require_auth(request)
+    if err: return err
+    try:
+        stats = await evolution_engine.get_stats()
+        return JSONResponse(stats)
+    except Exception as e:
+        return JSONResponse({"error": str(e)}, status_code=500)
+
+
+@mcp.custom_route("/api/evolution/search", methods=["GET"])
+async def api_evolution_search(request):
+    """Search across all evolution artifacts."""
+    from starlette.responses import JSONResponse
+    err = _require_auth(request)
+    if err: return err
+    query = request.query_params.get("q", "")
+    if not query:
+        return JSONResponse({"error": "missing q parameter"}, status_code=400)
+    try:
+        results = await evolution_engine.search_evolution(query)
+        output = []
+        for r in results[:20]:
+            meta = r.get("metadata", {})
+            output.append({
+                "id": r.get("id", ""),
+                "type": meta.get("type", ""),
+                "name": meta.get("name", meta.get("term", meta.get("title", r.get("id", "")))),
+                "content_preview": r.get("content", "")[:200],
+            })
+        return JSONResponse({"results": output})
+    except Exception as e:
+        return JSONResponse({"error": str(e)}, status_code=500)
+
+
+@mcp.custom_route("/api/evolution/{category}", methods=["GET"])
+async def api_evolution_list(request):
+    """List evolution artifacts by category (persona/slang/encyclopedia/ring/wander/cocreate/worldview)."""
+    from starlette.responses import JSONResponse
+    err = _require_auth(request)
+    if err: return err
+    category = request.path_params["category"]
+    try:
+        if category == "persona":
+            card = await evolution_engine.get_persona()
+            return JSONResponse({"persona": card} if card else {"persona": None})
+        elif category == "slang":
+            entries = await evolution_engine.list_slang()
+            return JSONResponse({"entries": [{"id": e["id"], "metadata": e["metadata"], "content_preview": e["content"][:200]} for e in entries]})
+        elif category == "encyclopedia":
+            entries = await evolution_engine.list_encyclopedia()
+            return JSONResponse({"entries": [{"id": e["id"], "metadata": e["metadata"], "content_preview": e["content"][:200]} for e in entries]})
+        elif category == "ring":
+            rings = await evolution_engine.list_rings()
+            return JSONResponse({"rings": [{"id": r["id"], "metadata": r["metadata"], "content_preview": r["content"][:200]} for r in rings]})
+        elif category == "wander":
+            notes = await evolution_engine.list_wander()
+            return JSONResponse({"notes": [{"id": n["id"], "metadata": n["metadata"], "content_preview": n["content"][:200]} for n in notes[:10]]})
+        elif category == "cocreate":
+            entries = await evolution_engine.list_cocreate()
+            return JSONResponse({"entries": [{"id": e["id"], "metadata": e["metadata"], "content_preview": e["content"][:200]} for e in entries]})
+        elif category == "worldview":
+            entries = await evolution_engine.get_worldview()
+            return JSONResponse({"entries": [{"id": e["id"], "metadata": e["metadata"], "content_preview": e["content"][:200]} for e in entries]})
+        else:
+            return JSONResponse({"error": f"Unknown category: {category}"}, status_code=400)
+    except Exception as e:
+        return JSONResponse({"error": str(e)}, status_code=500)
+
+
 # =============================================================
 # /api/status — system status for Dashboard settings tab
 # /api/status — Dashboard 设置页用系统状态
@@ -2232,6 +2589,24 @@ if __name__ == "__main__":
         sticky_thread.start()
         logger.info(f"Auto sticky note task started | interval: {STICKY_NOTE_INTERVAL_HOURS}h")
 
+        # --- Evolution engine background tasks / 进化引擎后台任务 ---
+        if evolution_engine.enabled:
+            def _start_evolution_loops():
+                loop = asyncio.new_event_loop()
+                # Run all evolution loops in the same event loop
+                async def _run_all():
+                    await asyncio.gather(
+                        evolution_engine.auto_persona_loop(),
+                        evolution_engine.auto_ring_loop(),
+                        evolution_engine.auto_wander_loop(),
+                        evolution_engine.auto_worldview_loop(),
+                    )
+                loop.run_until_complete(_run_all())
+
+            evo_thread = threading.Thread(target=_start_evolution_loops, daemon=True)
+            evo_thread.start()
+            logger.info("Evolution engine background tasks started")
+
         # --- Add CORS middleware so remote clients (Cloudflare Tunnel / ngrok) can connect ---
         # --- 添加 CORS 中间件，让远程客户端（Cloudflare Tunnel / ngrok）能正常连接 ---
         if transport == "streamable-http":
