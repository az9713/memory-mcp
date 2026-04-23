# memory-mcp

A lightweight semantic memory layer for Claude Code. Stores facts across sessions, retrieves them by meaning, and lets them fade naturally over time — all from a single local SQLite file.

Built by studying three production memory systems and distilling the best ideas into the simplest possible implementation.

---

## Origin: three repos, one insight

This started with Mark Kashef's video **[Every Claude Code Memory Pattern Explained](https://www.youtube.com/watch?v=OMkdlwZxSt8)**, which surveys how serious teams are building persistent memory for AI agents. After watching it, I pulled three repos and ran deep exploratory analysis on each:

### [mempalace](https://github.com/mempalace/mempalace)
The most architecturally inventive of the three. Organizes memory spatially — Drawers (content chunks), Closets (index pointers), Rooms (semantic domains), Wings (project scopes) — and implements a 4-layer progressive loading system that costs only ~600 tokens at wake-up. Key ideas taken: **rank-based boosting over raw cosine distance** (narrative text clusters too tightly for distance to be reliable), **exchange-pair chunking** (a conversation turn + response = atomic unit, never split), and a **temporal knowledge graph** with `valid_from`/`valid_to` on every fact.

### [claudesidian](https://github.com/heyitsnoah/claudesidian)
An Obsidian vault used as a memory backend for Claude Code. The critical insight here was **pre-compaction hooks**: Claude Code summarizes long sessions and destroys injected memory unless you re-inject before the summarization fires. Claudesidian solves this with a `PreCompaction` hook that reads critical files back in. Also introduced the pattern of **agent-scoped memory** — each agent role gets its own memory namespace, reducing noise from irrelevant context.

### [mem0](https://github.com/mem0ai/mem0)
The production-scale reference implementation. Most consequential ideas: the **ADD-only extraction design** (new facts never overwrite existing ones — contradictions accumulate and the LLM reasons over them), **UUID-to-index mapping** (real UUIDs are replaced with "0", "1", "2" before LLM extraction to prevent hallucinated IDs), and **entity spread attenuation** (entities linked to many memories get a diminishing boost to prevent common words from over-boosting irrelevant results). Also the source of the hybrid BM25 + vector search pattern.

### What got left out (deliberately)

The repos collectively contain: entity linking graphs, temporal triple stores, BM25 closet indexes, write-ahead logs, multi-tier ChromaDB collections, rerankers, async extraction pipelines, and multi-tenant session scoping. All of it was considered. None of it made the cut.

The target was a memory system that runs on a laptop, needs no external services, and can be understood by reading one 150-line Python file. The nuclear-bomb-for-a-fist-fight problem is real — most memory systems are engineered for scale that personal use will never reach.

---

## How it works

Three tiers. One decay formula. One SQLite file.

```
score = cosine_similarity × importance × exp(−age_days / half_life)
```

| Tier | Half-life | Use for |
|------|-----------|---------|
| `core` | ∞ (never fades) | Identity, preferences, standing rules |
| `warm` | 30 days | Active projects, recent learnings |
| `ephemeral` | 2 days | Session notes, transient observations |

**Recalling a memory resets its clock.** Things you keep talking about stay alive. Things you stop referencing fade out naturally — no manual cleanup required.

