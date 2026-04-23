# How memory works

The memory server stores facts as text, retrieves them by meaning (not exact wording), and lets them fade over time unless they stay relevant.

---

## The three tiers

Every memory belongs to exactly one tier. The tier controls how fast the memory fades.

| Tier | Half-life | Pruned after | Use for |
|------|-----------|--------------|---------|
| `core` | Never | Never | Identity, strong preferences, standing rules — things that should always be true |
| `warm` | 30 days | Never (decays to near-zero) | Active projects, recent learnings, contextual facts |
| `ephemeral` | 2 days | 7 days of no access | Session notes, transient observations, one-off facts |

A **half-life** of 30 days means a warm memory at full importance loses half its score every 30 days. After 90 days without any recall it's at ~12.5% of its original score — still retrievable, but far less likely to surface.

Core memories have no decay. A core memory stored today will score the same in five years.

---

## The decay formula

Every time memories are scored — during `recall` or `memories` — each result is multiplied by a decay factor computed at that instant:

```
score = cosine_similarity × importance × exp(−age_days / half_life)
```

Where:
- `cosine_similarity` — how semantically close the query is to the stored content (0.0 to 1.0)
- `importance` — the value you set when storing (0.0 to 1.0, default 0.5)
- `age_days` — days since `last_accessed` (not since creation)
- `half_life` — 30 for warm, 2 for ephemeral, ∞ for core

For core memories, the `exp(...)` term is 1.0 (no decay regardless of age).

---

## Reinforcement on recall

The key behavior: **recalling a memory resets its clock**.

Every time a memory appears in a `recall` result, its `last_accessed` timestamp is updated to now. This means memories that keep coming up naturally in conversation stay alive. Memories you stop talking about fade out on their own.

This mirrors how human memory works — things you use stay sharp; things you don't gradually blur.

---

## Vitality

`vitality` is the decay score computed without the similarity component:

```
vitality = importance × exp(−age_days / half_life)
```

It's what `memories()` uses to sort results. A memory with vitality 0.9 is alive and well; one at 0.05 is fading. Core memories always show vitality equal to their importance (1.0 if stored at max importance).

---

## Semantic search

The server doesn't do keyword matching. When you recall, your query is converted into a 384-dimensional vector using the `all-MiniLM-L6-v2` model — the same model that embedded the original memory. The search finds memories whose vectors are geometrically close to your query vector.

This means:
- "my communication style" finds "I prefer concise answers" even with no shared words
- "python project status" finds "working on the auth refactor" by topic proximity
- Spelling variations and synonyms work naturally

The search over-fetches 3× the requested limit, then re-ranks by the full decay score. This prevents a very old but relevant memory from losing to a recent but tangential one by raw vector distance alone.

---

## Storage

Everything lives in a single SQLite file at `~/.claude/memory.db`. Two tables:

**`memories`** — the text and metadata:

| Column | Type | Notes |
|--------|------|-------|
| `id` | TEXT | UUID, primary key |
| `content` | TEXT | The stored fact |
| `tier` | TEXT | `core`, `warm`, or `ephemeral` |
| `importance` | REAL | 0.0 – 1.0 |
| `created_at` | REAL | Unix timestamp, never changes |
| `last_accessed` | REAL | Unix timestamp, updated on every recall |

**`mem_vss`** (virtual, managed by sqlite-vec) — the vector index:

| Column | Type | Notes |
|--------|------|-------|
| `rowid` | INTEGER | Matches `memories.rowid` for joining |
| `embedding` | FLOAT[384] | 384-dim unit vector |

---

## Pruning

On server start, ephemeral memories not accessed in 7 days are deleted automatically. Warm and core memories are never deleted automatically — they only decay toward zero score.

To delete a specific memory manually, use [`forget`](../reference/tools.md#forget).
