# Configuration reference

All tunable constants are at the top of `memory_server.py`. There is no config file — edit the source directly.

---

## Constants

### `DB_PATH`

```python
DB_PATH = os.path.expanduser("~/.claude/memory.db")
```

**Type:** string (path)
**Default:** `~/.claude/memory.db`

Path to the SQLite database file. Created automatically on first use, including any missing parent directories.

Change this to keep multiple separate memory databases (e.g., one per project):

```python
DB_PATH = os.path.expanduser("~/my-project/.memory.db")
```

---

### `MODEL_NAME`

```python
MODEL_NAME = "all-MiniLM-L6-v2"
```

**Type:** string (HuggingFace model ID)
**Default:** `all-MiniLM-L6-v2`

The sentence-transformers model used to embed memories and queries. `all-MiniLM-L6-v2` produces 384-dimensional vectors, runs on CPU, and downloads ~80 MB on first use.

> **Warning:** Changing this after memories are already stored will break all existing search results. The stored vectors will be in the old model's embedding space; queries will use the new model's space. The two are incompatible. If you switch models, delete `memory.db` and start fresh.

Alternative models (must match `EMBEDDING_DIM`):

| Model | Dims | Size | Quality |
|-------|------|------|---------|
| `all-MiniLM-L6-v2` | 384 | ~80 MB | Good — recommended |
| `all-MiniLM-L12-v2` | 384 | ~120 MB | Better, slower |
| `all-mpnet-base-v2` | 768 | ~420 MB | Best, much slower |

---

### `EMBEDDING_DIM`

```python
EMBEDDING_DIM = 384
```

**Type:** integer
**Default:** `384`

Must match the output dimensionality of `MODEL_NAME`. Used in the `CREATE VIRTUAL TABLE` statement for `mem_vss`. Changing this without deleting the database will cause a schema error on startup.

---

### `HALF_LIFE`

```python
HALF_LIFE = {"core": float("inf"), "warm": 30.0, "ephemeral": 2.0}
```

**Type:** dict mapping tier name → float (days)
**Default:** core=∞, warm=30, ephemeral=2

Controls how fast each tier decays. A half-life of 30 days means a memory loses half its score every 30 days (when not recalled).

To make warm memories last longer:

```python
HALF_LIFE = {"core": float("inf"), "warm": 60.0, "ephemeral": 3.0}
```

To make ephemeral memories disappear faster (e.g., within hours):

```python
HALF_LIFE = {"core": float("inf"), "warm": 30.0, "ephemeral": 0.25}  # 6 hours
```

---

### `VALID_TIERS`

```python
VALID_TIERS = {"core", "warm", "ephemeral"}
```

**Type:** set of strings

The allowed tier names. If you add a new tier to `HALF_LIFE`, add it here too or `remember` will reject it.

---

### `PRUNE_AFTER_DAYS`

```python
PRUNE_AFTER_DAYS = 7
```

**Type:** integer (days)
**Default:** `7`

Ephemeral memories not accessed within this many days are deleted when the server starts. Warm and core memories are never pruned automatically.

To prune ephemeral memories more aggressively (e.g., same-day cleanup):

```python
PRUNE_AFTER_DAYS = 1
```

To disable automatic pruning entirely:

```python
PRUNE_AFTER_DAYS = 999999
```

---

### `CURRENT_SCHEMA_VERSION`

```python
CURRENT_SCHEMA_VERSION = 1
```

**Type:** integer
**Default:** `1`

The highest database schema migration version the server expects. On startup,
the server checks `schema_migrations` and applies any missing versions up to
this value.

Only increase this when you add a new migration entry in `memory_server.py`.
If this number is increased without a corresponding migration function, startup
fails with a missing migration error.

---

## Environment

No environment variables are read by `memory_server.py`. All configuration is in the source file.

The server does inherit the environment of the process that spawns it (Claude Code), which means `~` expansion uses the system's `HOME` / `USERPROFILE`.