Semantic search uses [`all-MiniLM-L6-v2`](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2) (384-dim, ~80 MB, CPU-fast) via [`sqlite-vec`](https://github.com/asg017/sqlite-vec). The entire vector index lives inside the SQLite file — no Qdrant, no Chroma, no Pinecone.

---

## Installation

**Dependencies:**

```bash
pip install mcp sqlite-vec sentence-transformers
```

**Register with Claude Code (global — recommended):**

```bash
claude mcp add --global memory python "/path/to/memory_server.py"
```

**Register for one project only:**

```bash
claude mcp add memory python "/path/to/memory_server.py"
```

Restart Claude Code. The `memory` server will appear as `✓ Connected` in `claude mcp list`.

The database is created automatically at `~/.claude/memory.db` on first use.

---

## Usage

You never call the tools directly. Talk to Claude normally — it decides when to store and retrieve.

### Store a preference

> "Remember that I never want comments in generated code unless the why is non-obvious."

Claude calls `remember("Never add comments unless the why is non-obvious", tier="core", importance=1.0)`.

### Store project context

> "We're building a FastAPI service that replaces a legacy Django monolith. The migration is happening module by module, starting with auth."

Claude stores this as `warm` — it's active context that will naturally fade once the project is done.

### Recall semantically

> "What do you know about our backend architecture?"

Claude calls `recall("backend architecture")` and surfaces the migration note even though the words don't match exactly.

### Review what's stored

> "Show me everything you remember, grouped by how long it's been since you used each memory."

Claude calls `memories()` and presents the full list sorted by vitality.

### Clean up

> "Forget that note about the Django migration — we finished it."

Claude calls `forget(memory_id)` and removes it permanently.

---

## Use cases

**Persistent preferences across sessions**
Store coding style preferences, communication preferences, and tool preferences as `core` memories. Claude will apply them automatically in every future session without being reminded.

**Project handoff**
At the end of a work session: "Summarize where we left off and store it." At the start of the next: "What were we working on?" The context survives the session boundary.

**Long-running project context**
Multi-week projects accumulate decisions, constraints, and rationale. Store architectural decisions as `warm` memories and recall them when revisiting related code. They fade naturally once the project ends.

**Personal knowledge base**
Store things you'd otherwise put in notes: "The production DB uses read replicas — writes go to primary, reads go to replica-1 or replica-2." Recall it when you need it, forget it when it's stale.

**Agent specialization**
Run Claude Code from different project directories, each registered with the same global memory server but storing different `warm`-tier context. Memory is shared across all sessions but the most relevant memories surface based on semantic query.

---

## Architecture

```
memory_server.py          ← single-file MCP server
~/.claude/memory.db       ← SQLite database (auto-created)
~/.cache/huggingface/     ← model cache (~80 MB, one-time download)
```

Two tables in the database:

```sql
-- Text and metadata
CREATE TABLE memories (
    id            TEXT PRIMARY KEY,   -- UUID
    content       TEXT NOT NULL,
    tier          TEXT NOT NULL,      -- 'core' | 'warm' | 'ephemeral'
    importance    REAL NOT NULL,      -- 0.0 – 1.0
    created_at    REAL NOT NULL,      -- Unix timestamp
    last_accessed REAL NOT NULL       -- reset on every recall
);

-- Vector index (managed by sqlite-vec)
CREATE VIRTUAL TABLE mem_vss USING vec0(
    embedding float[384]
);
```

`recall` over-fetches 3× the requested limit by vector distance, then re-ranks by the full decay score. This prevents a very recent but tangential memory from beating a slightly older but highly relevant one on raw distance alone.

Ephemeral memories not accessed in 7 days are pruned on server startup.

---

## Four tools

| Tool | What it does |
|------|-------------|
| `remember(content, tier, importance)` | Store a memory |
| `recall(query, limit)` | Semantic search with decay ranking |
| `forget(memory_id)` | Delete permanently by ID |
| `memories(tier)` | List all, sorted by vitality |

---

## Configuration

All constants are at the top of `memory_server.py`:

| Constant | Default | Description |
|----------|---------|-------------|
| `DB_PATH` | `~/.claude/memory.db` | Database location |
| `MODEL_NAME` | `all-MiniLM-L6-v2` | Embedding model |
| `HALF_LIFE` | `{core: ∞, warm: 30, ephemeral: 2}` | Decay half-lives in days |
| `PRUNE_AFTER_DAYS` | `7` | Delete stale ephemeral memories after this many days |

> **Warning:** Changing `MODEL_NAME` after storing memories breaks all existing search. Delete `memory.db` and start fresh if you switch models.

---

## Docs

Full documentation is in [`docs/`](docs/index.md):

- [Quickstart](docs/getting-started/quickstart.md)
- [How memory works](docs/concepts/how-memory-works.md)
- [Tool reference](docs/reference/tools.md)
- [Configuration](docs/reference/configuration.md)
- [Troubleshooting](docs/troubleshooting/common-issues.md)

---

## Stack

- [`mcp`](https://github.com/modelcontextprotocol/python-sdk) — Anthropic's MCP Python SDK (FastMCP)
- [`sqlite-vec`](https://github.com/asg017/sqlite-vec) — vector similarity search as a SQLite extension
- [`sentence-transformers`](https://www.sbert.net/) — local embedding model runner
- `all-MiniLM-L6-v2` — 384-dim model, 80 MB, CPU-fast, no GPU required
