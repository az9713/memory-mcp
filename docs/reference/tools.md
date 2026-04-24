# Tool reference

All four MCP tools exposed by the memory server. Claude calls these on your behalf — you interact through natural language, not direct tool calls.

---

## `remember`

Store a new memory.

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `content` | string | required | The text to store. Any length; no formatting required. |
| `tier` | string | `"warm"` | One of `"core"`, `"warm"`, `"ephemeral"`. Controls decay. |
| `scope` | string | `"global"` | Memory namespace. Use different values to isolate projects/agents. |
| `importance` | float | `0.5` | 0.0 to 1.0. Scales the decay score — higher importance resists fading. |

### Returns

```json
{
  "id": "d635d6ae-394b-4d45-a138-603f1734f169",
  "tier": "warm",
  "importance": 0.8,
  "stored": true
}
```

On error:

```json
{
  "stored": false,
  "error": "tier must be one of ['core', 'ephemeral', 'warm']"
}
```

### Tier guide

| Tier | When to use |
|------|-------------|
| `core` | Facts that should always be true: preferences, identity, rules, values |
| `warm` | Active context: current project, recent decisions, in-progress work |
| `ephemeral` | Session-only facts: today's task, temporary notes, transient state |

### Importance guide

| Value | When to use |
|-------|-------------|
| `1.0` | Critical facts that must survive a long time without being recalled |
| `0.7 – 0.9` | Important but not critical |
| `0.5` | Default — normal facts |
| `0.1 – 0.3` | Low-signal observations you want to keep briefly |

### Example

> "Remember that I'm allergic to TypeScript strict mode and always use `skipLibCheck: true`."

Claude stores this as `core` with `importance=1.0` — it's a strong permanent preference.

---

## `recall`

Search memories by semantic meaning and return the best matches.

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `query` | string | required | Natural language search query. |
| `limit` | integer | `5` | Max results to return. Clamped to 1–20. |
| `scope` | string | `"global"` | Search only within this memory namespace. |

### Returns

A list of matches, sorted by score descending:

```json
[
  {
    "id": "d635d6ae-394b-4d45-a138-603f1734f169",
    "content": "I prefer concise answers with no preamble.",
    "tier": "core",
    "score": 0.8741
  },
  {
    "id": "2abca6a3-7865-4877-bccc-9d9e67d6be32",
    "content": "Currently refactoring the auth module in /src/auth.",
    "tier": "warm",
    "score": 0.3102
  }
]
```

Returns an empty list `[]` if no matches are found or if `query` is empty.

### Scoring

Each result's `score` is `cosine_similarity × importance × decay`. A score of 0.87 means the memory is highly relevant, important, and recently accessed. A score of 0.03 means it's either distant in meaning, low importance, or very stale.

### Side effect

Every memory that appears in results has its `last_accessed` timestamp updated to now, resetting its decay clock.

### Example

> "What do you know about my coding preferences?"

Claude calls `recall("coding preferences", limit=5)` and returns the top matches for you to see.

---

## `forget`

Permanently delete a memory by its ID.

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `memory_id` | string | required | The UUID of the memory to delete. Get this from a `remember` or `recall` result. |

### Returns

On success:

```json
{ "deleted": true }
```

On failure (ID not found):

```json
{ "deleted": false, "error": "memory not found" }
```

### Notes

Deletion is permanent and immediate. There is no undo. Both the metadata row and the vector index entry are removed.

### Example

> "Forget that note about the TypeScript project — it's done."

Claude looks up the memory ID from a recent `recall`, then calls `forget` with it.

---

## `memories`

List all stored memories, optionally filtered by tier, sorted by vitality.

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `tier` | string or null | `null` | Filter to `"core"`, `"warm"`, or `"ephemeral"`. Omit for all tiers. |
| `scope` | string | `"global"` | List memories only in this namespace. |

### Returns

A list of all matching memories, sorted by `vitality` descending (most alive first):

```json
[
  {
    "id": "d635d6ae-394b-4d45-a138-603f1734f169",
    "content": "I prefer concise answers with no preamble.",
    "tier": "core",
    "importance": 1.0,
    "age_days": 12.3,
    "vitality": 1.0
  },
  {
    "id": "2abca6a3-7865-4877-bccc-9d9e67d6be32",
    "content": "Currently refactoring the auth module in /src/auth.",
    "tier": "warm",
    "importance": 0.8,
    "age_days": 45.1,
    "vitality": 0.2341
  }
]
```

### Vitality explained

`vitality = importance × exp(−age_days / half_life)`. Core memories always show vitality equal to their importance. A warm memory at importance 0.8 that hasn't been accessed in 60 days has vitality ≈ 0.08.

### Notes

`memories()` does not update `last_accessed`. Listing your memories does not keep them alive — only `recall` does that.

### Example

> "Show me everything you remember about me in the project-a scope."

Claude calls `memories(scope="project-a")` and presents that scoped list.

> "What are my core memories?"

Claude calls `memories(tier="core")`.
